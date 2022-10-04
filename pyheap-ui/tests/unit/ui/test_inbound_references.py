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
from ui.heap import Heap


def test_minimal() -> None:
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "type": None,
                "size": 0,
                "str": "",
                "attrs": {},
                "referents": [],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    assert heap._inbound_references._inbound_references == {1: set()}


def test_self_reference() -> None:
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "type": None,
                "size": 0,
                "str": "",
                "attrs": {},
                "referents": [1],
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    assert heap._inbound_references._inbound_references == {1: {1}}


def simple() -> None:
    # 1 -> 2 -> 4
    #  \-> 3 <--|
    heap_dict = {
        "objects": {
            "1": {
                "address": 1,
                "type": None,
                "size": 0,
                "str": "",
                "referents": {2, 3},
            },
            "2": {
                "address": 2,
                "type": None,
                "size": 0,
                "str": "",
                "attrs": {},
                "referents": {4},
            },
            "3": {
                "address": 3,
                "type": None,
                "size": 0,
                "str": "",
                "attrs": {},
                "referents": {},
            },
            "4": {
                "address": 4,
                "type": None,
                "size": 0,
                "str": "",
                "attrs": {},
                "referents": {3},
            },
        },
        "types": {},
    }
    heap = Heap(heap_dict)
    assert heap._inbound_references == {
        1: [],
        2: [1],
        3: [1, 4],
        4: [2],
    }
