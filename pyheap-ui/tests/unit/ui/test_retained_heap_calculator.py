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
from ui.heap import (
    Heap,
    RetainedHeapParallelCalculator,
    RetainedHeapSequentialCalculator,
)


def test_minimal() -> None:
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 20


def test_self_reference() -> None:
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [1],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 20


def test_circular_reference() -> None:
    # 1 -> 2 -> 3
    # ^         |
    # +---------+
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [3],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [1],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 10 + 20 + 30
    assert heap.object_retained_heap(2) == 10 + 20 + 30
    assert heap.object_retained_heap(3) == 10 + 20 + 30


def test_simple_tree() -> None:
    #  /-> 2
    # 1 -> 3
    #  \-> 4
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2, 3, 4],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 10 + 20 + 30 + 40
    assert heap.object_retained_heap(2) == 20
    assert heap.object_retained_heap(3) == 30
    assert heap.object_retained_heap(4) == 40


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
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2, 3, 4],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [5, 6, 7],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [8],
            },
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [9, 10, 11],
            },
            "5": {
                "address": 5,
                "size": 50,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "6": {
                "address": 6,
                "size": 60,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "7": {
                "address": 7,
                "size": 70,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "8": {
                "address": 8,
                "size": 80,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "9": {
                "address": 9,
                "size": 90,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "10": {
                "address": 10,
                "size": 100,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "11": {
                "address": 11,
                "size": 110,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert (
        heap.object_retained_heap(1)
        == 10 + 20 + 30 + 40 + 50 + 60 + 70 + 80 + 90 + 100 + 110
    )
    assert heap.object_retained_heap(2) == 20 + 50 + 60 + 70
    assert heap.object_retained_heap(3) == 30 + 80
    assert heap.object_retained_heap(4) == 40 + 90 + 100 + 110
    assert heap.object_retained_heap(5) == 50
    assert heap.object_retained_heap(6) == 60
    assert heap.object_retained_heap(7) == 70
    assert heap.object_retained_heap(8) == 80
    assert heap.object_retained_heap(9) == 90
    assert heap.object_retained_heap(10) == 100
    assert heap.object_retained_heap(11) == 110


def test_long_branch() -> None:
    # 1 -> 2 -> 3 -> 4 -> 5 -> 6
    #  \-> 7
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2, 7],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [3],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [4],
            },
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [5],
            },
            "5": {
                "address": 5,
                "size": 50,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [6],
            },
            "6": {
                "address": 6,
                "size": 60,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "7": {
                "address": 7,
                "size": 70,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 10 + 20 + 30 + 40 + 50 + 60 + 70
    assert heap.object_retained_heap(2) == 20 + 30 + 40 + 50 + 60
    assert heap.object_retained_heap(3) == 30 + 40 + 50 + 60
    assert heap.object_retained_heap(4) == 40 + 50 + 60
    assert heap.object_retained_heap(5) == 50 + 60
    assert heap.object_retained_heap(6) == 60
    assert heap.object_retained_heap(7) == 70


def test_transitive() -> None:
    #  /-> 2
    # 1    ^
    #  \-> 3
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2, 3],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 10 + 20 + 30
    assert heap.object_retained_heap(2) == 20
    assert heap.object_retained_heap(3) == 30


def test_side_reference() -> None:
    # 1 -> 2 -> 3 -> 4
    #                ^
    #                5
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [3],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [4],
            },
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "5": {
                "address": 5,
                "size": 50,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [4],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 10 + 20 + 30
    assert heap.object_retained_heap(2) == 20 + 30
    assert heap.object_retained_heap(3) == 30
    assert heap.object_retained_heap(4) == 40
    assert heap.object_retained_heap(5) == 50


def test_cross() -> None:
    # 1   2
    # |\ /|
    # | x |
    # v/ \v
    # 3   4
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [3, 4],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [3, 4],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 10
    assert heap.object_retained_heap(2) == 20
    assert heap.object_retained_heap(3) == 30
    assert heap.object_retained_heap(4) == 40


def test_complex_1() -> None:
    # 5 <- 4
    # |    ^    +--> 6 -> 7
    # |    |    |
    # +--> 3 -> 2 -> 1
    #      ^         |
    #      +---------+
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [3],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [1, 6],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2, 4],
            },
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [5],
            },
            "5": {
                "address": 5,
                "size": 50,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [3],
            },
            "6": {
                "address": 6,
                "size": 60,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [7],
            },
            "7": {
                "address": 7,
                "size": 70,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 10
    assert heap.object_retained_heap(2) == 20 + 10 + 60 + 70
    assert heap.object_retained_heap(3) == 30 + (20 + 10 + 60 + 70) + (40 + 50)
    assert heap.object_retained_heap(4) == 40 + 50
    assert heap.object_retained_heap(5) == 50


def test_complex_2() -> None:
    #         3
    #         v
    # 1 ----> 5 <--+
    # |            |
    # +-----> 6 -> 7 <---- 2
    #         v
    #         8
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [5, 6],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [4, 7],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [5],
            },
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2],
            },
            "5": {
                "address": 5,
                "size": 50,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [6],
            },
            "6": {
                "address": 6,
                "size": 60,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [7, 8],
            },
            "7": {
                "address": 7,
                "size": 70,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [5],
            },
            "8": {
                "address": 8,
                "size": 80,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 10
    assert heap.object_retained_heap(2) == 20 + 40
    assert heap.object_retained_heap(3) == 30
    assert heap.object_retained_heap(4) == 40 + 20
    assert heap.object_retained_heap(5) == 50
    assert heap.object_retained_heap(6) == 60 + 80
    assert heap.object_retained_heap(7) == 70
    assert heap.object_retained_heap(8) == 80


def test_complex_3() -> None:
    #           /-> 6
    #          /--> 5
    #         /---> 4
    #         |
    # 1 ----> 2 ---+
    # |            v
    # +-----> 3 -> 7
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2, 3],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [4, 5, 6, 7],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [7],
            },
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "5": {
                "address": 5,
                "size": 50,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "6": {
                "address": 6,
                "size": 60,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "7": {
                "address": 7,
                "size": 70,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 10 + 20 + 30 + 40 + 50 + 60 + 70
    assert heap.object_retained_heap(2) == 20 + 40 + 50 + 60
    assert heap.object_retained_heap(3) == 30
    assert heap.object_retained_heap(4) == 40
    assert heap.object_retained_heap(5) == 50
    assert heap.object_retained_heap(6) == 60
    assert heap.object_retained_heap(7) == 70


def test_forest_minimal() -> None:
    # 1  2  3  4
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 10
    assert heap.object_retained_heap(2) == 20
    assert heap.object_retained_heap(3) == 30
    assert heap.object_retained_heap(4) == 40


def test_forest_simple() -> None:
    # 1 -> 2  3 -> 4
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [4],
            },
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.object_retained_heap(1) == 10 + 20
    assert heap.object_retained_heap(2) == 20
    assert heap.object_retained_heap(3) == 30 + 40
    assert heap.object_retained_heap(4) == 40


def test_thread_minimal() -> None:
    # thread1 -> 1
    # thread2 -> 2
    heap_dict = {
        "threads": [
            {
                "thread_name": "thread1",
                "alive": True,
                "daemon": False,
                "stack_trace": [
                    {
                        "file": None,
                        "lineno": None,
                        "name": None,
                        "locals": {
                            "a": 1,
                        },
                    }
                ],
            },
            {
                "thread_name": "thread2",
                "alive": True,
                "daemon": False,
                "stack_trace": [
                    {
                        "file": None,
                        "lineno": None,
                        "name": None,
                        "locals": {
                            "b": 2,
                        },
                    }
                ],
            },
        ],
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.thread_retained_heap("thread1") == 10
    assert heap.thread_retained_heap("thread2") == 20


def test_thread_simple_multi_frame() -> None:
    # thread1 -> 1 -> 2
    #            |
    #            +--> 3
    #
    # thread2 -> 4 -> 5 -> 6
    #            ^         |
    #            +---------+
    heap_dict = {
        "threads": [
            {
                "thread_name": "thread1",
                "alive": True,
                "daemon": False,
                "stack_trace": [
                    {
                        "file": None,
                        "lineno": None,
                        "name": None,
                        "locals": {
                            "c": 2,
                        },
                    },
                    {
                        "file": None,
                        "lineno": None,
                        "name": None,
                        "locals": {
                            "a": 1,
                            "b": 3,
                        },
                    },
                ],
            },
            {
                "thread_name": "thread2",
                "alive": True,
                "daemon": False,
                "stack_trace": [
                    {
                        "file": None,
                        "lineno": None,
                        "name": None,
                        "locals": {
                            "a": 5,
                            "b": 6,
                        },
                    },
                    {
                        "file": None,
                        "lineno": None,
                        "name": None,
                        "locals": {
                            "a": 4,
                        },
                    },
                ],
            },
        ],
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2, 3],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [5],
            },
            "5": {
                "address": 5,
                "size": 50,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [6],
            },
            "6": {
                "address": 6,
                "size": 60,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [4],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.thread_retained_heap("thread1") == 10 + 20 + 30
    assert heap.thread_retained_heap("thread2") == 40 + 50 + 60


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
    heap_dict = {
        "threads": [
            {
                "thread_name": "thread1",
                "alive": True,
                "daemon": False,
                "stack_trace": [
                    {
                        "file": None,
                        "lineno": None,
                        "name": None,
                        "locals": {
                            "a": 1,
                            "b": 2,
                        },
                    }
                ],
            },
            {
                "thread_name": "thread2",
                "alive": True,
                "daemon": False,
                "stack_trace": [
                    {
                        "file": None,
                        "lineno": None,
                        "name": None,
                        "locals": {
                            "a": 5,
                            "b": 7,
                        },
                    }
                ],
            },
        ],
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [3],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [1, 6],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [2, 4],
            },
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [5],
            },
            "5": {
                "address": 5,
                "size": 50,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [3],
            },
            "6": {
                "address": 6,
                "size": 60,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [7],
            },
            "7": {
                "address": 7,
                "size": 70,
                "type": None,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
    assert heap.thread_retained_heap("thread1") == 10 + 20 + 60 + 70
    assert heap.thread_retained_heap("thread2") == 50 + 70


def test_calculators_equivalent_on_big_generated() -> None:
    objects = {
        str(i): {
            "address": i,
            "size": 20,
            "type": None,
            "str": "",
            "attrs": {},
            "referents": [],
        }
        for i in range(20_000)
    }
    for i in range(20_000):
        if i % 3 == 0:
            objects[str(i)]["referents"] = [i + 1]
    heap_dict = {
        "objects": objects,
        "types": {},
    }
    heap = Heap(heap_dict)
    heap_seq = RetainedHeapSequentialCalculator(heap).calculate()
    heap_par = RetainedHeapParallelCalculator(heap).calculate()
    assert heap_seq == heap_par
    heap.set_retained_heap(heap_seq)
