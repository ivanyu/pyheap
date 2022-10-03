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
from __future__ import annotations

from contextlib import closing
from typing import Optional

import gdb

"""
This module is executed in the context of GDB's own Python interpreter.
"""

Pointer = int
_NULL = 0


class InjectorException(Exception):
    ...


def _get_ptr(expression: str) -> Pointer:
    return int(gdb.parse_and_eval(expression))


class _GlobalsDict:
    def __init__(self, **kwargs: str | int) -> None:
        # Doc: https://docs.python.org/3/c-api/arg.html#c.Py_BuildValue
        format_items = []
        param_items = []
        for k, v in kwargs.items():
            format_items.append("s")
            param_items.append(f'"{k}"')
            if isinstance(v, str):
                format_items.append("s")
                param_items.append(f'"{v}"')
            elif isinstance(v, int):
                format_items.append("i")
                param_items.append(f"{v}")
            else:
                raise ValueError(f"Unsupported type {type(v)} of value {v}")
        format_str = "{" + "".join(format_items) + "}"
        param_str = ", ".join(param_items)
        self._ptr = _get_ptr(f'(void*) Py_BuildValue("{format_str}", {param_str})')
        if self._ptr == _NULL:
            raise InjectorException("Error calling Py_BuildValue")

    @property
    def ptr(self) -> Pointer:
        return self._ptr

    def get_str(self, key: str) -> Optional[str]:
        ptr = self._get(key)
        if ptr == _NULL:
            return None
        # Doc: https://docs.python.org/3/c-api/unicode.html#c.PyUnicode_AsUTF8
        result = gdb.parse_and_eval(
            f"(char*) PyUnicode_AsUTF8({ptr})"
        )  # borrowed reference
        if result == _NULL:
            raise InjectorException("Error calling PyUnicode_AsUTF8")
        return result.string()

    def _get(self, key: str) -> Pointer:
        # Doc: https://docs.python.org/3/c-api/dict.html#c.PyDict_GetItemString
        return _get_ptr(f'(void*) PyDict_GetItemString({self._ptr}, "{key}")')

    def close(self) -> None:
        # Doc: https://docs.python.org/3/c-api/refcounting.html#c.Py_DecRef
        gdb.parse_and_eval(f"Py_DecRef({self.ptr})")


class _FP:
    def __init__(self, path: str) -> None:
        self._fp = _get_ptr(f'(void*) fopen("{path}", "r")')
        if self._fp == _NULL:
            raise InjectorException(f"Error opening {path}")

    @property
    def ptr(self) -> Pointer:
        return self._fp

    def close(self) -> None:
        gdb.parse_and_eval(f"fclose({self.ptr})")


class DumpPythonHeap(gdb.Function):
    def __init__(self) -> None:
        super(DumpPythonHeap, self).__init__("dump_python_heap")

    def invoke(self, dumper_path: gdb.Value, heap_file: gdb.Value, str_len: gdb.Value, progress_file: gdb.Value) -> str:
        try:
            return self._invoke0(dumper_path, heap_file, str_len, progress_file)
        except Exception as e:
            import traceback
            traceback.print_exception(e)
            raise

    def _invoke0(
        self, dumper_path: gdb.Value, heap_file: gdb.Value, str_len: gdb.Value, progress_file: gdb.Value
    ) -> str:
        if str_len.type.name != "int":
            raise ValueError("str_len must be int")
        heap_file_str = heap_file.string()
        str_len_int = int(str_len)
        dumper_path_str = dumper_path.string()
        progress_file_str = progress_file.string()

        globals_dict = _GlobalsDict(
            __file__=dumper_path_str,
            heap_file=heap_file_str,
            str_len=str_len_int,
            progress_file=progress_file_str,
        )
        with (
            closing(globals_dict) as globals_dict,
            closing(_FP(dumper_path_str)) as fp,
        ):
            self._run_file(
                fp=fp, dumper_path_str=dumper_path_str, globals_dict=globals_dict
            )
            return globals_dict.get_str("result") or "Error getting result"

    @staticmethod
    def _run_file(*, fp: _FP, dumper_path_str: str, globals_dict: _GlobalsDict) -> None:
        # Doc: https://docs.python.org/3/c-api/veryhigh.html#c.PyRun_File
        Py_file_input = 257  # include/compile.h
        locals_ptr = "(void*) 0"
        r = _get_ptr(
            f'(void*) PyRun_File({fp.ptr}, "{dumper_path_str}", {Py_file_input}, {globals_dict.ptr}, {locals_ptr})'
        )
        if r == _NULL:
            raise InjectorException("Error calling PyRun_File")


DumpPythonHeap()
