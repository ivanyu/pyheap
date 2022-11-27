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
from unittest.mock import ANY

from pyheap_ui.heap import (
    RetainedHeap,
    objects_sorted_by_retained_heap,
    AddressWithRetainedHeap,
    types_sorted_by_retained_heap,
)
from pyheap_ui.heap_types import Heap, HeapObject


def test_objects_sorted_by_retained_heap() -> None:
    heap = Heap(
        header=None,
        threads=[],
        objects={
            1: HeapObject(
                address=1, type=None, size=None, referents=None, content=None
            ),
            2: HeapObject(
                address=2, type=None, size=None, referents=None, content=None
            ),
        },
        types={},
    )
    retained_heap = RetainedHeap(
        object_retained_heap={
            1: 123,
            2: 777,
        },
        thread_retained_heap={},
    )
    assert objects_sorted_by_retained_heap(heap, retained_heap) == [
        AddressWithRetainedHeap(addr=2, retained_heap=777),
        AddressWithRetainedHeap(addr=1, retained_heap=123),
    ]


def test_objects_sorted_by_retained_heap_non_existent() -> None:
    heap = Heap(
        header=None,
        threads=[],
        objects={
            1: HeapObject(address=1, type=1, size=None, referents=None, content=None)
        },
        types={},
    )
    retained_heap = RetainedHeap(object_retained_heap={}, thread_retained_heap={})
    assert objects_sorted_by_retained_heap(heap, retained_heap) == [
        AddressWithRetainedHeap(addr=1, retained_heap=0)
    ]


def test_types_sorted_by_retained_heap() -> None:
    heap = Heap(
        header=None,
        threads=[],
        objects={
            1: HeapObject(address=1, type=4, size=None, referents=None, content=None),
            2: HeapObject(address=2, type=5, size=None, referents=None, content=None),
            3: HeapObject(address=3, type=4, size=None, referents=None, content=None),
            4: HeapObject(address=4, type=10, size=None, referents=None, content=None),
            5: HeapObject(address=5, type=10, size=None, referents=None, content=None),
            10: HeapObject(
                address=10, type=10, size=None, referents=None, content=None
            ),
        },
        types={},
    )
    retained_heap = RetainedHeap(
        object_retained_heap={
            1: 123,
            2: 777,
            3: 12,
            4: 2,
            5: 3,
            10: 0,
        },
        thread_retained_heap={},
    )
    assert types_sorted_by_retained_heap(heap, retained_heap) == [
        AddressWithRetainedHeap(addr=5, retained_heap=777),
        AddressWithRetainedHeap(addr=4, retained_heap=123 + 12),
        AddressWithRetainedHeap(addr=10, retained_heap=2 + 3),
    ]
