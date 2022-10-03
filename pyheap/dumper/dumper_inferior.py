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
import gzip
import json
from contextlib import closing
from json.encoder import py_encode_basestring
import sys
import threading
import time
import traceback
from typing import List, Any, Dict, Tuple
import inspect
import io
from functools import lru_cache

"""
This module is executed in the context of the inferior.
"""

# This file has some optimizations to reduce the number of object allocations and boost speed,
# which results in more obscure code. Please, when you try to improve the code,
# make sure you're making the right trade-off with the performance.


# Inputs:
heap_file: str
str_len: int
progress_file: str

# Output:
result = None


def _dump_heap() -> str:
    global_start = time.monotonic()
    visited = 0

    gc_tracked_objects = _get_gc_tracked_objects()

    messages = []
    threads, locals_ = _get_threads_and_locals(messages)

    local_start = time.monotonic()
    with closing(ProgressReporter(progress_file)) as progress_reporter:
        object_jsons, types = _all_objects_jsons_and_types(
            gc_tracked_objects, locals_, progress_reporter
        )
    all_objects_duration = time.monotonic() - local_start

    local_start = time.monotonic()
    open_func = gzip.open if heap_file.endswith(".gz") else open
    with open_func(heap_file, "wb") as f:
        f.write("{\n".encode("utf-8"))

        f.write('  "metadata": '.encode("utf-8"))
        from datetime import datetime, timezone

        local_tz = datetime.now(timezone.utc).astimezone().tzinfo
        metadata = {"version": 1, "created_at": datetime.now(tz=local_tz).isoformat()}
        f.write(json.dumps(metadata, indent=2).encode("utf-8"))
        f.write(",\n".encode("utf-8"))

        f.write('  "threads": '.encode("utf-8"))
        f.write(json.dumps(threads, indent=2).encode("utf-8"))
        f.write(",\n".encode("utf-8"))

        f.write('  "objects": {\n'.encode("utf-8"))
        first_iteration = True
        for obj_str in object_jsons:
            visited += 1

            if not first_iteration:
                f.write(",\n".encode("utf-8"))
            else:
                first_iteration = False

            f.write(obj_str.encode("utf-8"))
        f.write("\n  },\n".encode("utf-8"))

        f.write('  "types": '.encode("utf-8"))
        f.write(json.dumps(types, indent=2).encode("utf-8"))

        f.write("\n}".encode("utf-8"))
    writing_duration = time.monotonic() - local_start

    result = (
        f"Heap dumped to {heap_file}. "
        + f"Visited {visited} objects. "
        + f"Took {(time.monotonic() - global_start):.3f} seconds total, "
        + f"{all_objects_duration:.3f} seconds collecting objects, "
        + f"{writing_duration:.3f} seconds writing file."
    )
    if messages:
        result += "\n" + "\n".join(messages) + "\n"
    return result


def _get_gc_tracked_objects() -> List[Any]:
    invisible_objects = set()
    invisible_objects.add(id(invisible_objects))
    invisible_objects.add(id(heap_file))
    invisible_objects.add(id(str_len))
    invisible_objects.add(id(result))
    invisible_objects.add(id(_dump_heap))
    invisible_objects.add(id(_all_objects_jsons_and_types))
    invisible_objects.add(id(_get_threads_and_locals))
    invisible_objects.add(id(_shadowed_dict_orig))
    invisible_objects.add(id(_check_class_orig))
    invisible_objects.add(id(ProgressReporter))

    return [o for o in gc.get_objects() if id(o) not in invisible_objects]


def _get_threads_and_locals(
    messages: List[str],
) -> Tuple[List[Dict[str, List[dict]]], List[Any]]:
    current_frames = sys._current_frames()
    all_locals: List[Any] = []
    stack_traces: List[Dict[str, List[dict]]] = []
    for thread in threading.enumerate():
        thread_dict = {
            "thread_name": thread.name,
            "alive": thread.is_alive(),
            "daemon": thread.daemon,
            "stack_trace": None,
        }
        stack_traces.append(thread_dict)

        current_thread_frame = current_frames.get(thread.ident)
        if current_thread_frame is None:
            messages.append(f"WARNING - stack for thread {thread.name} not found")
            continue

        thread_dict["stack_trace"] = []
        for frame, lineno in traceback.walk_stack(current_thread_frame):
            # Skip the dumper frames, which may be on top of normal frames.
            if frame.f_code.co_filename == __file__:
                continue

            all_locals.extend(frame.f_locals.values())
            thread_dict["stack_trace"].append(
                {
                    "file": frame.f_code.co_filename,
                    "lineno": lineno,
                    "name": frame.f_code.co_name,
                    "locals": {
                        loc_name: id(loc_value)
                        for loc_name, loc_value in frame.f_locals.items()
                    },
                }
            )
    return stack_traces, all_locals


def _all_objects_jsons_and_types(
    gc_tracked_objects: List[Any],
    locals_: List[Any],
    progress_reporter: ProgressReporter,
) -> Tuple[List[str], Dict[str, str]]:
    seen_ids = set()
    to_visit = []
    to_visit.extend(gc_tracked_objects)
    to_visit.extend(locals_)
    result_objects = []
    result_types = {}

    inspect._shadowed_dict = lru_cache(maxsize=None)(_shadowed_dict_orig)
    inspect._check_class = lru_cache(maxsize=None)(_check_class_orig)
    invisible_objects = set()
    invisible_objects.add(id(inspect._shadowed_dict))
    invisible_objects.add(id(inspect._check_class))

    done = 0
    progress_reporter.report(done, len(to_visit))

    while len(to_visit) > 0:
        obj = to_visit.pop()
        obj_id = id(obj)

        if obj_id in seen_ids or obj_id in invisible_objects:
            continue
        seen_ids.add(obj_id)
        done += 1

        type_ = type(obj)
        result_types[str(id(type_))] = type_.__name__

        # Self-references here are fine.
        referents = gc.get_referents(obj)
        to_visit.extend(referents)

        try:
            str_ = str(obj)
            if str_len > -1:
                str_ = str_[:str_len]
        except:
            str_ = "<ERROR on __str__>"

        # Format:
        # {
        #     "address": id(obj),
        #     "type": id(type_),
        #     "size": sys.getsizeof(obj),
        #     "str": str_,
        #     "attrs": {"aaa": id(aaa_value), ...},
        #     "referents": [id(r) for r in referents],
        # }

        s = io.StringIO()
        s.write(f'    "{id(obj)}": ')
        s.write("{")
        s.write(f'"address": {id(obj)}, ')
        s.write(f'"type": {id(type_)}, ')
        s.write(f'"size": {sys.getsizeof(obj)}, ')
        s.write(f'"str": {py_encode_basestring(str_)}, ')
        s.write('"attrs": {')
        first_iteration = True
        for attr in dir(obj):
            try:
                attr_value = inspect.getattr_static(obj, attr)

                if first_iteration:
                    first_iteration = False
                else:
                    s.write(", ")
                s.write(f'"{attr}": {id(attr_value)}')

                to_visit.append(attr_value)
            except (AttributeError, ValueError):
                pass
        s.write("},")

        s.write('"referents": [')
        s.write(", ".join(str(id(r)) for r in referents))
        s.write("]")

        s.write("}")

        result_objects.append(s.getvalue())
        progress_reporter.report(done, len(to_visit))

    progress_reporter.report(done, len(to_visit))
    return result_objects, result_types


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
