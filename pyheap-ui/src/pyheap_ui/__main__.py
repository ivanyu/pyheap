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
import functools
import logging
import mmap
import os
import time
import math
from typing import Optional, Any, Dict, List
from flask import Flask, render_template, abort, request
from flask.json.provider import DefaultJSONProvider
from .heap_types import Heap, JsonObject, Address, HeapObject
from .heap_reader import HeapReader
from .heap import (
    provide_retained_heap_with_caching,
    InboundReferences,
    RetainedHeap,
    objects_sorted_by_retained_heap,
    AddressWithRetainedHeap,
    types_sorted_by_retained_heap,
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
app.logger.setLevel(logging.INFO)
if app.logger.handlers:
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
    app.logger.handlers[0].setFormatter(formatter)

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
def heap_by_object() -> str:
    page = request.args.get("page") or 1
    try:
        page = int(page)
    except ValueError:
        page = 1

    search_type = request.args.get("search_type") or ""
    search_str_repr = request.args.get("search_str_repr") or ""

    found_objects = _find_objects_for_heap_view(search_type, search_str_repr)

    page_size = 1000
    object_count = len(found_objects)
    page_count = int(math.ceil(object_count / page_size))
    pagination = Pagination(page_count, page)
    objects_to_render = found_objects[(page - 1) * page_size : page * page_size]
    total_heap_size = sum((o.size for o in heap.objects.values()))
    return render_template(
        "heap_by_object.html",
        tab_heap_active=True,
        pagination=pagination,
        objects_to_render=objects_to_render,
        objects=heap.objects,
        types=heap.types,
        total_heap_size=total_heap_size,
        object_count=len(heap.objects),
        with_str_repr=heap.header.flags.with_str_repr,
        search_type=search_type,
    )


def _find_objects_for_heap_view(
    search_type: str, search_str_repr: str
) -> List[AddressWithRetainedHeap]:
    result = objects_sorted_by_retained_heap(heap, retained_heap)

    if search_type:
        result = [
            addr_with_rh
            for addr_with_rh in result
            if heap.types.get(heap.objects[addr_with_rh.addr].type) == search_type
        ]

    if search_str_repr:
        result = [
            addr_with_rh
            for addr_with_rh in result
            if search_str_repr in (heap.objects[addr_with_rh.addr].str_repr or "")
        ]

    return result


@app.route("/heap-by-type")
def heap_by_type() -> str:
    page = request.args.get("page") or 1
    try:
        page = int(page)
    except ValueError:
        page = 1

    search_type = request.args.get("search_type") or ""

    found_types = _find_types_for_heap_view(search_type)

    page_size = 1000
    type_count = len(found_types)
    page_count = int(math.ceil(type_count / page_size))
    pagination = Pagination(page_count, page)
    types_to_render = found_types[(page - 1) * page_size : page * page_size]
    total_heap_size = sum((o.size for o in heap.objects.values()))
    return render_template(
        "heap_by_type.html",
        tab_heap_active=True,
        pagination=pagination,
        types_to_render=types_to_render,
        types=heap.types,
        total_heap_size=total_heap_size,
        object_count=len(heap.objects),
        with_str_repr=heap.header.flags.with_str_repr,
        search_type=search_type,
    )


def _find_types_for_heap_view(search_type: str) -> List[AddressWithRetainedHeap]:
    result = types_sorted_by_retained_heap(heap, retained_heap)

    if search_type:
        result = [
            type_addr_with_rh
            for type_addr_with_rh in result
            if heap.types.get(type_addr_with_rh.addr) == search_type
        ]

    return result


@app.route("/objects/<int:address>")
@app.route("/objects/<int:address>/attributes")
def objects_attributes(address: int) -> str:
    if address not in heap.objects:
        abort(404)

    obj = heap.objects[address]

    return render_template(
        "objects_attributes.html",
        tab_object_active=True,
        object_tabs=_object_tabs(obj, "attributes"),
        address=address,
        obj=obj,
        retained_heap=retained_heap,
        type_address=obj.type,
        type=heap.types[obj.type],
        types=heap.types,
        objects=heap.objects,
    )


@app.route("/objects/<int:address>/elements")
def objects_elements(address: int) -> str:
    if address not in heap.objects:
        abort(404)
    obj = heap.objects[address]

    if obj.type not in well_known_container_types():
        abort(404)

    return render_template(
        "objects_elements.html",
        tab_object_active=True,
        object_tabs=_object_tabs(obj, "elements"),
        address=address,
        obj=obj,
        retained_heap=retained_heap,
        type_address=obj.type,
        type=heap.types[obj.type],
        types=heap.types,
        objects=heap.objects,
        well_known_container_type=well_known_container_types().get(obj.type),
    )


@app.route("/objects/<int:address>/instances")
def objects_instances(address: int) -> str:
    if address not in heap.objects:
        abort(404)
    obj = heap.objects[address]

    is_type_type = obj.type == heap.header.well_known_types.get("type")
    if not is_type_type:
        abort(404)

    type_instances = None
    if is_type_type:
        type_instances = [
            addr for addr, obj in heap.objects.items() if obj.type == address
        ]

    return render_template(
        "objects_instances.html",
        tab_object_active=True,
        object_tabs=_object_tabs(obj, "instances"),
        address=address,
        obj=obj,
        retained_heap=retained_heap,
        type_address=obj.type,
        type=heap.types[obj.type],
        types=heap.types,
        objects=heap.objects,
        type_instances=type_instances,
    )


@app.route("/objects/<int:address>/referents")
def objects_referents(address: int) -> str:
    if address not in heap.objects:
        abort(404)
    obj = heap.objects[address]

    return render_template(
        "objects_referents.html",
        tab_object_active=True,
        object_tabs=_object_tabs(obj, "referents"),
        address=address,
        obj=obj,
        retained_heap=retained_heap,
        type_address=obj.type,
        type=heap.types[obj.type],
    )


@app.route("/objects/<int:address>/inbound-references")
def objects_inbound_references(address: int) -> str:
    if address not in heap.objects:
        abort(404)
    obj = heap.objects[address]

    return render_template(
        "objects_inbound_references.html",
        tab_object_active=True,
        object_tabs=_object_tabs(obj, "inbound_references"),
        address=address,
        obj=obj,
        retained_heap=retained_heap,
        type_address=obj.type,
        type=heap.types[obj.type],
    )


def _object_tabs(obj: HeapObject, current_active: str) -> Dict[str, bool]:
    object_tabs = {"attributes": False}

    if obj.type in well_known_container_types():
        object_tabs["elements"] = False

    is_type_type = obj.type == heap.header.well_known_types.get("type")
    if is_type_type:
        object_tabs["instances"] = False

    object_tabs["referents"] = False
    object_tabs["inbound_references"] = False

    if current_active not in object_tabs:
        raise ValueError(f"{current_active} is not available for {obj}")
    else:
        object_tabs[current_active] = True
    return object_tabs


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


@app.template_filter()
def big_number(size: int) -> str:
    size_str = str(size)
    max_chunk_size = 3
    chunks = []
    for i in range(len(size_str), 0, -max_chunk_size):
        left = max(0, i - max_chunk_size)
        chunks.append(size_str[left:i])
    chunks.reverse()
    return "&nbsp;".join(chunks)


@functools.lru_cache
def well_known_container_types() -> Dict[Address, str]:
    return {
        heap.header.well_known_types["dict"]: "dict",
        heap.header.well_known_types["list"]: "list",
        heap.header.well_known_types["set"]: "set",
        heap.header.well_known_types["tuple"]: "tuple",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Heap viewer UI.", allow_abbrev=False)
    parser.add_argument("--file", "-f", type=str, required=True, help="heap file name")
    args = parser.parse_args()

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start = time.monotonic()
        app.logger.info("Loading file %s", args.file)
        with open(args.file, "rb") as f:
            mm = mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)
            reader = HeapReader(mm, object_progress_bar=True)
            heap = reader.read()
        app.logger.info(
            "Loading file finished in %.2f seconds", time.monotonic() - start
        )

        inbound_references = InboundReferences(heap.objects)
        retained_heap = provide_retained_heap_with_caching(
            args.file, heap, inbound_references
        )

    host = os.environ.get("FLASK_SERVER_NAME")
    app.run(debug=True, host=host)
