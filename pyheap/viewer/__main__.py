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
import gzip
import json
import time
import math
from typing import Optional, List

from flask import Flask, render_template, abort, request

from pyheap.heap import Heap, provide_retained_heap_with_caching, JsonObject

app = Flask(__name__)
heap: Optional[Heap] = None


@app.route("/")
@app.route("/threads")
def threads() -> str:
    return render_template(
        "threads.html",
        tab_threads_active=True,
        threads=list(heap.threads.values()),
        objects=heap.objects,
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
    objects = heap.objects_sorted_by_retained_heap()[
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
    )


@app.route("/objects/<address_str>")
def objects(address_str: str) -> str:
    address = -1
    try:
        address = int(address_str)
    except ValueError:
        abort(400)
    if address not in heap.objects:
        abort(404)

    obj = heap.objects[address]
    return render_template(
        "objects.html",
        tab_object_active=True,
        obj=obj,
        type=heap.types[obj.type],
        retained_heap=heap.object_retained_heap(address),
    )


@app.route("/api/objects/", methods=["POST"])
def objects_batch() -> JsonObject:
    if "addresses" not in request.json:
        abort(400)
    addresses = request.json["addresses"]
    result = []
    for address in addresses:
        if address not in heap.objects:
            abort(404)
        obj = heap.objects[address]
        obj_json = obj.to_json()
        obj_json["type"] = heap.types[obj.type]
        obj_json["inbound_references"] = list(heap.inbound_references[address])
        result.append(obj_json)
    return {"objects": result}


@app.route("/api/objects/<address>")
def api_object_get(address: str) -> JsonObject:
    try:
        address_int = int(address)
    except ValueError:
        abort(400)
    if address_int not in heap.objects:
        abort(404)

    obj = heap.objects[address_int]
    result = obj.to_json()
    result["type"] = heap.types[obj.type]
    result["inbound_references"] = list(heap.inbound_references[address])
    return result


class Pagination:
    _WINDOW = 3
    _MIN_PAGES_TO_COLLAPSE = 15

    def __init__(self, total_pages: int, page: int) -> None:
        if total_pages < 1:
            raise ValueError(f"Invalid total_pages: {total_pages}")
        if page < 1 or page > total_pages:
            raise ValueError(f"Invalid page number: {page}")
        self._total_pages = total_pages
        self._page = page

    @property
    def total_pages(self) -> int:
        return self._total_pages

    @property
    def page(self) -> int:
        return self._page

    @property
    def layout(self) -> List[Optional[int]]:
        result = [None] + list(range(1, self._total_pages + 1))

        if self._total_pages < self._MIN_PAGES_TO_COLLAPSE:
            return result[1:]

        right_distance = self._total_pages - self._page
        if right_distance > self._WINDOW * 2:
            del result[self._page + self._WINDOW : self._total_pages - self._WINDOW + 1]
            result.insert(self._page + self._WINDOW, None)

        left_distance = self._page - 1
        if left_distance > self._WINDOW * 2:
            del result[1 + self._WINDOW : self._page - self._WINDOW + 1]
            result.insert(1 + self._WINDOW, None)

        return result[1:]

    @property
    def prev_enabled(self) -> bool:
        return self._page > 1

    @property
    def next_enabled(self) -> bool:
        return self._page < self._total_pages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Heap viewer.", allow_abbrev=False)
    parser.add_argument("--file", "-f", type=str, required=True, help="heap file name")
    args = parser.parse_args()

    start = time.monotonic()
    app.logger.info("Loading file %s", args.file)
    open_func = gzip.open if args.file.endswith(".gz") else open
    with open_func(args.file, "r") as f:
        heap_dict = json.load(f)
    app.logger.info("Loading file finished in %.2f seconds", time.monotonic() - start)

    heap = Heap(heap_dict)
    heap.set_retained_heap(provide_retained_heap_with_caching(args.file, heap))

    app.run(debug=True)
