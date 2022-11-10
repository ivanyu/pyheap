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
from unittest.mock import MagicMock

from pyheap_ui.heap_reader import _NoneStrReprProvider, _StrReprProvider
from pyheap_ui.heap_types import HeapObject


DICT_TYPE = 0
LIST_TYPE = 1
SET_TYPE = 2
TUPLE_TYPE = 3
WELL_KNOWN_TYPES = {
    "dict": DICT_TYPE,
    "list": LIST_TYPE,
    "set": SET_TYPE,
    "tuple": TUPLE_TYPE,
}
OTHER_TYPE = 100

A_OBJ = HeapObject(address=0, type=OTHER_TYPE, size=0, referents=set(), content=None)
B_OBJ = HeapObject(address=1, type=OTHER_TYPE, size=0, referents=set(), content=None)
C_OBJ = HeapObject(address=2, type=OTHER_TYPE, size=0, referents=set(), content=None)
D_OBJ = HeapObject(address=3, type=OTHER_TYPE, size=0, referents=set(), content=None)
UNKNOWN_OBJ = HeapObject(
    address=100, type=OTHER_TYPE, size=0, referents=set(), content=None
)

A_OFFSET = 1000
B_OFFSET = 2000
C_OFFSET = 3000
D_OFFSET = 4000
READ_STR_REPR_MAPPING = {
    A_OFFSET: "a",
    B_OFFSET: "b",
    C_OFFSET: "c",
    D_OFFSET: "d",
}


def test_simple_dict() -> None:
    dict_obj = HeapObject(
        address=10,
        type=DICT_TYPE,
        size=0,
        referents=set(),
        content={
            A_OBJ.address: B_OBJ.address,
            C_OBJ.address: UNKNOWN_OBJ.address,
        },
    )

    objects = {
        A_OBJ.address: A_OBJ,
        B_OBJ.address: B_OBJ,
        C_OBJ.address: C_OBJ,
        dict_obj.address: dict_obj,
    }
    provider = _StrReprProvider(
        well_known_types=WELL_KNOWN_TYPES,
        objects=objects,
        read_str_repr=READ_STR_REPR_MAPPING.get,
    )
    provider.set_str_repr_offset(A_OBJ.address, A_OFFSET)
    provider.set_str_repr_offset(B_OBJ.address, B_OFFSET)
    provider.set_str_repr_offset(C_OBJ.address, C_OFFSET)
    assert provider.str_repr(A_OBJ) == "a"
    assert provider.str_repr(B_OBJ) == "b"
    assert provider.str_repr(C_OBJ) == "c"
    assert provider.str_repr(UNKNOWN_OBJ) == "(unknown)"
    assert provider.str_repr(dict_obj) == "{a: b, c: (unknown)}"


def test_recursive_dict() -> None:
    dict_obj = HeapObject(
        address=10,
        type=DICT_TYPE,
        size=0,
        referents=set(),
        content={
            A_OBJ.address: B_OBJ.address,
            C_OBJ.address: 10,
        },
    )

    objects = {
        A_OBJ.address: A_OBJ,
        B_OBJ.address: B_OBJ,
        C_OBJ.address: C_OBJ,
        dict_obj.address: dict_obj,
    }
    provider = _StrReprProvider(
        well_known_types=WELL_KNOWN_TYPES,
        objects=objects,
        read_str_repr=READ_STR_REPR_MAPPING.get,
    )
    provider.set_str_repr_offset(A_OBJ.address, A_OFFSET)
    provider.set_str_repr_offset(B_OBJ.address, B_OFFSET)
    provider.set_str_repr_offset(C_OBJ.address, C_OFFSET)
    assert provider.str_repr(dict_obj) == "{a: b, c: {...}}"


def test_simple_list() -> None:
    list_obj = HeapObject(
        address=10,
        type=LIST_TYPE,
        size=0,
        referents=set(),
        content=[A_OBJ.address, B_OBJ.address, C_OBJ.address, UNKNOWN_OBJ.address],
    )

    objects = {
        A_OBJ.address: A_OBJ,
        B_OBJ.address: B_OBJ,
        C_OBJ.address: C_OBJ,
        list_obj.address: list_obj,
    }
    provider = _StrReprProvider(
        well_known_types=WELL_KNOWN_TYPES,
        objects=objects,
        read_str_repr=READ_STR_REPR_MAPPING.get,
    )
    provider.set_str_repr_offset(A_OBJ.address, A_OFFSET)
    provider.set_str_repr_offset(B_OBJ.address, B_OFFSET)
    provider.set_str_repr_offset(C_OBJ.address, C_OFFSET)
    assert provider.str_repr(A_OBJ) == "a"
    assert provider.str_repr(B_OBJ) == "b"
    assert provider.str_repr(C_OBJ) == "c"
    assert provider.str_repr(UNKNOWN_OBJ) == "(unknown)"
    assert provider.str_repr(list_obj) == "[a, b, c, (unknown)]"


def test_recursive_list() -> None:
    list_obj = HeapObject(
        address=10,
        type=LIST_TYPE,
        size=0,
        referents=set(),
        content=[A_OBJ.address, B_OBJ.address, 10, C_OBJ.address],
    )

    objects = {
        A_OBJ.address: A_OBJ,
        B_OBJ.address: B_OBJ,
        C_OBJ.address: C_OBJ,
        list_obj.address: list_obj,
    }
    provider = _StrReprProvider(
        well_known_types=WELL_KNOWN_TYPES,
        objects=objects,
        read_str_repr=READ_STR_REPR_MAPPING.get,
    )
    provider.set_str_repr_offset(A_OBJ.address, A_OFFSET)
    provider.set_str_repr_offset(B_OBJ.address, B_OFFSET)
    provider.set_str_repr_offset(C_OBJ.address, C_OFFSET)
    assert provider.str_repr(list_obj) == "[a, b, [...], c]"


def test_simple_set() -> None:
    set_obj = HeapObject(
        address=10,
        type=SET_TYPE,
        size=0,
        referents=set(),
        content={A_OBJ.address, B_OBJ.address, C_OBJ.address, UNKNOWN_OBJ.address},
    )

    objects = {
        A_OBJ.address: A_OBJ,
        B_OBJ.address: B_OBJ,
        C_OBJ.address: C_OBJ,
        set_obj.address: set_obj,
    }
    provider = _StrReprProvider(
        well_known_types=WELL_KNOWN_TYPES,
        objects=objects,
        read_str_repr=READ_STR_REPR_MAPPING.get,
    )
    provider.set_str_repr_offset(A_OBJ.address, A_OFFSET)
    provider.set_str_repr_offset(B_OBJ.address, B_OFFSET)
    provider.set_str_repr_offset(C_OBJ.address, C_OFFSET)
    assert provider.str_repr(A_OBJ) == "a"
    assert provider.str_repr(B_OBJ) == "b"
    assert provider.str_repr(C_OBJ) == "c"
    assert provider.str_repr(UNKNOWN_OBJ) == "(unknown)"
    assert provider.str_repr(set_obj) == "{a, b, c, (unknown)}"


def test_recursive_set() -> None:
    set_obj = HeapObject(
        address=10,
        type=SET_TYPE,
        size=0,
        referents=set(),
        content={A_OBJ.address, B_OBJ.address, 10, C_OBJ.address},
    )

    objects = {
        A_OBJ.address: A_OBJ,
        B_OBJ.address: B_OBJ,
        C_OBJ.address: C_OBJ,
        set_obj.address: set_obj,
    }
    provider = _StrReprProvider(
        well_known_types=WELL_KNOWN_TYPES,
        objects=objects,
        read_str_repr=READ_STR_REPR_MAPPING.get,
    )
    provider.set_str_repr_offset(A_OBJ.address, A_OFFSET)
    provider.set_str_repr_offset(B_OBJ.address, B_OFFSET)
    provider.set_str_repr_offset(C_OBJ.address, C_OFFSET)
    assert provider.str_repr(set_obj) == "{a, b, {...}, c}"


def test_simple_tuple() -> None:
    tuple_obj = HeapObject(
        address=10,
        type=TUPLE_TYPE,
        size=0,
        referents=set(),
        content={A_OBJ.address, B_OBJ.address, C_OBJ.address, UNKNOWN_OBJ.address},
    )

    objects = {
        A_OBJ.address: A_OBJ,
        B_OBJ.address: B_OBJ,
        C_OBJ.address: C_OBJ,
        tuple_obj.address: tuple_obj,
    }
    provider = _StrReprProvider(
        well_known_types=WELL_KNOWN_TYPES,
        objects=objects,
        read_str_repr=READ_STR_REPR_MAPPING.get,
    )
    provider.set_str_repr_offset(A_OBJ.address, A_OFFSET)
    provider.set_str_repr_offset(B_OBJ.address, B_OFFSET)
    provider.set_str_repr_offset(C_OBJ.address, C_OFFSET)
    assert provider.str_repr(A_OBJ) == "a"
    assert provider.str_repr(B_OBJ) == "b"
    assert provider.str_repr(C_OBJ) == "c"
    assert provider.str_repr(UNKNOWN_OBJ) == "(unknown)"
    assert provider.str_repr(tuple_obj) == "(a, b, c, (unknown))"


def test_inner_collection() -> None:
    set_obj = HeapObject(
        address=10,
        type=SET_TYPE,
        size=0,
        referents=set(),
        content={A_OBJ.address, B_OBJ.address, C_OBJ.address},
    )
    tuple_obj = HeapObject(
        address=11,
        type=TUPLE_TYPE,
        size=0,
        referents=set(),
        content=(A_OBJ.address, set_obj.address, C_OBJ.address),
    )
    list_obj = HeapObject(
        address=12,
        type=LIST_TYPE,
        size=0,
        referents=set(),
        content=[A_OBJ.address, tuple_obj.address, C_OBJ.address],
    )
    dict_obj = HeapObject(
        address=13,
        type=DICT_TYPE,
        size=0,
        referents=set(),
        content={A_OBJ.address: list_obj.address},
    )
    objects = {
        A_OBJ.address: A_OBJ,
        B_OBJ.address: B_OBJ,
        C_OBJ.address: C_OBJ,
        set_obj.address: set_obj,
        tuple_obj.address: tuple_obj,
        list_obj.address: list_obj,
        dict_obj.address: dict_obj,
    }
    provider = _StrReprProvider(
        well_known_types=WELL_KNOWN_TYPES,
        objects=objects,
        read_str_repr=READ_STR_REPR_MAPPING.get,
    )
    provider.set_str_repr_offset(A_OBJ.address, A_OFFSET)
    provider.set_str_repr_offset(B_OBJ.address, B_OFFSET)
    provider.set_str_repr_offset(C_OBJ.address, C_OFFSET)
    assert provider.str_repr(A_OBJ) == "a"
    assert provider.str_repr(B_OBJ) == "b"
    assert provider.str_repr(C_OBJ) == "c"
    assert provider.str_repr(set_obj) == "{a, b, c}"
    assert provider.str_repr(tuple_obj) == "(a, {a, b, c}, c)"
    assert provider.str_repr(list_obj) == "[a, (a, {a, b, c}, c), c]"
    assert provider.str_repr(dict_obj) == "{a: [a, (a, {a, b, c}, c), c]}"


def test_mutual_recursive() -> None:
    tuple_obj = HeapObject(
        address=11,
        type=TUPLE_TYPE,
        size=0,
        referents=set(),
        content=None,
    )
    list_obj = HeapObject(
        address=12,
        type=LIST_TYPE,
        size=0,
        referents=set(),
        content=None,
    )
    list_obj.content = [A_OBJ.address, tuple_obj.address, C_OBJ.address]
    dict_obj = HeapObject(
        address=13,
        type=DICT_TYPE,
        size=0,
        referents=set(),
        content={A_OBJ.address: list_obj.address},
    )
    tuple_obj.content = (A_OBJ.address, dict_obj.address, C_OBJ.address)

    objects = {
        A_OBJ.address: A_OBJ,
        B_OBJ.address: B_OBJ,
        C_OBJ.address: C_OBJ,
        tuple_obj.address: tuple_obj,
        list_obj.address: list_obj,
        dict_obj.address: dict_obj,
    }
    provider = _StrReprProvider(
        well_known_types=WELL_KNOWN_TYPES,
        objects=objects,
        read_str_repr=READ_STR_REPR_MAPPING.get,
    )
    provider.set_str_repr_offset(A_OBJ.address, A_OFFSET)
    provider.set_str_repr_offset(B_OBJ.address, B_OFFSET)
    provider.set_str_repr_offset(C_OBJ.address, C_OFFSET)
    assert provider.str_repr(A_OBJ) == "a"
    assert provider.str_repr(B_OBJ) == "b"
    assert provider.str_repr(C_OBJ) == "c"
    assert provider.str_repr(tuple_obj) == "(a, {a: [a, (...), c]}, c)"
    assert provider.str_repr(list_obj) == "[a, (a, {a: [...]}, c), c]"
    assert provider.str_repr(dict_obj) == "{a: [a, (a, {...}, c), c]}"


def test_reading() -> None:
    obj = HeapObject(address=10, type=OTHER_TYPE, size=0, referents=set(), content=None)
    read_str_repr_mock = MagicMock()
    read_str_repr_mock.return_value = "result"
    provider = _StrReprProvider(
        well_known_types=WELL_KNOWN_TYPES,
        objects={obj.address: obj},
        read_str_repr=read_str_repr_mock,
    )
    provider.set_str_repr_offset(obj.address, 123)
    assert provider.str_repr(obj) == "result"
    read_str_repr_mock.assert_called_once_with(123)


def test_unknown_object() -> None:
    provider = _StrReprProvider(
        well_known_types=WELL_KNOWN_TYPES, objects={}, read_str_repr=lambda _: ""
    )
    obj = HeapObject(address=0, type=OTHER_TYPE, size=0, referents=set(), content=None)
    assert provider.str_repr(obj) == "(unknown)"


def test_none_provider_returns_none() -> None:
    obj = HeapObject(address=0, type=OTHER_TYPE, size=0, referents=set(), content=None)
    assert _NoneStrReprProvider().str_repr(obj) is None


def test_none_provider_set_offset() -> None:
    _NoneStrReprProvider().set_str_repr_offset(1, 0)  # should not raise
