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

import abc
import argparse
import random
import json
import gzip
import sys
import time
import logging
from dataclasses import dataclass
from functools import cached_property
from multiprocessing import Pool
from typing import Any, Dict, List, Set, Tuple, Mapping, Optional

Address = int

LOG = logging.getLogger()
LOG.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)
LOG.addHandler(handler)


@dataclass
class PyObject:
    address: int
    type: str
    size: int
    str_: str
    referents: Set[int]

    @staticmethod
    def from_dict(obj_dict: Dict[str, Any]) -> PyObject:
        return PyObject(
            address=obj_dict["address"],
            type=obj_dict["type"],
            size=obj_dict["size"],
            str_=obj_dict["str"],
            referents=set(obj_dict["referents"]),
        )


class ETA:
    def __init__(self, total: int) -> None:
        self._remain = total
        self._previous_avgs = []

    def make_step(self, size: int, duration: float) -> None:
        self._remain -= size
        self._previous_avgs.append(duration / size)

    def eta(self) -> float:
        avg_duration = sum(self._previous_avgs) / len(self._previous_avgs)
        return avg_duration * max(0, self._remain)


class InboundReferences:
    def __init__(self, objects: Dict[Address, PyObject]) -> None:
        self._inbound_references = self._index_inbound_references(objects)

    @staticmethod
    def _index_inbound_references(
        objects: Dict[Address, PyObject]
    ) -> Dict[Address, Set[Address]]:
        LOG.info("Indexing inbound references")
        start = time.monotonic()

        result: Dict[int, Set[int]] = {}

        for obj in objects.values():
            obj_address = obj.address
            if obj_address not in result:
                result[obj_address] = set()

            for referent_addr in obj.referents:
                if referent_addr not in result:
                    result[referent_addr] = set()
                if obj_address not in result[referent_addr]:
                    result[referent_addr].add(obj_address)

        LOG.info("Inbound references indexed in %.2f seconds", time.monotonic() - start)
        return result

    def __getitem__(self, addr: Address) -> Set[Address]:
        return self._inbound_references[addr]


class RetainedHeapCalculator:
    def __init__(
        self, objects: Mapping[Address, PyObject], inbound_references: InboundReferences
    ) -> None:
        self._objects = objects
        self._inbound_references = inbound_references
        self._subtree_roots = set()
        self._retained_heap: Dict[Address, int] = {}

    def calculate(self) -> Mapping[Address, int]:
        self._find_strict_subtrees()
        self._calculate_for_all0()
        return self._retained_heap

    @abc.abstractmethod
    def _calculate_for_all0(self) -> None:
        ...

    def _find_strict_subtrees(self) -> None:
        front = set()
        for obj in self._objects.values():
            if (
                len(obj.referents) == 0
                and len(self._inbound_references[obj.address]) < 2
            ):
                self._subtree_roots.add(obj.address)
                self._retained_heap[obj.address] = obj.size
                front.update(self._inbound_references[obj.address])

        next_front = set()
        while next_front != front:
            for current in front:
                obj = self._objects[current]
                # Skip if it has more than one inbound references.
                if len(self._inbound_references[obj.address]) > 1:
                    continue
                # Consider later if it has children not yet roots.
                if len(obj.referents - self._subtree_roots) > 0:
                    next_front.add(current)
                    continue

                self._subtree_roots.add(obj.address)
                self._retained_heap[obj.address] = obj.size + sum(
                    self._retained_heap[r] for r in obj.referents
                )
                next_front.update(self._inbound_references[obj.address])

            if front == next_front:
                break

            front = next_front
            next_front = set()

        # TODO Check invariants

    def _retained_heap0(self, addr: Address) -> int:
        result = 0
        deleted: Set[Address] = set()

        inbound_reference_view: Dict[Address, Set[Address]] = {}
        # Imitate deletion of the initial address.
        inbound_reference_view[addr] = set()

        front = [addr]

        while True:
            front.sort(key=lambda x: len(inbound_reference_view[x]), reverse=True)

            retained, deletion_happened = self._retained_heap_calculation_iteration(
                front, inbound_reference_view, deleted
            )
            if not deletion_happened:
                assert retained == 0
                break
            result += retained

        return result

    def _retained_heap_calculation_iteration(
        self,
        front: List[Address],
        inbound_reference_view: Dict[Address, Set[Address]],
        deleted: Set[Address],
    ) -> Tuple[int, bool]:
        retained = 0
        deletion_happened = False
        for i in range(len(front) - 1, -1, -1):
            current = front[i]

            if inbound_reference_view[current]:
                break
            if current in deleted:
                continue

            front.pop(i)
            deleted.add(current)
            deletion_happened = True

            if current in self._subtree_roots:
                retained += self._retained_heap[current]
            else:
                retained += self._objects[current].size
                to_be_added_to_front = self._objects[current].referents - deleted
                self._update_inbound_references_view(
                    current, deleted, to_be_added_to_front, inbound_reference_view
                )
                front.extend(to_be_added_to_front)

        return retained, deletion_happened

    def _update_inbound_references_view(
        self,
        current: Address,
        deleted: Set[Address],
        to_be_added_to_front: Set[Address],
        inbound_reference_view: Dict[Address, Set[Address]],
    ) -> None:
        for r in to_be_added_to_front:
            if r not in inbound_reference_view:
                inbound_reference_view[r] = self._inbound_references[r] - deleted
            else:
                inbound_reference_view[r].remove(current)


class RetainedHeapSequentialCalculator(RetainedHeapCalculator):
    def _calculate_for_all0(self) -> None:
        LOG.info("Calculating retained heap sequentially")
        global_start = time.monotonic()

        total = len(self._objects)
        step_size = 10_000
        eta = ETA(total)

        addresses = list(self._objects.keys())
        random.shuffle(addresses)

        start = time.monotonic()
        for i, addr in enumerate(addresses):
            if i % step_size == 0 and i > 0:
                step_duration = time.monotonic() - start
                eta.make_step(step_size, step_duration)
                start = time.monotonic()
                LOG.info(
                    "Done %r / %r, took %.2f s, ETA %.2f s",
                    i,
                    total,
                    step_duration,
                    eta.eta(),
                )
            self._retained_heap[addr] = self._retained_heap0(addr)

        LOG.info(
            "Calculating retained heap done, took %.2f s",
            time.monotonic() - global_start,
        )


class RetainedHeapParallelCalculator(RetainedHeapCalculator):
    def _calculate_for_all0(self) -> None:
        LOG.info("Calculating retained heap in parallel")
        global_start = time.monotonic()

        addresses = list(self._objects.keys())
        total = len(addresses)
        random.shuffle(addresses)
        chunk_size = 10_000
        eta = ETA(total)

        with Pool() as pool:
            r = pool.imap_unordered(self._work, addresses, chunksize=chunk_size)
            start = time.monotonic()
            for i, (addr, retained_heap_size) in enumerate(r):
                if i % chunk_size == 0 and i > 0:
                    step_duration = time.monotonic() - start
                    eta.make_step(chunk_size, step_duration)
                    start = time.monotonic()
                    LOG.info(
                        "Done %r / %r, took %.2f s, ETA %.2f s",
                        i,
                        total,
                        step_duration,
                        eta.eta(),
                    )
                self._retained_heap[addr] = retained_heap_size

        LOG.info(
            "Calculating retained heap done, took %.2f s",
            time.monotonic() - global_start,
        )

    def _work(self, addr: Address) -> Tuple[Address, int]:
        return addr, self._retained_heap0(addr)


class Heap:
    def __init__(self, heap_dict: Dict[str, Any]) -> None:
        LOG.info("Heap dump contains %d objects", len(heap_dict["objects"]))

        # Filter unknown objects from referents.
        filtered_objects = 0
        for obj in heap_dict["objects"].values():
            for i in range(len(obj["referents"]) - 1, -1, -1):
                r = obj["referents"][i]
                if str(r) not in heap_dict["objects"]:
                    filtered_objects += 1
                    obj["referents"].pop(i)
        LOG.info("%d unknown objects filtered", filtered_objects)

        self._objects: Dict[Address, PyObject] = {
            int(addr): PyObject.from_dict(obj_dict)
            for addr, obj_dict in heap_dict["objects"].items()
        }
        self._types: Dict[Address, str] = {
            int(addr): obj for addr, obj in heap_dict["types"].items()
        }
        self._inbound_references = InboundReferences(self._objects)
        self._retained_heap: Optional[Mapping[Address, int]] = None

    def calculate_retained_heap(self) -> None:
        parallel = True
        if parallel:
            calculator = RetainedHeapParallelCalculator(
                self._objects, self._inbound_references
            )
        else:
            calculator = RetainedHeapSequentialCalculator(
                self._objects, self._inbound_references
            )
        self._retained_heap = calculator.calculate()

    def retained_heap(self, addr: Address) -> int:
        return self._retained_heap[addr]

    def objects_sorted_by_retained_heap(self) -> List[Tuple[PyObject, int]]:
        addrs = [(o, self._retained_heap[o.address]) for o in self._objects.values()]
        addrs.sort(key=lambda x: x[1], reverse=True)
        return addrs

    @cached_property
    def total_heap_size(self) -> int:
        return sum(obj.size for obj in self._objects.values())


def retained_heap(args: argparse.Namespace) -> None:
    start = time.monotonic()
    LOG.info("Loading file %s", args.file)
    open_func = gzip.open if args.file.endswith(".gz") else open
    with open_func(args.file, "r") as f:
        heap_dict = json.load(f)
    LOG.info("Loading file finished in %.2f seconds", time.monotonic() - start)
    heap = Heap(heap_dict)
    heap.calculate_retained_heap()

    row_format = "{:<15}   {:<15} {:>18}   {:<100}"
    print(row_format.format("Address", "Object type", "Retained heap size", "str"))
    for obj, retained_heap in heap.objects_sorted_by_retained_heap()[: args.top_n]:
        print(row_format.format(obj.address, obj.type, retained_heap, obj.str_[:100]))

    print(f"Total heap size: {heap.total_heap_size} bytes")


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
