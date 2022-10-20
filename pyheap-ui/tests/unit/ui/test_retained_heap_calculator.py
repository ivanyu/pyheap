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
from pyheap_ui.heap import (
    RetainedHeapParallelCalculator,
    RetainedHeapSequentialCalculator,
    InboundReferences,
)
from pyheap_ui.heap_reader import Heap, HeapObject
from pyheap_ui.heap_types import HeapHeader, HeapThread, HeapThreadFrame, HeapFlags


_HEADER = HeapHeader(0, "", HeapFlags(True))


def test_minimal() -> None:
    objects = {
        1: HeapObject(type=0, size=20, referents=set()),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 20


def test_self_reference() -> None:
    objects = {
        1: HeapObject(type=0, size=20, referents={1}),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 20


def test_circular_reference() -> None:
    # 1 -> 2 -> 3
    # ^         |
    # +---------+
    objects = {
        1: HeapObject(type=0, size=10, referents={2}),
        2: HeapObject(type=0, size=20, referents={3}),
        3: HeapObject(type=0, size=30, referents={1}),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 10 + 20 + 30
    assert heap_seq.get_for_object(2) == 10 + 20 + 30
    assert heap_seq.get_for_object(3) == 10 + 20 + 30


def test_simple_tree() -> None:
    #  /-> 2
    # 1 -> 3
    #  \-> 4
    objects = {
        1: HeapObject(type=0, size=10, referents={2, 3, 4}),
        2: HeapObject(type=0, size=20, referents=set()),
        3: HeapObject(type=0, size=30, referents=set()),
        4: HeapObject(type=0, size=40, referents=set()),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 10 + 20 + 30 + 40
    assert heap_seq.get_for_object(2) == 20
    assert heap_seq.get_for_object(3) == 30
    assert heap_seq.get_for_object(4) == 40


def test_multi_level_tree() -> None:
    #         /--> 5
    #        /---> 6
    #       /----> 7
    #  /-> 2
    # 1 -> 3 ----> 8
    #  \-> 4
    #       \----> 9
    #        \---> 10
    #         \--> 11
    objects = {
        1: HeapObject(type=0, size=10, referents={2, 3, 4}),
        2: HeapObject(type=0, size=20, referents={5, 6, 7}),
        3: HeapObject(type=0, size=30, referents={8}),
        4: HeapObject(type=0, size=40, referents={9, 10, 11}),
        5: HeapObject(type=0, size=50, referents=set()),
        6: HeapObject(type=0, size=60, referents=set()),
        7: HeapObject(type=0, size=70, referents=set()),
        8: HeapObject(type=0, size=80, referents=set()),
        9: HeapObject(type=0, size=90, referents=set()),
        10: HeapObject(type=0, size=100, referents=set()),
        11: HeapObject(type=0, size=110, referents=set()),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert (
        heap_seq.get_for_object(1)
        == 10 + 20 + 30 + 40 + 50 + 60 + 70 + 80 + 90 + 100 + 110
    )
    assert heap_seq.get_for_object(2) == 20 + 50 + 60 + 70
    assert heap_seq.get_for_object(3) == 30 + 80
    assert heap_seq.get_for_object(4) == 40 + 90 + 100 + 110
    assert heap_seq.get_for_object(5) == 50
    assert heap_seq.get_for_object(6) == 60
    assert heap_seq.get_for_object(7) == 70
    assert heap_seq.get_for_object(8) == 80
    assert heap_seq.get_for_object(9) == 90
    assert heap_seq.get_for_object(10) == 100
    assert heap_seq.get_for_object(11) == 110


def test_long_branch() -> None:
    # 1 -> 2 -> 3 -> 4 -> 5 -> 6
    #  \-> 7
    objects = {
        1: HeapObject(type=0, size=10, referents={2, 7}),
        2: HeapObject(type=0, size=20, referents={3}),
        3: HeapObject(type=0, size=30, referents={4}),
        4: HeapObject(type=0, size=40, referents={5}),
        5: HeapObject(type=0, size=50, referents={6}),
        6: HeapObject(type=0, size=60, referents=set()),
        7: HeapObject(type=0, size=70, referents=set()),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 10 + 20 + 30 + 40 + 50 + 60 + 70
    assert heap_seq.get_for_object(2) == 20 + 30 + 40 + 50 + 60
    assert heap_seq.get_for_object(3) == 30 + 40 + 50 + 60
    assert heap_seq.get_for_object(4) == 40 + 50 + 60
    assert heap_seq.get_for_object(5) == 50 + 60
    assert heap_seq.get_for_object(6) == 60
    assert heap_seq.get_for_object(7) == 70


def test_transitive() -> None:
    #  /-> 2
    # 1    ^
    #  \-> 3
    objects = {
        1: HeapObject(type=0, size=10, referents={2, 3}),
        2: HeapObject(type=0, size=20, referents=set()),
        3: HeapObject(type=0, size=30, referents={2}),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 10 + 20 + 30
    assert heap_seq.get_for_object(2) == 20
    assert heap_seq.get_for_object(3) == 30


def test_side_reference() -> None:
    # 1 -> 2 -> 3 -> 4
    #                ^
    #                5
    objects = {
        1: HeapObject(type=0, size=10, referents={2}),
        2: HeapObject(type=0, size=20, referents={3}),
        3: HeapObject(type=0, size=30, referents={4}),
        4: HeapObject(type=0, size=40, referents=set()),
        5: HeapObject(type=0, size=50, referents={4}),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 10 + 20 + 30
    assert heap_seq.get_for_object(2) == 20 + 30
    assert heap_seq.get_for_object(3) == 30
    assert heap_seq.get_for_object(4) == 40
    assert heap_seq.get_for_object(5) == 50


def test_cross() -> None:
    # 1   2
    # |\ /|
    # | x |
    # v/ \v
    # 3   4
    objects = {
        1: HeapObject(type=0, size=10, referents={3, 4}),
        2: HeapObject(type=0, size=20, referents={3, 4}),
        3: HeapObject(type=0, size=30, referents=set()),
        4: HeapObject(type=0, size=40, referents=set()),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 10
    assert heap_seq.get_for_object(2) == 20
    assert heap_seq.get_for_object(3) == 30
    assert heap_seq.get_for_object(4) == 40


def test_complex_1() -> None:
    # 5 <- 4
    # |    ^    +--> 6 -> 7
    # |    |    |
    # +--> 3 -> 2 -> 1
    #      ^         |
    #      +---------+
    objects = {
        1: HeapObject(type=0, size=10, referents={3}),
        2: HeapObject(type=0, size=20, referents={1, 6}),
        3: HeapObject(type=0, size=30, referents={2, 4}),
        4: HeapObject(type=0, size=40, referents={5}),
        5: HeapObject(type=0, size=50, referents={3}),
        6: HeapObject(type=0, size=60, referents={7}),
        7: HeapObject(type=0, size=70, referents=set()),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 10
    assert heap_seq.get_for_object(2) == 20 + 10 + 60 + 70
    assert heap_seq.get_for_object(3) == 30 + (20 + 10 + 60 + 70) + (40 + 50)
    assert heap_seq.get_for_object(4) == 40 + 50
    assert heap_seq.get_for_object(5) == 50


def test_complex_2() -> None:
    #         3
    #         v
    # 1 ----> 5 <--+
    # |            |
    # +-----> 6 -> 7 <---- 2
    #         v
    #         8
    objects = {
        1: HeapObject(type=0, size=10, referents={5, 6}),
        2: HeapObject(type=0, size=20, referents={4, 7}),
        3: HeapObject(type=0, size=30, referents={5}),
        4: HeapObject(type=0, size=40, referents={2}),
        5: HeapObject(type=0, size=50, referents={6}),
        6: HeapObject(type=0, size=60, referents={7, 8}),
        7: HeapObject(type=0, size=70, referents={5}),
        8: HeapObject(type=0, size=80, referents=set()),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 10
    assert heap_seq.get_for_object(2) == 20 + 40
    assert heap_seq.get_for_object(3) == 30
    assert heap_seq.get_for_object(4) == 40 + 20
    assert heap_seq.get_for_object(5) == 50
    assert heap_seq.get_for_object(6) == 60 + 80
    assert heap_seq.get_for_object(7) == 70
    assert heap_seq.get_for_object(8) == 80


def test_complex_3() -> None:
    #           /-> 6
    #          /--> 5
    #         /---> 4
    #         |
    # 1 ----> 2 ---+
    # |            v
    # +-----> 3 -> 7
    objects = {
        1: HeapObject(type=0, size=10, referents={2, 3}),
        2: HeapObject(type=0, size=20, referents={4, 5, 6, 7}),
        3: HeapObject(type=0, size=30, referents={7}),
        4: HeapObject(type=0, size=40, referents=set()),
        5: HeapObject(type=0, size=50, referents=set()),
        6: HeapObject(type=0, size=60, referents=set()),
        7: HeapObject(type=0, size=70, referents=set()),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 10 + 20 + 30 + 40 + 50 + 60 + 70
    assert heap_seq.get_for_object(2) == 20 + 40 + 50 + 60
    assert heap_seq.get_for_object(3) == 30
    assert heap_seq.get_for_object(4) == 40
    assert heap_seq.get_for_object(5) == 50
    assert heap_seq.get_for_object(6) == 60
    assert heap_seq.get_for_object(7) == 70


def test_forest_minimal() -> None:
    # 1  2  3  4
    objects = {
        1: HeapObject(type=0, size=10, referents=set()),
        2: HeapObject(type=0, size=20, referents=set()),
        3: HeapObject(type=0, size=30, referents=set()),
        4: HeapObject(type=0, size=40, referents=set()),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 10
    assert heap_seq.get_for_object(2) == 20
    assert heap_seq.get_for_object(3) == 30
    assert heap_seq.get_for_object(4) == 40


def test_forest_simple() -> None:
    # 1 -> 2  3 -> 4
    objects = {
        1: HeapObject(type=0, size=10, referents={2}),
        2: HeapObject(type=0, size=20, referents=set()),
        3: HeapObject(type=0, size=30, referents={4}),
        4: HeapObject(type=0, size=40, referents=set()),
    }
    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_object(1) == 10 + 20
    assert heap_seq.get_for_object(2) == 20
    assert heap_seq.get_for_object(3) == 30 + 40
    assert heap_seq.get_for_object(4) == 40


def test_thread_minimal() -> None:
    # thread1 -> 1
    # thread2 -> 2
    objects = {
        1: HeapObject(type=0, size=10, referents=set()),
        2: HeapObject(type=0, size=20, referents=set()),
    }

    threads = [
        HeapThread(
            name="thread1",
            is_alive=True,
            is_daemon=False,
            stack_trace=[HeapThreadFrame("", 0, "", locals={"a": 1})],
        ),
        HeapThread(
            name="thread2",
            is_alive=True,
            is_daemon=False,
            stack_trace=[HeapThreadFrame("", 0, "", locals={"b": 2})],
        ),
    ]

    heap = Heap(_HEADER, threads=threads, objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_thread("thread1") == 10
    assert heap_seq.get_for_thread("thread2") == 20


def test_thread_simple_multi_frame() -> None:
    # thread1 -> 1 -> 2
    #            |
    #            +--> 3
    #
    # thread2 -> 4 -> 5 -> 6
    #            ^         |
    #            +---------+
    objects = {
        1: HeapObject(type=0, size=10, referents={2, 3}),
        2: HeapObject(type=0, size=20, referents=set()),
        3: HeapObject(type=0, size=30, referents=set()),
        4: HeapObject(type=0, size=40, referents={5}),
        5: HeapObject(type=0, size=50, referents={6}),
        6: HeapObject(type=0, size=60, referents={4}),
    }

    threads = [
        HeapThread(
            name="thread1",
            is_alive=True,
            is_daemon=False,
            stack_trace=[
                HeapThreadFrame("", 0, "", locals={"c": 2}),
                HeapThreadFrame("", 0, "", locals={"a": 1, "b": 3}),
            ],
        ),
        HeapThread(
            name="thread2",
            is_alive=True,
            is_daemon=False,
            stack_trace=[
                HeapThreadFrame("", 0, "", locals={"a": 5, "b": 6}),
                HeapThreadFrame("", 0, "", locals={"a": 4}),
            ],
        ),
    ]

    heap = Heap(_HEADER, threads=threads, objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_thread("thread1") == 10 + 20 + 30
    assert heap_seq.get_for_thread("thread2") == 40 + 50 + 60


def test_thread_complex_1() -> None:
    # 5 <- 4
    # |    ^    +--> 6 -> 7
    # |    |    |
    # +--> 3 -> 2 -> 1
    #      ^         |
    #      +---------+
    # thread 1 --> 1
    #          \-> 2
    # thread 2 --> 5
    #          \-> 7
    objects = {
        1: HeapObject(type=0, size=10, referents={3}),
        2: HeapObject(type=0, size=20, referents={1, 6}),
        3: HeapObject(type=0, size=30, referents={2, 4}),
        4: HeapObject(type=0, size=40, referents={5}),
        5: HeapObject(type=0, size=50, referents={3}),
        6: HeapObject(type=0, size=60, referents={7}),
        7: HeapObject(type=0, size=70, referents=set()),
    }

    threads = [
        HeapThread(
            name="thread1",
            is_alive=True,
            is_daemon=False,
            stack_trace=[HeapThreadFrame("", 0, "", locals={"a": 1, "b": 2})],
        ),
        HeapThread(
            name="thread2",
            is_alive=True,
            is_daemon=False,
            stack_trace=[HeapThreadFrame("", 0, "", locals={"a": 5, "b": 7})],
        ),
    ]

    heap = Heap(_HEADER, threads=threads, objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
    assert heap_seq.get_for_thread("thread1") == 10 + 20 + 60 + 70
    assert heap_seq.get_for_thread("thread2") == 50 + 70


def test_calculators_equivalent_on_big_generated() -> None:
    objects = {}
    for i in range(20_000):
        objects[i] = HeapObject(type=0, size=20, referents=set())
        if i % 3 == 0:
            objects[i].referents = {i + 1}

    heap = Heap(_HEADER, threads=[], objects=objects, types={})
    inbound_references = InboundReferences(objects)
    heap_seq = RetainedHeapSequentialCalculator(heap, inbound_references).calculate()
    heap_par = RetainedHeapParallelCalculator(heap, inbound_references).calculate()
    assert heap_seq == heap_par
