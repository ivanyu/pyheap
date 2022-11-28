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
import hashlib
import json
import logging
import os
import random
import sys
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path
from typing import Mapping, Set, Dict, List, Tuple, Optional, NamedTuple
from tqdm import tqdm

from pyheap_ui.heap_reader import Heap
from pyheap_ui.heap_types import ObjectDict, ThreadName, Address, JsonObject

LOG = logging.getLogger("heap")
LOG.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)
LOG.addHandler(handler)


class RetainedHeap:
    def __init__(
        self,
        *,
        object_retained_heap: Mapping[Address, int],
        thread_retained_heap: Mapping[ThreadName, int],
    ) -> None:
        self._object_retained_heap = object_retained_heap
        self._thread_retained_heap = thread_retained_heap

    def get_for_object(self, addr: Address) -> Optional[int]:
        return self._object_retained_heap.get(addr)

    def get_for_thread(self, thread_name: ThreadName) -> int:
        return self._thread_retained_heap[thread_name]

    @staticmethod
    def load(dict_: JsonObject) -> RetainedHeap:
        return RetainedHeap(
            object_retained_heap={int(k): v for k, v in dict_["objects"].items()},
            thread_retained_heap=dict(dict_["threads"]),
        )

    def dump(self) -> JsonObject:
        result = {
            "objects": self._object_retained_heap,
            "threads": self._thread_retained_heap,
        }
        return result

    # Needed for testing
    def __eq__(self, o: object) -> bool:
        if not isinstance(o, RetainedHeap):
            return False
        return self._object_retained_heap == o._object_retained_heap


class InboundReferences:
    def __init__(self, objects: ObjectDict) -> None:
        self._inbound_references = self._index_inbound_references(objects)

    @staticmethod
    def _index_inbound_references(
        objects: ObjectDict,
    ) -> Mapping[Address, Set[Address]]:
        LOG.info("Indexing inbound references")
        start = time.monotonic()

        result: Dict[int, Set[int]] = {}

        for obj_address, obj in objects.items():
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
        self,
        *,
        heap: Heap,
        inbound_references: InboundReferences,
        progress_bar: bool = False,
    ) -> None:
        self._calculated = False
        self._heap = heap
        self._inbound_references = inbound_references
        self._progress_bar = progress_bar
        self._subtree_roots = set()
        self._object_retained_heap: Dict[Address, int] = {}
        self._thread_retained_heap: Dict[ThreadName, int] = {}

    def calculate(self) -> RetainedHeap:
        if self._calculated:
            raise ValueError("Retained heap is already calculated")

        self._find_strict_subtrees()
        self._calculate_for_all_objects()
        self._calculate_for_all_threads()
        self._calculated = True
        return RetainedHeap(
            object_retained_heap=self._object_retained_heap,
            thread_retained_heap=self._thread_retained_heap,
        )

    def _find_strict_subtrees(self) -> None:
        front = set()
        for addr, obj in self._heap.objects.items():
            if len(obj.referents) == 0 and len(self._inbound_references[addr]) < 2:
                self._subtree_roots.add(addr)
                self._object_retained_heap[addr] = obj.size
                front.update(self._inbound_references[addr])

        next_front = set()
        while next_front != front:
            for current_addr in front:
                obj = self._heap.objects[current_addr]
                # Skip if it has more than one inbound references.
                if len(self._inbound_references[current_addr]) > 1:
                    continue
                # Consider later if it has children not yet roots.
                if len(obj.referents - self._subtree_roots) > 0:
                    next_front.add(current_addr)
                    continue

                self._subtree_roots.add(current_addr)
                self._object_retained_heap[current_addr] = obj.size + sum(
                    self._object_retained_heap[r] for r in obj.referents
                )
                next_front.update(self._inbound_references[current_addr])

            if front == next_front:
                break

            front = next_front
            next_front = set()

        # TODO Check invariants

    @abc.abstractmethod
    def _calculate_for_all_objects(self) -> None:
        ...

    def _calculate_for_all_threads(self) -> None:
        LOG.info("Calculating retained heap for threads sequentially")
        for thread_to_delete in self._heap.threads:
            inbound_reference_view: Dict[Address, int] = {}
            for obj in thread_to_delete.locals:
                inbound_reference_view[obj] = len(self._inbound_references[obj])
                for thread in self._heap.threads:
                    if thread == thread_to_delete:
                        continue
                    if obj in thread.locals:
                        inbound_reference_view[obj] += 1

            front = list(thread_to_delete.locals)
            self._thread_retained_heap[thread_to_delete.name] = self._retained_heap0(
                inbound_reference_view=inbound_reference_view,
                front=front,
                use_subtrees=False,
            )

    def _retained_heap_for_object(self, *, addr: Address, use_subtrees: bool) -> int:
        inbound_reference_view: Dict[Address, int] = {}
        # Imitate deletion of the initial address.
        inbound_reference_view[addr] = 0
        front = [addr]
        return self._retained_heap0(
            inbound_reference_view=inbound_reference_view,
            front=front,
            use_subtrees=use_subtrees,
        )

    def _retained_heap0(
        self,
        *,
        inbound_reference_view: Dict[Address, int],
        front: List[int],
        use_subtrees: bool,
    ) -> int:
        result = 0
        deleted: Set[Address] = set()

        while True:
            front.sort(key=lambda x: inbound_reference_view[x], reverse=True)

            retained, deletion_happened = self._retained_heap_calculation_iteration(
                front, inbound_reference_view, deleted, use_subtrees
            )
            if not deletion_happened:
                assert retained == 0
                break
            result += retained

        return result

    def _retained_heap_calculation_iteration(
        self,
        front: List[Address],
        inbound_reference_view: Dict[Address, int],
        deleted: Set[Address],
        use_subtrees: bool,
    ) -> Tuple[int, bool]:
        retained = 0
        deletion_happened = False
        for i in range(len(front) - 1, -1, -1):
            current = front[i]

            if inbound_reference_view[current] > 0:
                break
            if current in deleted:
                continue

            front.pop(i)
            deleted.add(current)
            deletion_happened = True

            if use_subtrees and current in self._subtree_roots:
                retained += self._object_retained_heap[current]
            elif current in self._heap.objects:
                retained += self._heap.objects[current].size
                to_be_added_to_front = self._heap.objects[current].referents - deleted
                self._update_inbound_references_view(
                    to_be_added_to_front, inbound_reference_view
                )
                front.extend(to_be_added_to_front)

        return retained, deletion_happened

    def _update_inbound_references_view(
        self,
        to_be_added_to_front: Set[Address],
        inbound_reference_view: Dict[Address, int],
    ) -> None:
        for r in to_be_added_to_front:
            if r not in inbound_reference_view:
                inbound_reference_view[r] = (
                    len(self._inbound_references[r]) - 1
                )  # -1 is newly deleted
            else:
                inbound_reference_view[r] -= 1


class RetainedHeapSequentialCalculator(RetainedHeapCalculator):
    def _calculate_for_all_objects(self) -> None:
        LOG.info("Calculating retained heap for objects sequentially")
        global_start = time.monotonic()

        addresses = list(self._heap.objects.keys())
        random.shuffle(addresses)

        iterator = addresses
        if self._progress_bar:
            iterator = tqdm(
                iterator,
                desc="Calculating retained heap",
                unit="objects",
                total=len(addresses),
            )
        for i, addr in enumerate(iterator):
            self._object_retained_heap[addr] = self._retained_heap_for_object(
                addr=addr, use_subtrees=True
            )

        LOG.info(
            "Calculating retained heap done, took %.2f s",
            time.monotonic() - global_start,
        )


class RetainedHeapParallelCalculator(RetainedHeapCalculator):
    def _calculate_for_all_objects(self) -> None:
        LOG.info("Calculating retained heap for objects in parallel")
        global_start = time.monotonic()

        addresses = list(self._heap.objects.keys())
        random.shuffle(addresses)
        chunk_size = 10_000

        with Pool() as pool:
            iterator = pool.imap_unordered(self._work, addresses, chunksize=chunk_size)
            if self._progress_bar:
                iterator = tqdm(
                    iterator,
                    desc="Calculating retained heap",
                    unit="objects",
                    total=len(addresses),
                )
            for i, (addr, retained_heap_size) in enumerate(iterator):
                self._object_retained_heap[addr] = retained_heap_size

        LOG.info(
            "Calculating retained heap done, took %.2f s",
            time.monotonic() - global_start,
        )

    def _work(self, addr: Address) -> Tuple[Address, int]:
        return addr, self._retained_heap_for_object(addr=addr, use_subtrees=False)


class RetainedHeapCache:
    VERSION = 1  # change when the algorithm changes

    def __init__(self, heap_file_name: str, cache_dir: Optional[str] = None) -> None:
        self._file_path = heap_file_name
        self._cache_dir = cache_dir

    def load_if_cache_exists(self) -> Optional[RetainedHeap]:
        try:
            with open(self._cache_file_name, "r") as f:
                cache_content = json.load(f)
            LOG.info("Loaded retained heap cache %s", self._cache_file_name)
            return RetainedHeap.load(cache_content)
        except FileNotFoundError:
            LOG.info("Retained heap cache %s doesn't exist", self._cache_file_name)
            return None

    def store(self, retained_heap: RetainedHeap) -> None:
        with open(self._cache_file_name, "w") as f:
            json.dump(retained_heap.dump(), f)
        LOG.info("Saved retained heap to cache %s", self._cache_file_name)

    @property
    def _cache_file_name(self) -> str:
        with open(self._file_path, "rb") as f:
            digest = hashlib.sha1(f.read()).hexdigest()

        suffix = f".{digest}.{self.VERSION}.retained_heap"
        if self._cache_dir is None:
            return f"{self._file_path}{suffix}"
        else:
            file_name = Path(self._file_path).name
            return str(Path(self._cache_dir) / f"{file_name}{suffix}")


def provide_retained_heap_with_caching(
    heap_file_name: str, heap: Heap, inbound_references: InboundReferences
) -> RetainedHeap:
    cache_dir = os.getenv("PYHEAP_CACHE_DIR")
    cache = RetainedHeapCache(heap_file_name=heap_file_name, cache_dir=cache_dir)
    retained_heap = cache.load_if_cache_exists()
    if retained_heap is not None:
        return retained_heap

    parallel_retained_heap_calculation = False
    if parallel_retained_heap_calculation:
        calculator = RetainedHeapParallelCalculator(
            heap=heap, inbound_references=inbound_references, progress_bar=True
        )
    else:
        calculator = RetainedHeapSequentialCalculator(
            heap=heap, inbound_references=inbound_references, progress_bar=True
        )
    retained_heap = calculator.calculate()

    cache.store(retained_heap)

    return retained_heap


class AddressWithRetainedHeap(NamedTuple):
    addr: Address
    retained_heap: int


def objects_sorted_by_retained_heap(
    heap: Heap, retained_heap: RetainedHeap
) -> List[AddressWithRetainedHeap]:
    result = [
        AddressWithRetainedHeap(addr, retained_heap.get_for_object(addr) or 0)
        for addr, o in heap.objects.items()
    ]
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def types_sorted_by_retained_heap(
    heap: Heap, retained_heap: RetainedHeap
) -> List[AddressWithRetainedHeap]:
    counter = Counter()
    for obj in heap.objects.values():
        counter[obj.type] += retained_heap.get_for_object(obj.address) or 0
    result = []
    for type_addr, rh in counter.most_common(None):
        result.append(AddressWithRetainedHeap(type_addr, rh))
    return result


def threads_sorted_by_retained_heap(
    heap: Heap, retained_heap: RetainedHeap
) -> List[Tuple[ThreadName, int]]:
    result = [
        (thread.name, retained_heap.get_for_thread(thread.name))
        for thread in heap.threads
    ]
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def total_heap_size(heap: Heap) -> int:
    return sum(obj.size for obj in heap.objects.values())
