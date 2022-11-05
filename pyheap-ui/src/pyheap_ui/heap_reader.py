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
import dataclasses
import mmap

import sys

if sys.version_info >= (3, 9):
    from functools import cache
else:
    from functools import lru_cache

    cache = lru_cache(maxsize=None)

import typing_extensions
from typing_extensions import Annotated
from typing import (
    Dict,
    TypeVar,
    Type,
    Callable,
    Union,
    Iterable,
    Any,
    Set,
    Optional,
    List,
)
import struct
from pyheap_ui.heap_types import (
    Heap,
    HeapObject,
    IntType,
    Address,
    UnsignedInt,
    HeapFlags,
    ObjectDict,
    AttributeName,
)

T = TypeVar("T")


@dataclasses.dataclass(frozen=True)
class _CommonType:
    attributes: Dict[AttributeName, Address]


def cache_by_id(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """This cache uses the object ID as the caching key.

    To use it, be sure the identity of the objects are stable enough. For example, it can be used for type objects,
    that are instantiated earlier in the program life cycle and aren't deleted.
    """
    cache_dict = {}

    def inner(arg: Any) -> Any:
        i = id(arg)
        if i in cache_dict:
            return cache_dict[i]
        r = func(arg)
        cache_dict[i] = r
        return r

    return inner


class HeapReader:
    _MAGIC = 123_000_321

    _UNSIGNED_BOOL_STRUCT = struct.Struct("!?")
    _UNSIGNED_BOOL_STRUCT_SIZE = _UNSIGNED_BOOL_STRUCT.size
    _SIGNED_SHORT_STRUCT = struct.Struct("!h")
    _SIGNED_SHORT_STRUCT_SIZE = _SIGNED_SHORT_STRUCT.size
    _UNSIGNED_SHORT_STRUCT = struct.Struct("!H")
    _UNSIGNED_SHORT_STRUCT_SIZE = _UNSIGNED_SHORT_STRUCT.size
    _UNSIGNED_INT_STRUCT = struct.Struct("!I")
    _UNSIGNED_INT_STRUCT_SIZE = _UNSIGNED_INT_STRUCT.size
    _UNSIGNED_LONG_STRUCT = struct.Struct("!Q")
    _UNSIGNED_LONG_STRUCT_SIZE = _UNSIGNED_LONG_STRUCT.size

    def __init__(self, buf: Union[bytes, mmap.mmap]) -> None:
        self._buf = buf
        self._offset = 0

        self._flags: Optional[HeapFlags] = None
        self._frequent_attrs: Optional[List[str]] = None
        self._common_types: Optional[Dict[Address, _CommonType]] = None

    def read(self) -> Heap:
        # Header
        magic = self._read_unsigned_long()
        if magic != self._MAGIC:
            raise ValueError("Invalid magic value")

        heap = self._read(Heap)

        # Footer
        magic = self._read_unsigned_long()
        if magic != self._MAGIC:
            raise ValueError("Invalid magic value")

        return heap

    def _read(self, type_: Type[T]) -> T:
        if type_ == HeapObject:
            return self._read_heap_object()
        elif type_ == HeapFlags:
            return self._read_heap_flags()
        elif type_ == ObjectDict:
            return self._read_object_dict()
        elif type_ == AttributeName:
            return self._read_attribute_name()
        elif self._is_dataclass(type_):
            return self._read_dataclass(type_)
        elif self._get_origin(type_) is list:
            return self._read_generic_list(type_)
        elif self._get_origin(type_) is set:
            return self._read_generic_set(type_)
        elif self._get_origin(type_) is dict:
            return self._read_generic_dict(type_)
        elif type_ == str:
            return self._read_long_string()
        elif type_ == bool:
            return self._read_bool()
        elif self._get_origin(type_) is Annotated:
            args = self._get_args(type_)
            if len(args) != 2 or args[0] != int and isinstance(args[1], IntType):
                raise ValueError(f"Unsupported type {type_}")
            if args[1] == IntType.UNSIGNED_INT:
                return self._read_unsigned_int()
            if args[1] == IntType.UNSIGNED_LONG:
                return self._read_unsigned_long()
            else:
                raise ValueError(f"Unsupported type {type_}")
        else:
            raise ValueError(f"Unsupported type {type_}")

    @staticmethod
    @cache_by_id
    def _is_dataclass(type_: Type[T]) -> bool:
        return dataclasses.is_dataclass(type_)

    @staticmethod
    @cache_by_id
    def _fields(type_: Type[T]) -> Iterable[dataclasses.Field]:
        return dataclasses.fields(type_)

    @staticmethod
    @cache_by_id
    def _get_origin(type_: Type[T]) -> Any:
        return typing_extensions.get_origin(type_)

    @staticmethod
    @cache_by_id
    def _get_args(type_: Type[T]) -> Any:
        return typing_extensions.get_args(type_)

    def _read_heap_object(self) -> HeapObject:
        r = HeapObject(
            type=self._read(Address),
            size=self._read(UnsignedInt),
            referents=self._read(Set[Address]),
        )

        # Attributes are present only for non-"common" types.
        if r.type not in self._common_types:
            # Skip the attributes.
            r.set_read_attributes_func(self._offset, self._read_attributes)
            attr_count = self._read_unsigned_int()
            for _ in range(attr_count):
                self._skip_attribute_name_or_index()
                self._skip_unsigned_long()
        else:
            r.set_read_attributes_func(
                -1, lambda _: self._common_types[r.type].attributes
            )

        # Skip the string representation.
        if self._flags.with_str_repr:
            r.set_read_str_repr_func(self._offset, self._read_str_repr)
            self._skip_long_string()

        return r

    def _read_attributes(self, offset: int) -> Dict[AttributeName, Address]:
        self._offset = offset

        dict_size = self._read_unsigned_int()
        result: Dict[AttributeName, Address] = {}
        for _ in range(dict_size):
            k = self._read_attribute_name()
            v = self._read(Address)
            result[k] = v
        return result

    def _read_attribute_name(self) -> AttributeName:
        length_or_index = self._read_signed_short()
        if length_or_index >= 0:
            name = self._read_string_with_known_length(length_or_index)
        else:
            true_index = -1 * (length_or_index + 1)
            name = self._frequent_attrs[true_index]
        return AttributeName(name)

    def _read_str_repr(self, offset: int) -> str:
        self._offset = offset
        return self._read_long_string()

    def _read_heap_flags(self) -> HeapFlags:
        flag_with_str_repr = 1
        value = self._read_unsigned_long()
        r = HeapFlags(with_str_repr=bool(value & flag_with_str_repr))
        self._flags = r
        return r

    def _read_object_dict(self) -> ObjectDict:
        self._frequent_attrs = self._read_generic_list(List[str])
        self._common_types = self._read_generic_dict(Dict[Address, _CommonType])
        r = ObjectDict(self._read_generic_dict(ObjectDict.__supertype__))
        return r

    def _read_dataclass(self, type_: Type[T]) -> T:
        fields = {}
        for f in self._fields(type_):
            fields[f.name] = self._read(f.type)
        return type_(**fields)

    def _read_generic_list(self, type_: Type[T]) -> T:
        args = self._get_args(type_)
        if len(args) != 1:
            raise ValueError(f"Unsupported type {type_}")
        list_size = self._read_unsigned_int()
        result = []
        for _ in range(list_size):
            result.append(self._read(args[0]))
        return result

    def _read_generic_set(self, type_: Type[T]) -> T:
        args = self._get_args(type_)
        if len(args) != 1:
            raise ValueError(f"Unsupported type {type_}")
        set_size = self._read_unsigned_int()
        result = set()
        for _ in range(set_size):
            result.add(self._read(args[0]))
        return result

    def _read_generic_dict(self, type_: Type[T]) -> T:
        args = self._get_args(type_)
        if len(args) != 2:
            raise ValueError(f"Unsupported type {type_}")
        dict_size = self._read_unsigned_int()
        result = {}
        for _ in range(dict_size):
            k = self._read(args[0])
            v = self._read(args[1])
            result[k] = v
        return result

    def _skip_attribute_name_or_index(self) -> None:
        length_or_index = self._read_signed_short()
        if length_or_index >= 0:
            self._offset += length_or_index

    def _skip_long_string(self) -> None:
        length = self._UNSIGNED_SHORT_STRUCT.unpack_from(self._buf, self._offset)[0]
        self._offset += self._UNSIGNED_SHORT_STRUCT_SIZE + length

    def _skip_unsigned_long(self) -> None:
        self._offset += self._UNSIGNED_LONG_STRUCT_SIZE

    def _read_long_string(self) -> str:
        length = self._UNSIGNED_SHORT_STRUCT.unpack_from(self._buf, self._offset)[0]
        self._offset += self._UNSIGNED_SHORT_STRUCT_SIZE
        return self._read_string_with_known_length(length)

    def _read_string_with_known_length(self, length: int) -> str:
        # Cache short string structures for performance.
        if length <= 1024:
            s = self._get_string_struct(length)
            r = s.unpack_from(self._buf, self._offset)[0]
            self._offset += s.size
        else:
            fmt = f"!{length}s"
            r = struct.unpack_from(fmt, self._buf, self._offset)[0]
            self._offset += struct.calcsize(fmt)

        return r.decode("utf-8")

    @cache
    def _get_string_struct(self, length: int) -> struct.Struct:
        return struct.Struct(f"!{length}s")

    def _read_signed_short(self) -> int:
        value = self._SIGNED_SHORT_STRUCT.unpack_from(self._buf, self._offset)[0]
        self._offset += self._SIGNED_SHORT_STRUCT_SIZE
        return value

    def _read_unsigned_int(self) -> int:
        value = self._UNSIGNED_INT_STRUCT.unpack_from(self._buf, self._offset)[0]
        self._offset += self._UNSIGNED_INT_STRUCT_SIZE
        return value

    def _read_unsigned_long(self) -> int:
        value = self._UNSIGNED_LONG_STRUCT.unpack_from(self._buf, self._offset)[0]
        self._offset += self._UNSIGNED_LONG_STRUCT_SIZE
        return value

    def _read_bool(self) -> bool:
        value = self._UNSIGNED_BOOL_STRUCT.unpack_from(self._buf, self._offset)[0]
        self._offset += self._UNSIGNED_BOOL_STRUCT_SIZE
        return value
