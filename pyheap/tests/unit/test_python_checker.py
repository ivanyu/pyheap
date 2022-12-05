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
from typing import Optional
from unittest.mock import patch, mock_open, MagicMock, NonCallableMagicMock

import pytest

from python_checker import check_if_python, _get_libpython_path


def test_symbol_found_in_exe() -> None:
    def mock(*args):
        assert args[0] == "/proc/1/exe"
        return mock_open(read_data="")()

    elffile_mock = MagicMock()
    section_mock = NonCallableMagicMock()
    elffile_mock.get_section_by_name = MagicMock(return_value=section_mock)
    section_mock.is_null = MagicMock(return_value=False)
    section_mock.get_symbol_by_name.return_value = NonCallableMagicMock()
    with patch("builtins.open", side_effect=mock), patch(
        "elftools.elf.elffile.ELFFile", return_value=elffile_mock
    ):
        assert check_if_python(1)


def test_symbol_found_in_libpython() -> None:
    def mock(*args):
        if args[0] == "/proc/1/exe":
            return mock_open(read_data="")()
        elif args[0] == "/proc/1/maps":
            d = """558e62a04000-558e62a05000 r--p 00000000 00:1d 28059                      /usr/local/bin/python3.8
7f700d482000-7f700d484000 r--p 00000000 00:1d 1384                       /usr/local/lib/libpython3.8.so.1.0
            """
            return mock_open(read_data=d)()
        elif args[0] == "/proc/1/root/usr/local/lib/libpython3.8.so.1.0":
            return mock_open(read_data="")()
        else:
            assert False

    elffile_exe_mock = MagicMock()
    section_mock = NonCallableMagicMock()
    elffile_exe_mock.get_section_by_name = MagicMock(return_value=section_mock)
    section_mock.is_null = MagicMock(return_value=False)
    section_mock.get_symbol_by_name.return_value = None

    elffile_libpython_mock = MagicMock()
    section_mock = NonCallableMagicMock()
    elffile_libpython_mock.get_section_by_name = MagicMock(return_value=section_mock)
    section_mock.is_null = MagicMock(return_value=False)
    section_mock.get_symbol_by_name.return_value = NonCallableMagicMock()

    with patch("builtins.open", side_effect=mock), patch(
        "elftools.elf.elffile.ELFFile",
        side_effect=[elffile_exe_mock, elffile_libpython_mock],
    ):
        assert check_if_python(1)


def test_symbol_not_found_no_libpython() -> None:
    def mock(*args):
        if args[0] == "/proc/1/exe":
            return mock_open(read_data="")()
        elif args[0] == "/proc/1/maps":
            d = """558e62a04000-558e62a05000 r--p 00000000 00:1d 28059                      /usr/local/bin/python3.8
"""
            return mock_open(read_data=d)()
        else:
            assert False

    elffile_exe_mock = MagicMock()
    section_mock = NonCallableMagicMock()
    elffile_exe_mock.get_section_by_name = MagicMock(return_value=section_mock)
    section_mock.is_null = MagicMock(return_value=False)
    section_mock.get_symbol_by_name.return_value = None

    with patch("builtins.open", side_effect=mock), patch(
        "elftools.elf.elffile.ELFFile",
        return_value=elffile_exe_mock,
    ):
        assert not check_if_python(1)


def test_symbol_not_found_in_libpython() -> None:
    def mock(*args):
        if args[0] == "/proc/1/exe":
            return mock_open(read_data="")()
        elif args[0] == "/proc/1/maps":
            d = """558e62a04000-558e62a05000 r--p 00000000 00:1d 28059                      /usr/local/bin/python3.8
7f700d482000-7f700d484000 r--p 00000000 00:1d 1384                       /usr/local/lib/libpython3.8.so.1.0
            """
            return mock_open(read_data=d)()
        elif args[0] == "/proc/1/root/usr/local/lib/libpython3.8.so.1.0":
            return mock_open(read_data="")()
        else:
            assert False

    elffile_exe_mock = MagicMock()
    section_mock = NonCallableMagicMock()
    elffile_exe_mock.get_section_by_name = MagicMock(return_value=section_mock)
    section_mock.is_null = MagicMock(return_value=False)
    section_mock.get_symbol_by_name.return_value = None

    elffile_libpython_mock = MagicMock()
    section_mock = NonCallableMagicMock()
    elffile_libpython_mock.get_section_by_name = MagicMock(return_value=section_mock)
    section_mock.is_null = MagicMock(return_value=False)
    section_mock.get_symbol_by_name.return_value = None

    with patch("builtins.open", side_effect=mock), patch(
        "elftools.elf.elffile.ELFFile",
        side_effect=[elffile_exe_mock, elffile_libpython_mock],
    ):
        assert not check_if_python(1)


@pytest.mark.parametrize(
    "path, expected",
    [
        (
            "/usr/local/lib/libpython3.8.so.1.0",
            "/proc/123/root/usr/local/lib/libpython3.8.so.1.0",
        ),
        (
            "/usr/lib64/libpython3.8.so.1.0",
            "/proc/123/root/usr/lib64/libpython3.8.so.1.0",
        ),
        (
            "/usr/local/lib/libpython3.10.so.1.0",
            "/proc/123/root/usr/local/lib/libpython3.10.so.1.0",
        ),
        (
            "/usr/lib64/libpython3.11.so.1.0",
            "/proc/123/root/usr/lib64/libpython3.11.so.1.0",
        ),
        ("/usr/lib/x86_64-linux-gnu/libuuid.so.1.3.0", None),
        (None, None),
    ],
)
def test_get_libpython_path(path: Optional[str], expected: Optional[str]) -> None:
    path = path or ""
    maps_data = f"""558e62a04000-558e62a05000 r--p 00000000 00:1d 28059                      /usr/local/bin/python3.10
558e647d4000-558e64b37000 rw-p 00000000 00:00 0                          [heap]
7f70085f5000-7f700c000000 ---p 00000000 00:00 0
7f700d482000-7f700d484000 r--p 00000000 00:1d 1384                       /usr/lib/x86_64-linux-gnu/libuuid.so.1.3.0
7f700e87e000-7f700e976000 r--p 0027e000 00:1d 28227                      {path}    
"""
    with patch("builtins.open", mock_open(read_data=maps_data)):
        assert _get_libpython_path(123) == expected
