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
from typing import Callable

import pytest

from pyheap.analyzer import (
    Heap,
    RetainedHeapParallelCalculator,
    RetainedHeapSequentialCalculator,
    RetainedHeapCalculator,
)


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_minimal(calculator_factory: Callable[[Heap], RetainedHeapCalculator]) -> None:
    heap_dict = {
        "objects": {
            "1": {"address": 1, "size": 20, "type": None, "str": "", "referents": []},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 20


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_self_reference(
    calculator_factory: Callable[[Heap], RetainedHeapCalculator]
) -> None:
    heap_dict = {
        "objects": {
            "1": {"address": 1, "size": 20, "type": None, "str": "", "referents": [1]},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 20


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_circular_reference(
    calculator_factory: Callable[[Heap], RetainedHeapCalculator]
) -> None:
    # 1 -> 2 -> 3
    # ^         |
    # +---------+
    heap_dict = {
        "objects": {
            "1": {"address": 1, "size": 10, "type": None, "str": "", "referents": [2]},
            "2": {"address": 2, "size": 20, "type": None, "str": "", "referents": [3]},
            "3": {"address": 3, "size": 30, "type": None, "str": "", "referents": [1]},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 10 + 20 + 30
    assert heap.retained_heap(2) == 10 + 20 + 30
    assert heap.retained_heap(3) == 10 + 20 + 30


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_simple_tree(
    calculator_factory: Callable[[Heap], RetainedHeapCalculator]
) -> None:
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
                "referents": [2, 3, 4],
            },
            "2": {"address": 2, "size": 20, "type": None, "str": "", "referents": []},
            "3": {"address": 3, "size": 30, "type": None, "str": "", "referents": []},
            "4": {"address": 4, "size": 40, "type": None, "str": "", "referents": []},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 10 + 20 + 30 + 40
    assert heap.retained_heap(2) == 20
    assert heap.retained_heap(3) == 30
    assert heap.retained_heap(4) == 40


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_multi_level_tree(
    calculator_factory: Callable[[Heap], RetainedHeapCalculator]
) -> None:
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
                "referents": [2, 3, 4],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "referents": [5, 6, 7],
            },
            "3": {"address": 3, "size": 30, "type": None, "str": "", "referents": [8]},
            "4": {
                "address": 4,
                "size": 40,
                "type": None,
                "str": "",
                "referents": [9, 10, 11],
            },
            "5": {"address": 5, "size": 50, "type": None, "str": "", "referents": []},
            "6": {"address": 6, "size": 60, "type": None, "str": "", "referents": []},
            "7": {"address": 7, "size": 70, "type": None, "str": "", "referents": []},
            "8": {"address": 8, "size": 80, "type": None, "str": "", "referents": []},
            "9": {"address": 9, "size": 90, "type": None, "str": "", "referents": []},
            "10": {
                "address": 10,
                "size": 100,
                "type": None,
                "str": "",
                "referents": [],
            },
            "11": {
                "address": 11,
                "size": 110,
                "type": None,
                "str": "",
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert (
        heap.retained_heap(1) == 10 + 20 + 30 + 40 + 50 + 60 + 70 + 80 + 90 + 100 + 110
    )
    assert heap.retained_heap(2) == 20 + 50 + 60 + 70
    assert heap.retained_heap(3) == 30 + 80
    assert heap.retained_heap(4) == 40 + 90 + 100 + 110
    assert heap.retained_heap(5) == 50
    assert heap.retained_heap(6) == 60
    assert heap.retained_heap(7) == 70
    assert heap.retained_heap(8) == 80
    assert heap.retained_heap(9) == 90
    assert heap.retained_heap(10) == 100
    assert heap.retained_heap(11) == 110


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_long_branch(
    calculator_factory: Callable[[Heap], RetainedHeapCalculator]
) -> None:
    # 1 -> 2 -> 3 -> 4 -> 5 -> 6
    #  \-> 7
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "size": 10,
                "type": None,
                "str": "",
                "referents": [2, 7],
            },
            "2": {"address": 2, "size": 20, "type": None, "str": "", "referents": [3]},
            "3": {"address": 3, "size": 30, "type": None, "str": "", "referents": [4]},
            "4": {"address": 4, "size": 40, "type": None, "str": "", "referents": [5]},
            "5": {"address": 5, "size": 50, "type": None, "str": "", "referents": [6]},
            "6": {"address": 6, "size": 60, "type": None, "str": "", "referents": []},
            "7": {"address": 7, "size": 70, "type": None, "str": "", "referents": []},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 10 + 20 + 30 + 40 + 50 + 60 + 70
    assert heap.retained_heap(2) == 20 + 30 + 40 + 50 + 60
    assert heap.retained_heap(3) == 30 + 40 + 50 + 60
    assert heap.retained_heap(4) == 40 + 50 + 60
    assert heap.retained_heap(5) == 50 + 60
    assert heap.retained_heap(6) == 60
    assert heap.retained_heap(7) == 70


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_transitive(
    calculator_factory: Callable[[Heap], RetainedHeapCalculator]
) -> None:
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
                "referents": [2, 3],
            },
            "2": {"address": 2, "size": 20, "type": None, "str": "", "referents": []},
            "3": {"address": 3, "size": 30, "type": None, "str": "", "referents": [2]},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 10 + 20 + 30
    assert heap.retained_heap(2) == 20
    assert heap.retained_heap(3) == 30


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_side_reference(
    calculator_factory: Callable[[Heap], RetainedHeapCalculator]
) -> None:
    # 1 -> 2 -> 3 -> 4
    #                ^
    #                5
    heap_dict = {
        "objects": {
            "1": {"address": 1, "size": 10, "type": None, "str": "", "referents": [2]},
            "2": {"address": 2, "size": 20, "type": None, "str": "", "referents": [3]},
            "3": {"address": 3, "size": 30, "type": None, "str": "", "referents": [4]},
            "4": {"address": 4, "size": 40, "type": None, "str": "", "referents": []},
            "5": {"address": 5, "size": 50, "type": None, "str": "", "referents": [4]},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 10 + 20 + 30
    assert heap.retained_heap(2) == 20 + 30
    assert heap.retained_heap(3) == 30
    assert heap.retained_heap(4) == 40
    assert heap.retained_heap(5) == 50


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_cross(calculator_factory: Callable[[Heap], RetainedHeapCalculator]) -> None:
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
                "referents": [3, 4],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "referents": [3, 4],
            },
            "3": {"address": 3, "size": 30, "type": None, "str": "", "referents": []},
            "4": {"address": 4, "size": 40, "type": None, "str": "", "referents": []},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 10
    assert heap.retained_heap(2) == 20
    assert heap.retained_heap(3) == 30
    assert heap.retained_heap(4) == 40


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_complex_1(
    calculator_factory: Callable[[Heap], RetainedHeapCalculator]
) -> None:
    # 5 <- 4
    # |    ^    +--> 6 -> 7
    # |    |    |
    # +--> 3 -> 2 -> 1
    #      ^         |
    #      +---------+
    heap_dict = {
        "objects": {
            "1": {"address": 1, "size": 10, "type": None, "str": "", "referents": [3]},
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "referents": [1, 6],
            },
            "3": {
                "address": 3,
                "size": 30,
                "type": None,
                "str": "",
                "referents": [2, 4],
            },
            "4": {"address": 4, "size": 40, "type": None, "str": "", "referents": [5]},
            "5": {"address": 5, "size": 50, "type": None, "str": "", "referents": [3]},
            "6": {"address": 6, "size": 60, "type": None, "str": "", "referents": [7]},
            "7": {"address": 7, "size": 70, "type": None, "str": "", "referents": []},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 10
    assert heap.retained_heap(2) == 20 + 10 + 60 + 70
    assert heap.retained_heap(3) == 30 + (20 + 10 + 60 + 70) + (40 + 50)
    assert heap.retained_heap(4) == 40 + 50
    assert heap.retained_heap(5) == 50


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_complex_2(
    calculator_factory: Callable[[Heap], RetainedHeapCalculator]
) -> None:
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
                "referents": [5, 6],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "referents": [4, 7],
            },
            "3": {"address": 3, "size": 30, "type": None, "str": "", "referents": [5]},
            "4": {"address": 4, "size": 40, "type": None, "str": "", "referents": [2]},
            "5": {"address": 5, "size": 50, "type": None, "str": "", "referents": [6]},
            "6": {
                "address": 6,
                "size": 60,
                "type": None,
                "str": "",
                "referents": [7, 8],
            },
            "7": {"address": 7, "size": 70, "type": None, "str": "", "referents": [5]},
            "8": {"address": 8, "size": 80, "type": None, "str": "", "referents": []},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 10
    assert heap.retained_heap(2) == 20 + 40
    assert heap.retained_heap(3) == 30
    assert heap.retained_heap(4) == 40 + 20
    assert heap.retained_heap(5) == 50
    assert heap.retained_heap(6) == 60 + 80
    assert heap.retained_heap(7) == 70
    assert heap.retained_heap(8) == 80


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_complex_3(
    calculator_factory: Callable[[Heap], RetainedHeapCalculator]
) -> None:
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
                "referents": [2, 3],
            },
            "2": {
                "address": 2,
                "size": 20,
                "type": None,
                "str": "",
                "referents": [4, 5, 6, 7],
            },
            "3": {"address": 3, "size": 30, "type": None, "str": "", "referents": [7]},
            "4": {"address": 4, "size": 40, "type": None, "str": "", "referents": []},
            "5": {"address": 5, "size": 50, "type": None, "str": "", "referents": []},
            "6": {"address": 6, "size": 60, "type": None, "str": "", "referents": []},
            "7": {"address": 7, "size": 70, "type": None, "str": "", "referents": []},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 10 + 20 + 30 + 40 + 50 + 60 + 70
    assert heap.retained_heap(2) == 20 + 40 + 50 + 60
    assert heap.retained_heap(3) == 30
    assert heap.retained_heap(4) == 40
    assert heap.retained_heap(5) == 50
    assert heap.retained_heap(6) == 60
    assert heap.retained_heap(7) == 70


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_forest_minimal(
    calculator_factory: Callable[[Heap], RetainedHeapCalculator]
) -> None:
    # 1  2  3  4
    heap_dict = {
        "objects": {
            "1": {"address": 1, "size": 10, "type": None, "str": "", "referents": []},
            "2": {"address": 2, "size": 20, "type": None, "str": "", "referents": []},
            "3": {"address": 3, "size": 30, "type": None, "str": "", "referents": []},
            "4": {"address": 4, "size": 40, "type": None, "str": "", "referents": []},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 10
    assert heap.retained_heap(2) == 20
    assert heap.retained_heap(3) == 30
    assert heap.retained_heap(4) == 40


@pytest.mark.parametrize(
    "calculator_factory",
    [RetainedHeapSequentialCalculator, RetainedHeapParallelCalculator],
)
def test_forest_simple(
    calculator_factory: Callable[[Heap], RetainedHeapCalculator]
) -> None:
    # 1 -> 2  3 -> 4
    heap_dict = {
        "objects": {
            "1": {"address": 1, "size": 10, "type": None, "str": "", "referents": [2]},
            "2": {"address": 2, "size": 20, "type": None, "str": "", "referents": []},
            "3": {"address": 3, "size": 30, "type": None, "str": "", "referents": [4]},
            "4": {"address": 4, "size": 40, "type": None, "str": "", "referents": []},
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    calculator = calculator_factory(heap)
    heap.set_retained_heap(calculator.calculate())
    assert heap.retained_heap(1) == 10 + 20
    assert heap.retained_heap(2) == 20
    assert heap.retained_heap(3) == 30 + 40
    assert heap.retained_heap(4) == 40
