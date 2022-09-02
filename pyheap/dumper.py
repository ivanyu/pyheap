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
import sys
import time
from typing import List, Any, NamedTuple

"""
This module is executed in the context of the inferior.
"""


class _PyObject(NamedTuple):
    obj: Any
    referents: List[Any]


def dump_heap(heap_file: str) -> str:
    try:
        return _dump_heap0(heap_file)
    except Exception:
        import traceback

        print(traceback.format_exc())
        return traceback.format_exc()


def _dump_heap0(heap_file: str) -> str:
    start = time.monotonic()
    visited = 0
    all_objects = _all_objects()

    with open(heap_file, "w") as f:
        f.write("{\n")

        types = {}

        f.write('  "objects": {\n')
        first_iteration = True
        for obj, referents in all_objects:
            visited += 1

            type_ = type(obj)
            types[str(id(type_))] = type_.__name__

            if not first_iteration:
                f.write(",\n")
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
            f.write(f'    "{id(obj)}": ')
            f.write(json.dumps(obj_dict))
        f.write("  \n},\n")

        f.write('  "types": ')
        f.write(json.dumps(types, indent=2))

        f.write("\n}")

    return f"Heap dumped to {heap_file}. Visited {visited} objects. Took {(time.monotonic() - start):.3f} seconds."


def _all_objects() -> List[_PyObject]:
    invisible_objects = set()
    invisible_objects.add(id(invisible_objects))
    invisible_objects.add(id(sys.modules["dumper"]))
    invisible_objects.add(id(sys.modules["dumper"].__name__))
    invisible_objects.add(id(sys.modules["dumper"].__dict__))
    invisible_objects.add(id(sys.modules["dumper"].__annotations__))
    invisible_objects.add(id(sys.modules["dumper"].__doc__))
    invisible_objects.add(id(sys.modules["dumper"].__loader__))
    invisible_objects.add(id(sys.modules["dumper"].__spec__))
    invisible_objects.add(id(sys.modules["dumper"].__package__))
    invisible_objects.add(id(sys.modules["dumper"].__file__))
    invisible_objects.add(id(_PyObject))
    invisible_objects.add(id(dump_heap))
    invisible_objects.add(id(_dump_heap0))
    invisible_objects.add(id(_all_objects))

    seen_ids = set()
    invisible_objects.add(id(seen_ids))

    to_visit = []
    invisible_objects.add(id(to_visit))

    gc_objects = gc.get_objects()
    invisible_objects.add(id(gc_objects))

    to_visit.extend(gc_objects)

    result = []
    invisible_objects.add(id(result))

    while len(to_visit) > 0:
        obj = to_visit.pop()
        obj_id = id(obj)
        invisible_objects.add(id(obj_id))

        if obj_id in invisible_objects or obj_id in seen_ids:
            continue

        seen_ids.add(obj_id)

        # Self-references here are fine.
        referents = gc.get_referents(obj)
        invisible_objects.add(id(referents))

        obj = _PyObject(obj=obj, referents=referents)
        invisible_objects.add(id(obj))

        result.append(obj)
        to_visit.extend(referents)

    return result
