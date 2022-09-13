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
import sys
import threading
import time
import traceback
from typing import List, Any, NamedTuple, Dict, Tuple

"""
This module is executed in the context of the inferior.
"""


class _PyObject(NamedTuple):
    obj: Any
    referents: List[Any]


def dump_heap(heap_file: str) -> str:
    try:
        return _dump_heap0(heap_file)
    except:
        import traceback

        print(traceback.format_exc())
        return traceback.format_exc()


def _dump_heap0(heap_file: str) -> str:
    start = time.monotonic()
    visited = 0

    gc_tracked_objects = _get_gc_tracked_objects()

    messages = []
    threads, locals_ = _get_threads_and_locals(messages)

    all_objects = _all_objects(gc_tracked_objects, locals_)

    open_func = gzip.open if heap_file.endswith(".gz") else open
    with open_func(heap_file, "wb") as f:
        f.write("{\n".encode("utf-8"))

        f.write('  "threads": '.encode("utf-8"))
        f.write(json.dumps(threads, indent=2).encode("utf-8"))
        f.write(",\n".encode("utf-8"))

        types = {}

        f.write('  "objects": {\n'.encode("utf-8"))
        first_iteration = True
        for obj, referents in all_objects:
            visited += 1

            type_ = type(obj)
            types[str(id(type_))] = type_.__name__

            if not first_iteration:
                f.write(",\n".encode("utf-8"))
            else:
                first_iteration = False

            try:
                str_ = str(obj)[:1000]
            except:
                str_ = "<ERROR on __str__>"
            obj_dict = {
                "address": id(obj),
                "type": type_.__name__,
                "size": sys.getsizeof(obj),
                "str": str_,
                "referents": [id(r) for r in referents],
            }
            f.write(f'    "{id(obj)}": '.encode("utf-8"))
            f.write(json.dumps(obj_dict).encode("utf-8"))
        f.write("  \n},\n".encode("utf-8"))

        f.write('  "types": '.encode("utf-8"))
        f.write(json.dumps(types, indent=2).encode("utf-8"))

        f.write("\n}".encode("utf-8"))

    result = f"Heap dumped to {heap_file}. Visited {visited} objects. Took {(time.monotonic() - start):.3f} seconds."
    if messages:
        result += "\n" + "\n".join(messages) + "\n"
    return result


def _get_gc_tracked_objects() -> List[Any]:
    invisible_objects = set()
    invisible_objects.add(id(invisible_objects))
    invisible_objects.add(id(sys.modules["dumper"]))
    invisible_objects.add(id(sys.modules["dumper"].__name__))
    invisible_objects.add(id(sys.modules["dumper"].__dict__))
    invisible_objects.add(id(sys.modules["dumper"].__doc__))
    invisible_objects.add(id(sys.modules["dumper"].__loader__))
    invisible_objects.add(id(sys.modules["dumper"].__spec__))
    invisible_objects.add(id(sys.modules["dumper"].__package__))
    invisible_objects.add(id(sys.modules["dumper"].__file__))
    invisible_objects.add(id(_PyObject))
    invisible_objects.add(id(dump_heap))
    invisible_objects.add(id(_dump_heap0))
    invisible_objects.add(id(_all_objects))

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


def _all_objects(gc_tracked_objects: List[Any], locals_: List[Any]) -> List[_PyObject]:
    seen_ids = set()
    to_visit = []
    to_visit.extend(gc_tracked_objects)
    to_visit.extend(locals_)
    result = []

    while len(to_visit) > 0:
        obj = to_visit.pop()
        obj_id = id(obj)

        if obj_id in seen_ids:
            continue

        seen_ids.add(obj_id)
        # Self-references here are fine.
        referents = gc.get_referents(obj)
        obj = _PyObject(obj=obj, referents=referents)
        result.append(obj)
        to_visit.extend(referents)

    return result
