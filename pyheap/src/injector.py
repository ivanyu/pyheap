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

import base64
from contextlib import closing
from typing import Optional

import gdb

"""
This module is executed in the context of GDB's own Python interpreter.
"""

Pointer = int
_NULL = 0
_BUILTINS = "__builtins__"


class InjectorException(Exception):
    ...


def _get_ptr(expression: str) -> Pointer:
    return int(gdb.parse_and_eval(expression))


class _GlobalsDict:
    def __init__(self, **kwargs: str | int) -> None:
        if _BUILTINS in kwargs:
            raise ValueError(f"{_BUILTINS} is not explicitly supported")

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

        # Add __builtins__.
        set_items_result = _get_ptr(
            f'PyDict_SetItemString({self._ptr}, "{_BUILTINS}", _PyInterpreterState_Get()->builtins)'
        )
        if set_items_result < 0:
            raise InjectorException(
                f"Error calling PyDict_SetItemString to set {_BUILTINS}"
            )

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
        gdb.parse_and_eval(f"(void)Py_DecRef({self.ptr})")


class _DumperCode:
    COMPILED_FILE_NAME = "<pyheap>"

    def __init__(self, dumper_code_b64: str) -> None:
        code_bytes = base64.b64decode(dumper_code_b64.encode("utf-8"))
        code_char_string = "".join([hex(b).replace("0x", r"\x") for b in code_bytes])

        self._result_ptr: Pointer = _NULL

        # Doc: https://docs.python.org/3/c-api/veryhigh.html#c.PyRun_File
        Py_file_input = 257  # include/compile.h
        self._code_ptr: Pointer = _get_ptr(
            f'(void*) Py_CompileString("{code_char_string}", "{self.COMPILED_FILE_NAME}", {Py_file_input})'
        )
        if self._code_ptr == _NULL:
            raise InjectorException("Error calling Py_CompileString")

    def run(self, globals_dict: _GlobalsDict) -> None:
        locals_ptr = "(void*) 0"
        self._result_ptr = _get_ptr(
            f"(void*) PyEval_EvalCode({self._code_ptr}, {globals_dict.ptr}, {locals_ptr})"
        )
        if self._result_ptr == _NULL:
            raise InjectorException("Error calling PyEval_EvalCode")

    def close(self) -> None:
        # Doc: https://docs.python.org/3/c-api/refcounting.html#c.Py_DecRef
        if self._code_ptr != _NULL:
            gdb.parse_and_eval(f"(void) Py_DecRef({self._code_ptr})")
        if self._result_ptr != _NULL:
            gdb.parse_and_eval(f"(void) Py_DecRef({self._result_ptr})")


class DumpPythonHeap(gdb.Function):
    def __init__(self) -> None:
        super(DumpPythonHeap, self).__init__("dump_python_heap")

    def invoke(
        self,
        dumper_code_b64: gdb.Value,
        heap_file: gdb.Value,
        str_repr_len: gdb.Value,
        progress_file: gdb.Value,
    ) -> str:
        try:
            return self._invoke0(
                dumper_code_b64, heap_file, str_repr_len, progress_file
            )
        except Exception as e:
            import traceback

            traceback.print_exception(e)
            raise

    def _invoke0(
        self,
        dumper_code_b64: gdb.Value,
        heap_file: gdb.Value,
        str_repr_len: gdb.Value,
        progress_file: gdb.Value,
    ) -> str:
        dumper_code_b64_str = dumper_code_b64.string()
        heap_file_str = heap_file.string()

        if str_repr_len.type.name != "int":
            raise ValueError("str_repr_len must be int")
        str_repr_len_int = int(str_repr_len)

        progress_file_str = progress_file.string()

        dumper_code = _DumperCode(dumper_code_b64_str)
        globals_dict = _GlobalsDict(
            __file__=dumper_code.COMPILED_FILE_NAME,
            heap_file=heap_file_str,
            str_repr_len=str_repr_len_int,
            progress_file=progress_file_str,
        )
        with closing(globals_dict) as globals_dict, closing(dumper_code) as dumper_code:
            dumper_code.run(globals_dict)
            return globals_dict.get_str("result") or "Error getting result"


DumpPythonHeap()
