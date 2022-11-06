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
from typing import List, Any, Dict, Tuple, BinaryIO, Set, Type, Optional
import inspect
from functools import lru_cache
from datetime import datetime, timezone
import struct
from uuid import UUID, uuid4
from typing.io import IO

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
result = ""  # avoid dealing with None
result_error = ""  # avoid dealing with None

# Max negative range of short int. "-1" because the indexing starts with 1.
_MAX_FREQUENT_ATTR_COUNT = (0b111111111111111 + 1) - 1
# Max positive range of short int.
_MAX_FREQUENT_ATTR_LENGTH = 0b111111111111111


class _HeapWriter:
    _MAGIC = 123_000_321
    _VERSION = 1

    _BOOL_STRUCT = struct.Struct("!?")
    _SIGNED_SHORT_STRUCT = struct.Struct("!h")
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
        self.write_long_string(created_at)

        self.write_unsigned_long(self._flags)

    def write_footer(self) -> None:
        self._write_magic()

    def _write_magic(self) -> None:
        self.write_unsigned_long(self._MAGIC)

    def write_long_string(self, value: str) -> None:
        b = value.encode("utf-8")
        self._f.write(struct.pack(f"!H{len(b)}s", len(b), b))

    def write_short_string(self, value: str) -> None:
        b = value.encode("utf-8")
        self._f.write(struct.pack(f"!h{len(b)}s", len(b), b))

    def write_signed_short(self, value: int) -> None:
        self._f.write(self._SIGNED_SHORT_STRUCT.pack(value))

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

    def write_attribute(
        self,
        attribute_name: str,
        attribute_value: Any,
        frequent_attributes: Dict[str, int],
    ) -> None:
        freq_attr_idx = frequent_attributes.get(attribute_name)
        if freq_attr_idx is not None:
            self.write_signed_short(-1 * freq_attr_idx - 1)
        else:
            self.write_short_string(attribute_name)
        self.write_unsigned_long(id(attribute_value))


def _dump_heap() -> str:
    global_start = time.monotonic()

    gc_tracked_objects = _get_gc_tracked_objects()
    with open(heap_file, "wb") as f:
        writer = _HeapWriter(f=f, with_str_repr=str_repr_len >= 0)
        writer.write_header()

        messages = []
        all_locals = _write_threads_and_return_locals(writer, messages)

        frequent_attributes = _write_frequent_attributes(writer)
        common_types, objects_to_visit = _write_common_types(
            writer, frequent_attributes
        )

        with closing(ProgressReporter(progress_file)) as progress_reporter:
            types, visited = _write_objects_and_return_types(
                writer=writer,
                gc_tracked_objects=gc_tracked_objects,
                locals_=all_locals,
                frequent_attributes=frequent_attributes,
                common_types=common_types,
                additional_objects_to_visit=objects_to_visit,
                progress_reporter=progress_reporter,
                messages=messages,
            )

        writer.write_unsigned_int(len(types))
        for addr, type_name in types.items():
            writer.write_unsigned_long(addr)
            writer.write_long_string(type_name)

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
    invisible_objects.add(id(result_error))
    invisible_objects.add(id(_dump_heap))
    invisible_objects.add(id(_write_objects_and_return_types))
    invisible_objects.add(id(_write_frequent_attributes))
    invisible_objects.add(id(_write_common_types))
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
        writer.write_long_string(thread.name)
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
            writer.write_long_string(frame.f_code.co_filename)
            # Line number
            writer.write_unsigned_int(lineno)
            # Function name
            writer.write_long_string(frame.f_code.co_name)

            # Locals:
            writer.write_unsigned_int(len(frame.f_locals))
            for loc_name, loc_value in frame.f_locals.items():
                writer.write_long_string(loc_name)
                writer.write_unsigned_long(id(loc_value))

            all_locals.extend(frame.f_locals.values())
    return all_locals


def _write_frequent_attributes(writer: _HeapWriter) -> Dict[str, int]:
    """Add the attributes of most common types."""
    frequent_attrs = set()

    frequent_attrs.update(dir(object))
    frequent_attrs.update(dir(type))
    frequent_attrs.update(dir(super))

    frequent_attrs.update(dir(int))
    frequent_attrs.update(dir(float))
    frequent_attrs.update(dir(complex))
    frequent_attrs.update(dir(bool))

    frequent_attrs.update(dir(str))
    frequent_attrs.update(dir(bytes))
    frequent_attrs.update(dir(bytearray))
    frequent_attrs.update(dir(memoryview))

    frequent_attrs.update(dir(list))
    frequent_attrs.update(dir(tuple))
    frequent_attrs.update(dir(range))
    frequent_attrs.update(dir(slice))
    frequent_attrs.update(dir(filter))
    frequent_attrs.update(dir(reversed))

    frequent_attrs.update(dir(set))
    frequent_attrs.update(dir(frozenset))
    frequent_attrs.update(dir(dict))

    import contextlib

    frequent_attrs.update(dir(contextlib.AbstractContextManager))
    frequent_attrs.update(dir(contextlib.AbstractAsyncContextManager))
    frequent_attrs.update(dir(contextlib.ContextDecorator))
    frequent_attrs.update(dir(contextlib.closing))
    frequent_attrs.update(dir(contextlib.redirect_stdout))
    frequent_attrs.update(dir(contextlib.redirect_stderr))
    frequent_attrs.update(dir(contextlib.suppress))
    frequent_attrs.update(dir(contextlib.ExitStack))
    frequent_attrs.update(dir(contextlib.AsyncExitStack))
    frequent_attrs.update(dir(contextlib.nullcontext))

    frequent_attrs.update(dir(_write_frequent_attributes))  # function
    frequent_attrs.update(dir(_write_frequent_attributes.__code__))  # code
    frequent_attrs.update(dir(list.__init__))  # wrapper_descriptor
    frequent_attrs.update(dir(len))  # builtin_function_or_method
    frequent_attrs.update(dir(set.union))  # method_descriptor

    frequent_attrs.update(dir(property))
    frequent_attrs.update(dir(classmethod))
    frequent_attrs.update(dir(staticmethod))

    frequent_attrs.update(dir(Exception))
    frequent_attrs.update(dir(AssertionError))
    frequent_attrs.update(dir(AttributeError))
    frequent_attrs.update(dir(OSError))
    frequent_attrs.update(dir(DeprecationWarning))
    frequent_attrs.update(dir(GeneratorExit))
    frequent_attrs.update(dir(ImportError))
    frequent_attrs.update(dir(SyntaxError))

    import functools

    if sys.version_info >= (3, 9):
        frequent_attrs.update(dir(functools.cache))
    frequent_attrs.update(dir(functools.cached_property))

    import enum

    frequent_attrs.update(dir(enum.Enum))

    import typing

    frequent_attrs.update(dir(typing.List))
    frequent_attrs.update(dir(typing.Set))
    frequent_attrs.update(dir(typing.Tuple))
    frequent_attrs.update(dir(typing.Optional))
    frequent_attrs.update(dir(typing.TypeVar))
    frequent_attrs.update(dir(typing.Iterable))
    frequent_attrs.update(dir(typing.Protocol))
    frequent_attrs.update(dir(typing.Generator))
    frequent_attrs.update(dir(typing.Sequence))
    frequent_attrs.update(dir(typing.Container))
    frequent_attrs.update(dir(typing.MutableSequence))
    frequent_attrs.update(dir(typing.AbstractSet))
    frequent_attrs.update(dir(typing.MappingView))
    frequent_attrs.update(dir(typing.ItemsView))
    frequent_attrs.update(dir(typing.KeysView))
    frequent_attrs.update(dir(typing.ValuesView))
    frequent_attrs.update(dir(typing.ContextManager))
    frequent_attrs.update(dir(typing.Mapping))
    frequent_attrs.update(dir(typing.MutableMapping))
    frequent_attrs.update(dir(typing.IO))
    frequent_attrs.update(dir(typing.TextIO))
    frequent_attrs.update(dir(typing.Match))
    frequent_attrs.update(dir(typing.Pattern))
    frequent_attrs.update(dir(typing.NamedTuple))
    frequent_attrs.update(dir(typing.NewType))

    import dataclasses

    frequent_attrs.update(dir(dataclasses.dataclass))
    frequent_attrs.update(dir(dataclasses.Field))
    frequent_attrs.update(dir(dataclasses.FrozenInstanceError))

    from builtins import __loader__

    frequent_attrs.update(dir(__loader__))

    frequent_attrs_list = [
        a for a in frequent_attrs if len(a) <= _MAX_FREQUENT_ATTR_LENGTH
    ]
    frequent_attrs_list.sort(key=lambda x: len(x), reverse=True)
    frequent_attrs_list = frequent_attrs_list[:_MAX_FREQUENT_ATTR_COUNT]

    result: Dict[str, int] = {}

    writer.write_unsigned_int(len(frequent_attrs_list))
    for i, attr in enumerate(frequent_attrs_list):
        writer.write_short_string(attr)
        result[attr] = i

    return result


def _write_common_types(
    writer: _HeapWriter, frequent_attributes: Dict[str, int]
) -> Tuple[Set[Type], List[Any]]:
    """Write attributes of "common" types.

    We consider "common" the most basic (and most frequent) types, which are not dict-based,
    i.e. can't have attributes other than the built-in attributes.
    """
    common_types_and_examples = {
        int: 0,
        float: 0.0,
        bool: False,
        str: "",
        bytes: b"",
        list: [],
        set: set(),
        dict: {},
    }
    to_visit = []

    writer.write_unsigned_int(len(common_types_and_examples))
    for t, example in common_types_and_examples.items():
        to_visit.append(t)

        # Address
        writer.write_unsigned_long(id(t))

        # Attributes
        attrs: List[Tuple[str, object]] = []
        for attr in dir(example):
            try:
                attr_value = inspect.getattr_static(example, attr)
                to_visit.append(attr_value)
                attrs.append((attr, attr_value))
            except (AttributeError, ValueError):
                pass

        writer.write_unsigned_int(len(attrs))
        for attr, attr_value in attrs:
            writer.write_attribute(attr, attr_value, frequent_attributes)

    return set(common_types_and_examples.keys()), to_visit


def _write_objects_and_return_types(
    *,
    writer: _HeapWriter,
    gc_tracked_objects: List[Any],
    locals_: List[Any],
    frequent_attributes: Dict[str, int],
    common_types: Set[Type],
    additional_objects_to_visit: List[Any],
    progress_reporter: ProgressReporter,
    messages: List[str],
) -> Tuple[Dict[int, str], int]:
    seen_ids = set()
    to_visit: List[Any] = []
    to_visit.extend(gc_tracked_objects)
    to_visit.extend(locals_)
    to_visit.extend(common_types)
    to_visit.extend(additional_objects_to_visit)

    result_types: Dict[int, str] = {id(t): t.__name__ for t in common_types}

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
        obj_size = 0
        try:
            obj_size = sys.getsizeof(obj)
        except Exception as e:
            messages.append(f"Error getting size of {type_}: {e}")
        writer.write_unsigned_int(obj_size)

        # Referents
        writer.write_unsigned_int(len(referents))
        for r in referents:
            writer.write_unsigned_long(id(r))

        # Attributes -- write them only for non-"common" types.
        if type_ not in common_types:
            attrs: List[Tuple[str, object]] = []
            try:
                for attr in dir(obj):
                    try:
                        attr_value = inspect.getattr_static(obj, attr)
                        to_visit.append(attr_value)
                        attrs.append((attr, attr_value))
                    except (AttributeError, ValueError):
                        pass
            except Exception as e:
                messages.append(f"Error collecting attributes of type {type_}: {e}")

            writer.write_unsigned_int(len(attrs))
            for attr, attr_value in attrs:
                writer.write_attribute(attr, attr_value, frequent_attributes)

        # String representation
        if str_repr_len >= 0:
            try:
                str_repr = str(obj)[:str_repr_len]
            except:
                str_repr = "<ERROR on __str__>"
            writer.write_long_string(str_repr)

        progress_reporter.report(done, len(to_visit))

    # Object count -- real value.
    writer.close_unsigned_int_mark(object_count_mark, done)

    progress_reporter.report(done, len(to_visit))
    return result_types, done


class ProgressReporter:
    _GRANULARITY = 1_000

    def __init__(self, path: str) -> None:
        self._f: Optional[IO] = None

        if path:
            try:
                self._f = open(path, "w")
            except OSError:
                self._f = None

        self._started = time.monotonic()

    def report(self, done: int, remain: int) -> None:
        if self._f is None:
            return

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
        if self._f is not None:
            self._f.close()


_shadowed_dict_orig = inspect._shadowed_dict
_check_class_orig = inspect._check_class

try:
    result = _dump_heap()
except:
    print(traceback.format_exc())
    result_error = traceback.format_exc()
finally:
    inspect._shadowed_dict = _shadowed_dict_orig
    inspect._check_class = _check_class_orig
