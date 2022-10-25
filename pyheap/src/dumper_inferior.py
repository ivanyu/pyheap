#
# Copyright 2022 Ivan Yurchenko
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from __future__ import annotations
import gc
import json
from contextlib import closing
import sys
import threading
import time
import traceback
from types import FrameType
from typing import List, Any, Dict, Tuple, BinaryIO
import inspect
from functools import lru_cache
from datetime import datetime, timezone
import struct
from uuid import UUID, uuid4

"""
This module is executed in the context of the inferior.
"""

# This file has some optimizations to reduce the number of object allocations and boost speed,
# which results in more obscure code. Please, when you try to improve the code,
# make sure you're making the right trade-off with the performance.


# Inputs:
heap_file: str
str_repr_len: int
progress_file: str

# Output:
result = None


class _HeapWriter:
    _MAGIC = 123_000_321
    _VERSION = 1

    _BOOL_STRUCT = struct.Struct("!?")
    _UNSIGNED_INT_STRUCT = struct.Struct("!I")
    _UNSIGNED_LONG_STRUCT = struct.Struct("!Q")

    _FLAG_WITH_STR_REPR = 1

    def __init__(self, *, f: BinaryIO, with_str_repr: bool) -> None:
        self._f = f
        self._marks = {}

        self._flags = 0
        if with_str_repr:
            self._flags = self._flags | self._FLAG_WITH_STR_REPR

    def write_header(self) -> None:
        self._write_magic()

        self.write_unsigned_int(self._VERSION)
        local_tz = datetime.now(timezone.utc).astimezone().tzinfo
        created_at = datetime.now(tz=local_tz).isoformat()
        self.write_string(created_at)

        self.write_unsigned_long(self._flags)

    def write_footer(self) -> None:
        self._write_magic()

    def _write_magic(self) -> None:
        self.write_unsigned_long(self._MAGIC)

    def write_string(self, value: str) -> None:
        b = value.encode("utf-8")
        self._f.write(struct.pack(f"!H{len(b)}s", len(b), b))

    def write_bool(self, value: bool) -> None:
        self._f.write(self._BOOL_STRUCT.pack(value))

    def write_unsigned_int(self, value: int) -> None:
        self._f.write(self._UNSIGNED_INT_STRUCT.pack(value))

    def write_unsigned_long(self, value: int) -> None:
        self._f.write(self._UNSIGNED_LONG_STRUCT.pack(value))

    def mark_unsigned_int(self) -> UUID:
        mark = uuid4()
        self._marks[mark] = self._f.tell()
        self.write_unsigned_int(0)
        return mark

    def close_unsigned_int_mark(self, mark: UUID, value: int) -> None:
        offset = self._f.tell()
        self._f.seek(self._marks[mark])
        self.write_unsigned_int(value)
        self._f.seek(offset)
        del self._marks[mark]


def _dump_heap() -> str:
    global_start = time.monotonic()
    visited = 0

    gc_tracked_objects = _get_gc_tracked_objects()
    with open(heap_file, "wb") as f:
        writer = _HeapWriter(f=f, with_str_repr=str_repr_len >= 0)
        writer.write_header()

        messages = []
        all_locals = _write_threads_and_return_locals(writer, messages)

        with closing(ProgressReporter(progress_file)) as progress_reporter:
            types = _write_objects_jsons_and_return_types(
                writer, gc_tracked_objects, all_locals, progress_reporter
            )

        writer.write_unsigned_int(len(types))
        for addr, type_name in types.items():
            writer.write_unsigned_long(addr)
            writer.write_string(type_name)

        writer.write_footer()

    result = (
        f"Heap dumped to {heap_file}. "
        + f"Visited {visited} objects. "
        + f"Took {(time.monotonic() - global_start):.3f} seconds"
    )
    if messages:
        result += "\n" + "\n".join(messages) + "\n"
    return result


def _get_gc_tracked_objects() -> List[Any]:
    invisible_objects = set()
    invisible_objects.add(id(invisible_objects))
    invisible_objects.add(id(heap_file))
    invisible_objects.add(id(str_repr_len))
    invisible_objects.add(id(result))
    invisible_objects.add(id(_dump_heap))
    invisible_objects.add(id(_write_objects_jsons_and_return_types))
    invisible_objects.add(id(_write_threads_and_return_locals))
    invisible_objects.add(id(_shadowed_dict_orig))
    invisible_objects.add(id(_check_class_orig))
    invisible_objects.add(id(ProgressReporter))
    invisible_objects.add(id(_HeapWriter))

    return [o for o in gc.get_objects() if id(o) not in invisible_objects]


def _write_threads_and_return_locals(
    writer: _HeapWriter,
    messages: List[str],
) -> List[Any]:
    current_frames = sys._current_frames()
    all_locals: List[Any] = []

    all_threads = list(threading.enumerate())
    writer.write_unsigned_int(len(all_threads))

    for thread in all_threads:
        writer.write_string(thread.name)
        writer.write_bool(thread.is_alive())
        writer.write_bool(thread.daemon)

        current_thread_frame = current_frames.get(thread.ident)
        if current_thread_frame is None:
            messages.append(f"WARNING - stack for thread {thread.name} not found")
            # Stack trace length
            writer.write_unsigned_int(0)
            continue

        # Skip the dumper frames, which may be on top of normal frames.
        stack_trace: List[Tuple[FrameType, int]] = [
            el
            for el in traceback.walk_stack(current_thread_frame)
            if el[0].f_code.co_filename != __file__
        ]
        # Stack trace length
        writer.write_unsigned_int(len(stack_trace))
        for frame, lineno in stack_trace:
            # File name
            writer.write_string(frame.f_code.co_filename)
            # Line number
            writer.write_unsigned_int(lineno)
            # Function name
            writer.write_string(frame.f_code.co_name)

            # Locals:
            writer.write_unsigned_int(len(frame.f_locals))
            for loc_name, loc_value in frame.f_locals.items():
                writer.write_string(loc_name)
                writer.write_unsigned_long(id(loc_value))

            all_locals.extend(frame.f_locals.values())
    return all_locals


def _write_objects_jsons_and_return_types(
    writer: _HeapWriter,
    gc_tracked_objects: List[Any],
    locals_: List[Any],
    progress_reporter: ProgressReporter,
) -> Dict[int, str]:
    seen_ids = set()
    to_visit = []
    to_visit.extend(gc_tracked_objects)
    to_visit.extend(locals_)
    result_types: Dict[int, str] = {}

    inspect._shadowed_dict = lru_cache(maxsize=None)(_shadowed_dict_orig)
    inspect._check_class = lru_cache(maxsize=None)(_check_class_orig)
    invisible_objects = set()
    invisible_objects.add(id(inspect._shadowed_dict))
    invisible_objects.add(id(inspect._check_class))

    done = 0
    progress_reporter.report(done, len(to_visit))

    # Object count -- will be written in the end.
    object_count_mark = writer.mark_unsigned_int()

    while len(to_visit) > 0:
        obj = to_visit.pop()
        obj_id = id(obj)

        if obj_id in seen_ids or obj_id in invisible_objects:
            continue
        seen_ids.add(obj_id)
        done += 1

        type_ = type(obj)
        result_types[id(type_)] = type_.__name__

        # Self-references here are fine.
        referents = [r for r in gc.get_referents(obj) if id(r) not in invisible_objects]
        to_visit.extend(referents)

        # Address
        writer.write_unsigned_long(id(obj))
        # Type
        writer.write_unsigned_long(id(type_))
        # Size
        writer.write_unsigned_int(sys.getsizeof(obj))

        # Referents
        writer.write_unsigned_int(len(referents))
        for r in referents:
            writer.write_unsigned_long(id(r))

        # Attributes
        attrs: List[Tuple[str, object]] = []
        for attr in dir(obj):
            try:
                attr_value = inspect.getattr_static(obj, attr)
                to_visit.append(attr_value)
                attrs.append((attr, attr_value))
            except (AttributeError, ValueError):
                pass
        writer.write_unsigned_int(len(attrs))
        for attr, attr_value in attrs:
            writer.write_string(attr)
            writer.write_unsigned_long(id(attr_value))

        # String representation
        if str_repr_len >= 0:
            try:
                str_repr = str(obj)[:str_repr_len]
            except:
                str_repr = "<ERROR on __str__>"
            writer.write_string(str_repr)

        progress_reporter.report(done, len(to_visit))

    # Object count -- real value.
    writer.close_unsigned_int_mark(object_count_mark, done)

    progress_reporter.report(done, len(to_visit))
    return result_types


class ProgressReporter:
    _GRANULARITY = 1_000

    def __init__(self, path: str) -> None:
        self._f = open(path, "w")
        self._started = time.monotonic()

    def report(self, done: int, remain: int) -> None:
        if done % ProgressReporter._GRANULARITY == 0:
            self._f.seek(0)
            self._f.truncate()
            json.dump(
                {
                    "since_start_sec": time.monotonic() - self._started,
                    "done": done,
                    "remain": remain,
                },
                self._f,
            )
            self._f.write("\n")
            self._f.flush()

    def close(self) -> None:
        self._f.close()


_shadowed_dict_orig = inspect._shadowed_dict
_check_class_orig = inspect._check_class

try:
    result = _dump_heap()
except:
    print(traceback.format_exc())
    result = traceback.format_exc()
finally:
    inspect._shadowed_dict = _shadowed_dict_orig
    inspect._check_class = _check_class_orig
