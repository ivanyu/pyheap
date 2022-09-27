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
import gdb

"""
This module is executed in the context of GDB's own Python interpreter.
"""

Pointer = int


class DumpPythonHeap(gdb.Function):
    def __init__(self) -> None:
        super(DumpPythonHeap, self).__init__("dump_python_heap")

    def invoke(
        self, dumper_path: gdb.Value, heap_file: gdb.Value, str_len: gdb.Value
    ) -> str:
        if str_len.type.name != "int":
            raise ValueError("str_len must be int")
        heap_file_str = heap_file.string()
        str_len_int = int(str_len)

        dumper_module_ptr = self._inject_dumper_module(dumper_path.string())
        if dumper_module_ptr == 0:
            return "Error injecting dumper module"

        result_str_ptr = self._call_dump_function(
            dumper_module_ptr, heap_file_str, str_len_int
        )
        result = gdb.parse_and_eval(
            f"(char *)PyUnicode_AsUTF8({result_str_ptr})"
        ).string()
        return result

    @staticmethod
    def _inject_dumper_module(dumper_path: str) -> Pointer:
        # Insert the path of the dumper module into `sys.path` in the inferior process.
        sys_ptr = DumpPythonHeap.get_ptr('(void *) PyImport_ImportModule("sys")')
        path_ptr = DumpPythonHeap.get_ptr(
            f'(void *) PyObject_GetAttrString({sys_ptr}, "path")'
        )
        extra_path_ptr = DumpPythonHeap.get_ptr(
            f'(void *) PyUnicode_FromString("{dumper_path}")'
        )
        gdb.parse_and_eval(f"(int) PyList_Insert({path_ptr}, 1, {extra_path_ptr})")

        return DumpPythonHeap.get_ptr(
            '(void*) PyImport_ImportModule("dumper_inferior")'
        )

    @staticmethod
    def _call_dump_function(
        dumper_module_ptr: int, heap_file_name: str, str_len: int
    ) -> Pointer:
        dump_heap_ptr = DumpPythonHeap.get_ptr(
            f'(void *) PyObject_GetAttrString({dumper_module_ptr}, "dump_heap")'
        )
        return DumpPythonHeap.get_ptr(
            f'(void *) PyObject_CallFunction({dump_heap_ptr}, "si", "{heap_file_name}", {str_len})'
        )

    @staticmethod
    def get_ptr(expression: str) -> Pointer:
        return int(gdb.parse_and_eval(expression))


DumpPythonHeap()
