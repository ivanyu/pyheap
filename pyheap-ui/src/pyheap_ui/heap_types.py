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
from dataclasses import dataclass
from enum import Enum, auto
from typing import Annotated, NewType, Dict, List, Set, Optional, Callable, Any, Mapping


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


@dataclass
class HeapObject:
    type: Address
    size: UnsignedInt
    referents: Set[Address]

    def __post_init__(self) -> None:
        self._read_attributes_func: Optional[Callable[[], Dict[str, Address]]] = None
        self._read_str_repr_func: Optional[Callable[[], str]] = None

    def set_read_attributes_func(self, func: Callable[[], Dict[str, Address]]) -> None:
        self._read_attributes_func = func

    def set_read_str_repr_func(self, func: Callable[[], str]) -> None:
        self._read_str_repr_func = func

    @property
    def attributes(self) -> Dict[str, Address]:
        return self._read_attributes_func()

    @property
    def str_repr(self) -> Optional[str]:
        if self._read_str_repr_func:
            return self._read_str_repr_func()
        else:
            return None

    def __getstate__(self) -> Dict[str, Any]:
        # Exclude pickling the lazy load functions.
        state = self.__dict__.copy()
        if "_read_attributes_func" in state:
            del state["_read_attributes_func"]
        if "_read_str_repr_func" in state:
            del state["_read_str_repr_func"]
        return state


ObjectDict = Dict[Address, HeapObject]


@dataclass(frozen=True)
class Heap:
    header: HeapHeader
    threads: List[HeapThread]
    objects: ObjectDict
    types: Dict[Address, str]
