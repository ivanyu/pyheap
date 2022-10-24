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
from pyheap_ui.heap import InboundReferences
from pyheap_ui.heap_reader import HeapObject


def test_minimal() -> None:
    objects = {
        1: HeapObject(0, 0, set()),
    }
    assert InboundReferences(objects)._inbound_references == {1: set()}


def test_self_reference() -> None:
    objects = {
        1: HeapObject(0, 0, {1}),
    }
    assert InboundReferences(objects)._inbound_references == {1: {1}}


def simple() -> None:
    # 1 -> 2 -> 4
    #  \-> 3 <--|
    objects = {
        1: HeapObject(0, 0, {2, 3}),
        2: HeapObject(0, 0, {4}),
        3: HeapObject(0, 0, set()),
        4: HeapObject(0, 0, {3}),
    }
    assert InboundReferences(objects)._inbound_references == {
        1: [],
        2: [1],
        3: [1, 4],
        4: [2],
    }
