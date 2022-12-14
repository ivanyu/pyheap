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
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Set, Optional, Callable, Any, Mapping, Union, Tuple, cast
from typing_extensions import Annotated, NewType


class IntType(Enum):
    UNSIGNED_INT = auto()
    UNSIGNED_LONG = auto()


UnsignedInt = Annotated[int, IntType.UNSIGNED_INT]
UnsignedLong = Annotated[int, IntType.UNSIGNED_LONG]
Address = UnsignedLong
Offset = NewType("Offset", int)

ThreadName = str
JsonObject = Mapping[str, Any]


@dataclass(frozen=True)
class HeapFlags:
    with_str_repr: bool


@dataclass(frozen=True)
class HeapHeader:
    version: UnsignedInt
    created_at: str
    flags: HeapFlags
    well_known_types: Dict[str, Address]


@dataclass(frozen=True)
class HeapThreadFrame:
    co_filename: str
    lineno: UnsignedInt
    co_name: str
    locals: Dict[str, Address]


@dataclass(frozen=True)
class HeapThread:
    name: str
    is_alive: bool
    is_daemon: bool
    stack_trace: List[HeapThreadFrame]

    @property
    def locals(self) -> Set[Address]:
        result = set()
        for frame in self.stack_trace:
            result.update(frame.locals.values())
        return result


AttributeName = NewType("AttributeName", str)
ObjectContent = Union[
    Dict[Address, Address], List[Address], Set[Address], Tuple[Address, ...], None
]


@dataclass
class HeapObject:
    address: Address
    type: Address
    size: UnsignedInt
    referents: Set[Address]
    content: ObjectContent = field(default=None)

    def __post_init__(self) -> None:
        self._attributes_offset: Optional[int] = None
        self._read_attributes_func: Optional[
            Callable[[int], Dict[AttributeName, Address]]
        ] = None

        self._str_repr_func: Optional[Callable[["HeapObject"], Optional[str]]] = None

    def __hash__(self) -> int:
        return hash(self.address)

    def __eq__(self, o: object) -> bool:
        if isinstance(o, HeapObject):
            return cast(HeapObject, o).address == self.address
        else:
            return False

    def set_read_attributes_func(
        self, offset: int, func: Callable[[int], Dict[AttributeName, Address]]
    ) -> None:
        self._attributes_offset = offset
        self._read_attributes_func = func

    @property
    def attributes(self) -> Dict[AttributeName, Address]:
        return self._read_attributes_func(self._attributes_offset)

    @property
    def str_repr(self) -> Optional[str]:
        return self._str_repr_func(self)

    def __getstate__(self) -> Dict[str, Any]:
        # Exclude pickling the lazy load functions.
        state = self.__dict__.copy()
        if "_read_attributes_func" in state:
            del state["_read_attributes_func"]
        if "_str_repr_func" in state:
            del state["_str_repr_func"]
        return state


ObjectDict = NewType("ObjectDict", Dict[Address, HeapObject])


@dataclass(frozen=True)
class Heap:
    header: HeapHeader
    threads: List[HeapThread]
    objects: ObjectDict
    types: Dict[Address, str]
