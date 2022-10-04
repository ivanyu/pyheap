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
import dataclasses
import hashlib
import json
import logging
import random
import sys
import time
from dataclasses import dataclass
from functools import cached_property
from multiprocessing import Pool
from typing import Mapping, Any, Set, Dict, Collection, List, Tuple, Optional

LOG = logging.getLogger("heap")
LOG.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)
LOG.addHandler(handler)

Address = int
ThreadName = str
JsonObject = Mapping[str, Any]


class RetainedHeap:
    def __init__(
        self,
        *,
        object_retained_heap: Mapping[Address, int],
        thread_retained_heap: Mapping[ThreadName, int],
    ) -> None:
        self._object_retained_heap = object_retained_heap
        self._thread_retained_heap = thread_retained_heap

    def get_for_object(self, addr: Address) -> int:
        return self._object_retained_heap[addr]

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


@dataclass
class PyObject:
    address: int
    type: int
    size: int
    str_: str
    attrs: Dict[str, Address]
    referents: Set[Address]

    @staticmethod
    def from_dict(obj_dict: Dict[str, Any]) -> PyObject:
        return PyObject(
            address=obj_dict["address"],
            type=obj_dict["type"],
            size=obj_dict["size"],
            str_=obj_dict["str"],
            attrs=obj_dict["attrs"],
            referents=set(obj_dict["referents"]),
        )

    def to_json(self) -> JsonObject:
        r = dataclasses.asdict(self)
        r["referents"] = list(r["referents"])
        r["str"] = r["str_"]
        del r["str_"]
        return r


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
    def __init__(self, objects: Mapping[Address, PyObject]) -> None:
        self._inbound_references = self._index_inbound_references(objects)

    @staticmethod
    def _index_inbound_references(
        objects: Mapping[Address, PyObject]
    ) -> Mapping[Address, Set[Address]]:
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
    def __init__(self, heap: Heap) -> None:
        self._calculated = False
        self._heap = heap
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
        for obj in self._heap.objects.values():
            if (
                len(obj.referents) == 0
                and len(self._heap.inbound_references[obj.address]) < 2
            ):
                self._subtree_roots.add(obj.address)
                self._object_retained_heap[obj.address] = obj.size
                front.update(self._heap.inbound_references[obj.address])

        next_front = set()
        while next_front != front:
            for current in front:
                obj = self._heap.objects[current]
                # Skip if it has more than one inbound references.
                if len(self._heap.inbound_references[obj.address]) > 1:
                    continue
                # Consider later if it has children not yet roots.
                if len(obj.referents - self._subtree_roots) > 0:
                    next_front.add(current)
                    continue

                self._subtree_roots.add(obj.address)
                self._object_retained_heap[obj.address] = obj.size + sum(
                    self._object_retained_heap[r] for r in obj.referents
                )
                next_front.update(self._heap.inbound_references[obj.address])

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
        for thread_name, thread_obj in self._heap.threads.items():
            self._thread_retained_heap[thread_name] = self._retained_heap0(
                addrs=thread_obj.locals, use_subtrees=False
            )

    def _retained_heap0(self, *, addrs: Collection[Address], use_subtrees: bool) -> int:
        result = 0
        deleted: Set[Address] = set()

        inbound_reference_view: Dict[Address, Set[Address]] = {}
        # Imitate deletion of the initial addresses.
        for a in addrs:
            inbound_reference_view[a] = set()

        front = list(addrs)

        while True:
            front.sort(key=lambda x: len(inbound_reference_view[x]), reverse=True)

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
        inbound_reference_view: Dict[Address, Set[Address]],
        deleted: Set[Address],
        use_subtrees: bool,
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

            if use_subtrees and current in self._subtree_roots:
                retained += self._object_retained_heap[current]
            else:
                retained += self._heap.objects[current].size
                to_be_added_to_front = self._heap.objects[current].referents - deleted
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
                inbound_reference_view[r] = self._heap.inbound_references[r] - deleted
            else:
                # This extra check is not masking some mistake in the retained heap algorithm.
                # Normally we "delete" only one root object. It refers to some other objects,
                # which don't have the inbound reference view defined yet. They are processed
                # by the other branch of this if-else. In this case, the check is not needed.
                # However, when we calculate a thread's retained heap, we "delete" multiple root objects,
                # which may refer to one another. Hence, this extra check.
                if current in inbound_reference_view[r]:
                    inbound_reference_view[r].remove(current)


class RetainedHeapSequentialCalculator(RetainedHeapCalculator):
    def _calculate_for_all_objects(self) -> None:
        LOG.info("Calculating retained heap for objects sequentially")
        global_start = time.monotonic()

        total = len(self._heap.objects)
        step_size = 10_000
        eta = ETA(total)

        addresses = list(self._heap.objects.keys())
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
            self._object_retained_heap[addr] = self._retained_heap0(
                addrs=[addr], use_subtrees=True
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
                self._object_retained_heap[addr] = retained_heap_size

        LOG.info(
            "Calculating retained heap done, took %.2f s",
            time.monotonic() - global_start,
        )

    def _work(self, addr: Address) -> Tuple[Address, int]:
        return addr, self._retained_heap0(addrs=[addr], use_subtrees=False)


class RetainedHeapCache:
    VERSION = 1  # change when the algorithm changes

    def __init__(self, heap_file_name: str) -> None:
        self._file_name = heap_file_name

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
        with open(self._file_name, "rb") as f:
            digest = hashlib.sha1(f.read()).hexdigest()
        return f"{self._file_name}.{digest}.{self.VERSION}.retained_heap"


@dataclass
class Frame:
    file: str
    lineno: int
    name: str
    locals: Dict[str, Address]

    @staticmethod
    def from_dict(frame_dict: JsonObject) -> Frame:
        return Frame(
            file=frame_dict["file"],
            lineno=frame_dict["lineno"],
            name=frame_dict["name"],
            locals=frame_dict["locals"],
        )


@dataclass
class PyThread:
    thread_name: ThreadName
    alive: bool
    daemon: bool
    stack_trace: List[Frame]

    @property
    def locals(self) -> Set[Address]:
        result = set()
        for frame in self.stack_trace:
            result.update(frame.locals.values())
        return result

    @staticmethod
    def from_dict(thread_dict: JsonObject) -> PyThread:
        return PyThread(
            thread_name=thread_dict["thread_name"],
            alive=thread_dict["alive"],
            daemon=thread_dict["daemon"],
            stack_trace=[Frame.from_dict(d) for d in thread_dict["stack_trace"]],
        )


class Heap:
    def __init__(self, heap_dict: JsonObject) -> None:
        LOG.info("Heap dump contains %d objects", len(heap_dict["objects"]))
        LOG.info("Heap dump contains %d threads", len(heap_dict.get("threads", [])))

        self._threads: Dict[ThreadName, PyThread] = {}
        for d in heap_dict.get("threads", []):
            thread_obj = PyThread.from_dict(d)
            self._threads[thread_obj.thread_name] = thread_obj

        # Filter unknown objects from referents.
        filtered_objects = 0
        for obj in heap_dict["objects"].values():
            for i in range(len(obj["referents"]) - 1, -1, -1):
                r = obj["referents"][i]
                if str(r) not in heap_dict["objects"]:
                    filtered_objects += 1
                    obj["referents"].pop(i)
        LOG.info("%d unknown objects filtered", filtered_objects)

        self._objects: Mapping[Address, PyObject] = {
            int(addr): PyObject.from_dict(obj_dict)
            for addr, obj_dict in heap_dict["objects"].items()
        }
        self._types: Mapping[Address, str] = {
            int(addr): obj for addr, obj in heap_dict["types"].items()
        }
        self._inbound_references = InboundReferences(self._objects)
        self._retained_heap: Optional[RetainedHeap] = None

    @property
    def threads(self) -> Mapping[ThreadName, PyThread]:
        return self._threads

    @property
    def objects(self) -> Mapping[Address, PyObject]:
        return self._objects

    @property
    def types(self) -> Mapping[Address, str]:
        return self._types

    @property
    def inbound_references(self) -> InboundReferences:
        return self._inbound_references

    def set_retained_heap(self, retained_heap: RetainedHeap) -> None:
        self._retained_heap = retained_heap

    def object_retained_heap(self, addr: Address) -> int:
        return self._retained_heap.get_for_object(addr)

    def thread_retained_heap(self, thread_name: ThreadName) -> int:
        return self._retained_heap.get_for_thread(thread_name)

    def objects_sorted_by_retained_heap(self) -> List[Tuple[PyObject, int]]:
        result = [
            (o, self._retained_heap.get_for_object(o.address))
            for o in self._objects.values()
        ]
        result.sort(key=lambda x: x[1], reverse=True)
        return result

    def threads_sorted_by_retained_heap(self) -> List[Tuple[ThreadName, int]]:
        result = [
            (thread_name, self._retained_heap.get_for_thread(thread_name))
            for thread_name in self._threads.keys()
        ]
        result.sort(key=lambda x: x[1], reverse=True)
        return result

    @cached_property
    def total_heap_size(self) -> int:
        return sum(obj.size for obj in self._objects.values())


def provide_retained_heap_with_caching(heap_file_name: str, heap: Heap) -> RetainedHeap:
    cache = RetainedHeapCache(heap_file_name)
    retained_heap = cache.load_if_cache_exists()
    if retained_heap is not None:
        return retained_heap

    parallel_retained_heap_calculation = True
    if parallel_retained_heap_calculation:
        calculator = RetainedHeapParallelCalculator(heap)
    else:
        calculator = RetainedHeapSequentialCalculator(heap)
    retained_heap = calculator.calculate()

    cache.store(retained_heap)

    return retained_heap
