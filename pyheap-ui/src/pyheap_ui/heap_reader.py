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
from abc import ABC, abstractmethod
import sys

from tqdm import tqdm

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
    Tuple,
    cast,
    Mapping,
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
    HeapHeader,
    ObjectContent,
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

    def __init__(
        self, buf: Union[bytes, mmap.mmap], object_progress_bar: bool = False
    ) -> None:
        self._buf = buf
        self._offset = 0

        self._object_progress_bar = object_progress_bar

        self._flags: Optional[HeapFlags] = None
        self._frequent_attrs: Optional[List[str]] = None
        self._common_types: Optional[Dict[Address, _CommonType]] = None
        self._header: Optional[HeapHeader] = None
        self._objects: Optional[ObjectDict] = None

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
        if type_ == HeapHeader:
            return self._read_heap_header()
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
        elif self._get_origin(type_) is tuple:
            return self._read_generic_tuple(type_)
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

    def _read_heap_header(self) -> HeapHeader:
        header = self._read_dataclass(HeapHeader)
        if header.version != 1:
            raise ValueError(f"Unsupported heap format version: {header.version}")
        self._header = header
        return header

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

    def _read_heap_object(self, address: Address) -> HeapObject:
        type_ = self._read(Address)
        size_ = self._read(UnsignedInt)

        is_well_known_container_type = type_ in {
            self._header.well_known_types["dict"],
            self._header.well_known_types["list"],
            self._header.well_known_types["set"],
            self._header.well_known_types["tuple"],
        }

        content: ObjectContent = None
        extra_referents: Set[Address] = set()
        if type_ == self._header.well_known_types["dict"]:
            content = self._read_generic_dict(Dict[Address, Address])
            extra_referents.update(content.keys())
            extra_referents.update(content.values())
        if type_ == self._header.well_known_types["list"]:
            content = self._read_generic_list(List[Address])
            extra_referents.update(content)
        if type_ == self._header.well_known_types["set"]:
            content = self._read_generic_set(Set[Address])
            extra_referents.update(content)
        if type_ == self._header.well_known_types["tuple"]:
            content = self._read_generic_tuple(Tuple[Address])
            extra_referents.update(content)

        referents = self._read(Set[Address])
        referents.update(extra_referents)

        r = HeapObject(
            address=address,
            type=type_,
            size=size_,
            referents=referents,
            content=content,
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

        r._str_repr_func = self._str_repr_provider.str_repr
        self._str_repr_provider.set_str_repr_offset(address, self._offset)

        # Skip the string representation.
        if self._flags.with_str_repr and not is_well_known_container_type:
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

    def _read_heap_flags(self) -> HeapFlags:
        flag_with_str_repr = 1
        value = self._read_unsigned_long()
        r = HeapFlags(with_str_repr=bool(value & flag_with_str_repr))
        self._flags = r
        return r

    def _read_object_dict(self) -> ObjectDict:
        self._frequent_attrs = self._read_generic_list(List[str])
        self._common_types = self._read_generic_dict(Dict[Address, _CommonType])

        objects = ObjectDict({})

        if self._header.flags.with_str_repr:
            self._str_repr_provider = _StrReprProvider(
                well_known_types=self._header.well_known_types,
                objects=objects,
                read_str_repr=self._read_str_repr,
            )
        else:
            self._str_repr_provider = _NoneStrReprProvider()

        dict_size = self._read_unsigned_int()
        iterator = range(dict_size)
        if self._object_progress_bar:
            iterator = tqdm(iterator, desc="Loading objects", unit="objects")
        for _ in iterator:
            addr = self._read(Address)
            obj = self._read_heap_object(addr)
            objects[addr] = obj
        return objects

    def _read_str_repr(self, offset: int) -> str:
        self._offset = offset
        return self._read_long_string()

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

    def _read_generic_tuple(self, type_: Type[T]) -> T:
        args = self._get_args(type_)
        if len(args) != 1:
            raise ValueError(f"Unsupported type {type_}")
        return tuple(self._read_generic_list(List[args[0]]))

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

        return r.decode("utf-8", "backslashreplace")

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


class _AbstractStrReprProvider(ABC):
    @abstractmethod
    def set_str_repr_offset(self, address: Address, offset: int) -> None:
        pass

    @abstractmethod
    def str_repr(self, obj: HeapObject) -> Optional[str]:
        pass


class _NoneStrReprProvider(_AbstractStrReprProvider):
    def set_str_repr_offset(self, address: Address, offset: int) -> None:
        pass  # do nothing

    def str_repr(self, obj: HeapObject) -> Optional[str]:
        return None


class _StrReprProvider(_AbstractStrReprProvider):
    def __init__(
        self,
        *,
        well_known_types: Dict[str, Address],
        objects: ObjectDict,
        read_str_repr: Callable[[int], str],
    ) -> None:
        self._offsets = {}

        self._dict_type = well_known_types["dict"]
        self._list_type = well_known_types["list"]
        self._set_type = well_known_types["set"]
        self._tuple_type = well_known_types["tuple"]
        self._container_types = {
            self._dict_type,
            self._list_type,
            self._set_type,
            self._tuple_type,
        }

        self._objects = objects
        self._read_str_repr = read_str_repr

    def set_str_repr_offset(self, address: Address, offset: int) -> None:
        """Sets the string representation offset in the file.

        The offset may not always be valid: For the well-known container types, it's not supposed to be used."""
        self._offsets[address] = offset

    def str_repr(self, obj: HeapObject) -> Optional[str]:
        return self._str_repr_internal(obj.address, set())

    def _str_repr_internal(
        self, address: Address, seen_objects: Set[Address]
    ) -> Optional[str]:
        obj = self._objects.get(address)

        if obj is None:
            return "(unknown)"
        if obj.type not in self._container_types:
            return self._read_str_repr(self._offsets[obj.address])

        left_bracket: str
        right_bracket: str
        if obj.type == self._dict_type:
            left_bracket = "{"
            right_bracket = "}"
        elif obj.type == self._list_type:
            left_bracket = "["
            right_bracket = "]"
        elif obj.type == self._set_type:
            left_bracket = "{"
            right_bracket = "}"
        elif obj.type == self._tuple_type:
            left_bracket = "("
            right_bracket = ")"
        else:
            raise ValueError(f"Unsupported type {obj.type}")

        if obj.address in seen_objects:
            return left_bracket + "..." + right_bracket

        inner: str
        new_seen_objects = set(seen_objects)
        new_seen_objects.add(obj.address)

        if obj.type == self._dict_type:
            content = cast(Mapping, obj.content)
            inner = ", ".join(
                self._str_repr_internal(k, new_seen_objects)
                + ": "
                + self._str_repr_internal(v, new_seen_objects)
                for k, v in content.items()
            )
        elif (
            obj.type == self._list_type
            or obj.type == self._tuple_type
            or obj.type == self._set_type
        ):
            content = cast(Iterable, obj.content)
            inner = ", ".join(
                self._str_repr_internal(a, new_seen_objects) for a in content
            )
        else:
            raise ValueError(f"Unsupported type {obj.type}")
        return left_bracket + inner + right_bracket
