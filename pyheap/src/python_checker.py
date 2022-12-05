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
import re
from typing import Optional

from elftools.elf import elffile

from constants import PY_EVAL_EVAL_FRAME_DEFAULT
from proc import proc_maps


def check_if_python(pid: int) -> bool:
    """Checks (as far as the heuristics go) that the target process is CPython, and we can work with it."""

    # First check if the executable itself has the _PyEval_EvalFrameDefault symbol.
    # Consider it Python if it does.
    if _check_has_eval_symbol(f"/proc/{pid}/exe"):
        return True

    # Then, check if it uses libpython and if this library has _PyEval_EvalFrameDefault.
    # Consider it Python if it does.
    libpython_path = _get_libpython_path(pid)
    if not libpython_path:
        return False
    return _check_has_eval_symbol(libpython_path)


def _check_has_eval_symbol(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            elf = elffile.ELFFile(f)
            dynsym = elf.get_section_by_name(".dynsym")
            if dynsym.is_null():
                return False
            pyeval_sym = dynsym.get_symbol_by_name(PY_EVAL_EVAL_FRAME_DEFAULT)
            return pyeval_sym is not None
    except PermissionError as e:
        raise Exception(
            "Hint: the target process is likely run under a different user, use sudo"
        ) from e


def _get_libpython_path(pid: int) -> Optional[str]:
    try:
        for parts in proc_maps(pid):
            if len(parts) != 6:
                continue

            path = parts[-1]
            if re.search(r"libpython([\d.]+)?\.so(\.|$)", path):
                return f"/proc/{pid}/root{path}"
        else:
            return None
    except PermissionError as e:
        raise Exception(
            "Hint: the target process is likely run under a different user, use sudo"
        ) from e
