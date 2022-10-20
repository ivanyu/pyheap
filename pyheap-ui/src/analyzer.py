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

import argparse
import json
import mmap
import shutil
import sys
import time
import logging

from pyheap_ui.heap import (
    provide_retained_heap_with_caching,
    InboundReferences,
    objects_sorted_by_retained_heap,
    threads_sorted_by_retained_heap,
    total_heap_size,
)
from pyheap_ui.heap_reader import HeapReader

LOG = logging.getLogger("analyzer")
LOG.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)
LOG.addHandler(handler)


def retained_heap(args: argparse.Namespace) -> None:
    start = time.monotonic()
    LOG.info("Loading file %s", args.file)

    with open(args.file, "rb") as f:
        mm = mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)
        reader = HeapReader(mm)
        heap = reader.read()

    LOG.info("Loading file finished in %.2f seconds", time.monotonic() - start)

    inbound_references = InboundReferences(heap.objects)
    retained_heap = provide_retained_heap_with_caching(
        args.file, heap, inbound_references
    )

    terminal_columns, _ = shutil.get_terminal_size()

    print("Retained heap for objects:")
    before_str_repr = "{:<15} | {:<15} | {:>18} | "
    room_for_str = terminal_columns - len(before_str_repr.format("", "", ""))
    row_format = before_str_repr + "{:<" + str(room_for_str) + "}"
    print(
        row_format.format(
            "Address", "Object type", "Retained heap size", "String representation"
        )
    )
    print("-" * terminal_columns)
    for addr, obj, obj_retained_heap in objects_sorted_by_retained_heap(
        heap, retained_heap
    )[: args.top_n]:
        type_ = heap.types[obj.type]
        print(
            row_format.format(
                addr, type_, obj_retained_heap, obj.str_repr[:room_for_str]
            )
        )

    print()
    print("Retained heap for threads:")
    row_format = "{:<50} | {:>18}"
    print(row_format.format("Thread", "Retained heap size"))
    print("-" * 71)
    for thread_name, thread_retained_heap in threads_sorted_by_retained_heap(
        heap, retained_heap
    ):
        print(row_format.format(thread_name, thread_retained_heap))

    print()
    print(f"Total heap size: {total_heap_size(heap)} bytes")


parser = argparse.ArgumentParser(description="Analyzes heap files.", allow_abbrev=False)
subparsers = parser.add_subparsers(help="command")
subparsers.required = True

parser_retained_heap = subparsers.add_parser(
    "retained-heap", help="show retained heap statistics"
)
parser_retained_heap.add_argument(
    "--file", "-f", type=str, required=True, help="heap file name"
)
parser_retained_heap.add_argument(
    "--top-n", "-n", type=int, default=100, help="number of top objects to show"
)
parser_retained_heap.set_defaults(func=retained_heap)


if __name__ == "__main__":
    args = parser.parse_args()
    args.func(args)
