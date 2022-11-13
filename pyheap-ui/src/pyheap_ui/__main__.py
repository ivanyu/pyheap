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
import argparse
import dataclasses
import mmap
import os
import time
import math
from typing import Optional, Any
from flask import Flask, render_template, abort, request
from flask.json.provider import DefaultJSONProvider

from .heap_types import Heap, JsonObject
from .heap_reader import HeapReader
from .heap import (
    provide_retained_heap_with_caching,
    InboundReferences,
    RetainedHeap,
    objects_sorted_by_retained_heap,
)
from .pagination import Pagination


class AppJSONProvider(DefaultJSONProvider):
    def dumps(self, obj: Any, **kwargs: Any) -> str:
        kwargs["default"] = self.default
        return super().dumps(obj, **kwargs)

    def default(self, o: Any) -> Any:
        if isinstance(o, set):
            return list(o)
        else:
            return super().default(o)


class MyFlask(Flask):
    json_provider_class = AppJSONProvider


app = MyFlask(__name__)

heap: Optional[Heap] = None
inbound_references: Optional[InboundReferences] = None
retained_heap: Optional[RetainedHeap] = None


@app.route("/")
@app.route("/threads")
def threads() -> str:
    return render_template(
        "threads.html",
        tab_threads_active=True,
        threads=heap.threads,
        objects=heap.objects,
        retained_heap=retained_heap,
    )


@app.route("/heap")
def heap() -> str:
    page = request.args.get("page") or 1
    try:
        page = int(page)
    except ValueError:
        page = 1

    page_size = 1000
    object_count = len(heap.objects)
    page_count = int(math.ceil(object_count / page_size))
    pagination = Pagination(page_count, page)
    objects = objects_sorted_by_retained_heap(heap, retained_heap)[
        (page - 1) * page_size : page * page_size
    ]
    total_heap_size = sum((o.size for o in heap.objects.values()))
    return render_template(
        "heap.html",
        tab_heap_active=True,
        pagination=pagination,
        objects=objects,
        types=heap.types,
        total_heap_size=total_heap_size,
        object_count=object_count,
        with_str_repr=heap.header.flags.with_str_repr,
    )


@app.route("/objects/<int:address>")
def objects(address: int) -> str:
    if address not in heap.objects:
        abort(404)

    obj = heap.objects[address]

    well_known_type = next(
        (k for k, v in heap.header.well_known_types.items() if v == obj.type), None
    )

    return render_template(
        "objects.html",
        tab_object_active=True,
        address=address,
        obj=obj,
        type=heap.types[obj.type],
        objects=heap.objects,
        types=heap.types,
        retained_heap=retained_heap,
        well_known_type=well_known_type,
    )


@app.route("/api/objects/", methods=["POST"])
def objects_batch() -> JsonObject:
    if "addresses" not in request.json:
        abort(400)
    addresses = request.json["addresses"]
    result = []
    for address in addresses:
        if address not in heap.objects:
            result.append(None)
        else:
            obj = heap.objects[address]
            obj_json = dataclasses.asdict(obj)
            obj_json["type"] = heap.types[obj.type]
            obj_json["inbound_references"] = list(inbound_references[address])
            obj_json["address"] = address
            obj_json["str_repr"] = obj.str_repr
            obj_json["retained_heap"] = retained_heap.get_for_object(address)
            result.append(obj_json)
    return {"objects": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Heap viewer UI.", allow_abbrev=False)
    parser.add_argument("--file", "-f", type=str, required=True, help="heap file name")
    args = parser.parse_args()

    start = time.monotonic()
    app.logger.info("Loading file %s", args.file)
    with open(args.file, "rb") as f:
        mm = mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)
        reader = HeapReader(mm)
        heap = reader.read()
    app.logger.info("Loading file finished in %.2f seconds", time.monotonic() - start)

    inbound_references = InboundReferences(heap.objects)
    retained_heap = provide_retained_heap_with_caching(
        args.file, heap, inbound_references
    )

    host = os.environ.get("FLASK_SERVER_NAME")
    app.run(debug=True, host=host)
