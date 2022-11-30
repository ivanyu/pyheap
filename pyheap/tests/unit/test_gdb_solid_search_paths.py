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
from unittest.mock import mock_open, patch, MagicMock

import pytest

from gdb import solib_search_paths


def test_both_path_present_and_same_dir() -> None:
    with patch(
        "builtins.open",
        _mock_maps(
            libc_path="/lib/x86_64-linux-gnu/libc-2.31.so",
            libpthread_path="/lib/x86_64-linux-gnu/libpthread-2.31.so",
        ),
    ):
        r = solib_search_paths(123, 456)
    assert r == ["/proc/456/root/lib/x86_64-linux-gnu"]


def test_both_path_present_and_different_dir() -> None:
    with patch(
        "builtins.open",
        _mock_maps(
            libc_path="/lib/x86_64-linux-gnu/libc-2.31.so",
            libpthread_path="/lib64/libpthread-2.31.so",
        ),
    ):
        r = solib_search_paths(123, 456)
    assert set(r) == {
        "/proc/456/root/lib/x86_64-linux-gnu",
        "/proc/456/root/lib64",
    }


def test_only_libc_path() -> None:
    with patch(
        "builtins.open",
        _mock_maps(
            libc_path="/lib/x86_64-linux-gnu/libc-2.31.so",
            libpthread_path=None,
        ),
    ):
        r = solib_search_paths(123, 456)
    assert r == ["/proc/456/root/lib/x86_64-linux-gnu"]


@pytest.mark.parametrize(
    "libc_path",
    [
        "/lib/x86_64-linux-gnu/libc-2.31.so",
        "/lib/x86_64-linux-gnu/libc.so",
        "/lib/x86_64-linux-gnu/libc.so.6",
    ],
)
def test_filename_format(libc_path: str) -> None:
    with patch(
        "builtins.open",
        _mock_maps(
            libc_path=libc_path,
            libpthread_path=None,
        ),
    ):
        r = solib_search_paths(123, 456)
    assert r == ["/proc/456/root/lib/x86_64-linux-gnu"]


def test_libc_path_not_present() -> None:
    with patch(
        "builtins.open",
        _mock_maps(libc_path=None, libpthread_path=None),
    ):
        solib_search_paths(123, 456)


def _mock_maps(
    *, libc_path: Optional[str], libpthread_path: Optional[str]
) -> MagicMock:
    maps_data = """558e62a04000-558e62a05000 r--p 00000000 00:1d 28059                      /usr/local/bin/python3.10
558e62a05000-558e62a06000 r-xp 00001000 00:1d 28059                      /usr/local/bin/python3.10
558e62a06000-558e62a07000 r--p 00002000 00:1d 28059                      /usr/local/bin/python3.10
558e62a07000-558e62a08000 r--p 00002000 00:1d 28059                      /usr/local/bin/python3.10
558e62a08000-558e62a09000 rw-p 00003000 00:1d 28059                      /usr/local/bin/python3.10
558e647d4000-558e64b37000 rw-p 00000000 00:00 0                          [heap]
7f7008000000-7f70085f5000 rw-p 00000000 00:00 0 
7f70085f5000-7f700c000000 ---p 00000000 00:00 0 
7f700cd37000-7f700ce37000 rw-p 00000000 00:00 0 
7f700d179000-7f700d279000 rw-p 00000000 00:00 0 
7f700d30a000-7f700d40a000 rw-p 00000000 00:00 0 
7f700d482000-7f700d484000 r--p 00000000 00:1d 1384                       /usr/lib/x86_64-linux-gnu/libuuid.so.1.3.0
7f700d484000-7f700d488000 r-xp 00002000 00:1d 1384                       /usr/lib/x86_64-linux-gnu/libuuid.so.1.3.0
7f700d488000-7f700d489000 r--p 00006000 00:1d 1384                       /usr/lib/x86_64-linux-gnu/libuuid.so.1.3.0
7f700d489000-7f700d48a000 r--p 00006000 00:1d 1384                       /usr/lib/x86_64-linux-gnu/libuuid.so.1.3.0
7f700d48a000-7f700d48b000 rw-p 00007000 00:1d 1384                       /usr/lib/x86_64-linux-gnu/libuuid.so.1.3.0
7f700d493000-7f700d495000 r--p 00000000 00:1d 28826                      /usr/local/lib/python3.10/lib-dynload/select.cpython-310-x86_64-linux-gnu.so
7f700d495000-7f700d498000 r-xp 00002000 00:1d 28826                      /usr/local/lib/python3.10/lib-dynload/select.cpython-310-x86_64-linux-gnu.so
7f700d498000-7f700d49a000 r--p 00005000 00:1d 28826                      /usr/local/lib/python3.10/lib-dynload/select.cpython-310-x86_64-linux-gnu.so
7f700d49a000-7f700d49b000 r--p 00006000 00:1d 28826                      /usr/local/lib/python3.10/lib-dynload/select.cpython-310-x86_64-linux-gnu.so
7f700d49b000-7f700d49c000 rw-p 00007000 00:1d 28826                      /usr/local/lib/python3.10/lib-dynload/select.cpython-310-x86_64-linux-gnu.so
7f700d49c000-7f700d49e000 r--p 00000000 00:1d 28791                      /usr/local/lib/python3.10/lib-dynload/_posixsubprocess.cpython-310-x86_64-linux-gnu.so
7f700d49e000-7f700d4a1000 r-xp 00002000 00:1d 28791                      /usr/local/lib/python3.10/lib-dynload/_posixsubprocess.cpython-310-x86_64-linux-gnu.so
7f700d4a1000-7f700d4a2000 r--p 00005000 00:1d 28791                      /usr/local/lib/python3.10/lib-dynload/_posixsubprocess.cpython-310-x86_64-linux-gnu.so
7f700d4a2000-7f700d4a3000 r--p 00005000 00:1d 28791                      /usr/local/lib/python3.10/lib-dynload/_posixsubprocess.cpython-310-x86_64-linux-gnu.so
7f700d4a3000-7f700d4a4000 rw-p 00006000 00:1d 28791                      /usr/local/lib/python3.10/lib-dynload/_posixsubprocess.cpython-310-x86_64-linux-gnu.so
7f700d4a4000-7f700d4a5000 r--p 00000000 00:1d 28817                      /usr/local/lib/python3.10/lib-dynload/fcntl.cpython-310-x86_64-linux-gnu.so
7f700d4a5000-7f700d4a7000 r-xp 00001000 00:1d 28817                      /usr/local/lib/python3.10/lib-dynload/fcntl.cpython-310-x86_64-linux-gnu.so
7f700d4a7000-7f700d4a9000 r--p 00003000 00:1d 28817                      /usr/local/lib/python3.10/lib-dynload/fcntl.cpython-310-x86_64-linux-gnu.so
7f700d4a9000-7f700d4aa000 r--p 00004000 00:1d 28817                      /usr/local/lib/python3.10/lib-dynload/fcntl.cpython-310-x86_64-linux-gnu.so
7f700d4aa000-7f700d4ab000 rw-p 00005000 00:1d 28817                      /usr/local/lib/python3.10/lib-dynload/fcntl.cpython-310-x86_64-linux-gnu.so
7f700d4ab000-7f700d4b0000 r--p 00000000 00:1d 28775                      /usr/local/lib/python3.10/lib-dynload/_datetime.cpython-310-x86_64-linux-gnu.so
7f700d4b0000-7f700d4c2000 r-xp 00005000 00:1d 28775                      /usr/local/lib/python3.10/lib-dynload/_datetime.cpython-310-x86_64-linux-gnu.so
7f700d4c2000-7f700d4c8000 r--p 00017000 00:1d 28775                      /usr/local/lib/python3.10/lib-dynload/_datetime.cpython-310-x86_64-linux-gnu.so
7f700d4c8000-7f700d4c9000 r--p 0001c000 00:1d 28775                      /usr/local/lib/python3.10/lib-dynload/_datetime.cpython-310-x86_64-linux-gnu.so
7f700d4c9000-7f700d4cc000 rw-p 0001d000 00:1d 28775                      /usr/local/lib/python3.10/lib-dynload/_datetime.cpython-310-x86_64-linux-gnu.so
7f700d4cc000-7f700d5cc000 rw-p 00000000 00:00 0 
7f700d5cc000-7f700d5cd000 ---p 00000000 00:00 0 
7f700d5cd000-7f700e0c2000 rw-p 00000000 00:00 0 
7f700e0c8000-7f700e0cb000 r--p 00000000 00:1d 28802                      /usr/local/lib/python3.10/lib-dynload/_struct.cpython-310-x86_64-linux-gnu.so
7f700e0cb000-7f700e0d0000 r-xp 00003000 00:1d 28802                      /usr/local/lib/python3.10/lib-dynload/_struct.cpython-310-x86_64-linux-gnu.so
7f700e0d0000-7f700e0d4000 r--p 00008000 00:1d 28802                      /usr/local/lib/python3.10/lib-dynload/_struct.cpython-310-x86_64-linux-gnu.so
7f700e0d4000-7f700e0d5000 r--p 0000b000 00:1d 28802                      /usr/local/lib/python3.10/lib-dynload/_struct.cpython-310-x86_64-linux-gnu.so
7f700e0d5000-7f700e0d6000 rw-p 0000c000 00:1d 28802                      /usr/local/lib/python3.10/lib-dynload/_struct.cpython-310-x86_64-linux-gnu.so
7f700e0d6000-7f700e0d9000 r--p 00000000 00:1d 28819                      /usr/local/lib/python3.10/lib-dynload/math.cpython-310-x86_64-linux-gnu.so
7f700e0d9000-7f700e0e1000 r-xp 00003000 00:1d 28819                      /usr/local/lib/python3.10/lib-dynload/math.cpython-310-x86_64-linux-gnu.so
7f700e0e1000-7f700e0e5000 r--p 0000b000 00:1d 28819                      /usr/local/lib/python3.10/lib-dynload/math.cpython-310-x86_64-linux-gnu.so
7f700e0e5000-7f700e0e6000 r--p 0000e000 00:1d 28819                      /usr/local/lib/python3.10/lib-dynload/math.cpython-310-x86_64-linux-gnu.so
7f700e0e6000-7f700e0e7000 rw-p 0000f000 00:1d 28819                      /usr/local/lib/python3.10/lib-dynload/math.cpython-310-x86_64-linux-gnu.so
7f700e0e7000-7f700e2e7000 rw-p 00000000 00:00 0 
7f700e2e7000-7f700e2f4000 r--p 00000000 00:1d 617                        /lib/x86_64-linux-gnu/libm-2.31.so
7f700e2f4000-7f700e38e000 r-xp 0000d000 00:1d 617                        /lib/x86_64-linux-gnu/libm-2.31.so
7f700e38e000-7f700e429000 r--p 000a7000 00:1d 617                        /lib/x86_64-linux-gnu/libm-2.31.so
7f700e429000-7f700e42a000 r--p 00141000 00:1d 617                        /lib/x86_64-linux-gnu/libm-2.31.so
7f700e42a000-7f700e42b000 rw-p 00142000 00:1d 617                        /lib/x86_64-linux-gnu/libm-2.31.so
"""
    if libc_path is not None:
        maps_data += f"""7f700e42b000-7f700e44d000 r--p 00000000 00:1d 596                        {libc_path}
7f700e44d000-7f700e5a7000 r-xp 00022000 00:1d 596                        {libc_path}
7f700e5a7000-7f700e5f6000 r--p 0017c000 00:1d 596                        {libc_path}
7f700e5f6000-7f700e5fa000 r--p 001ca000 00:1d 596                        {libc_path}
7f700e5fa000-7f700e5fc000 rw-p 001ce000 00:1d 596                        {libc_path}
7f700e5fc000-7f700e600000 rw-p 00000000 00:00 0
"""

    maps_data += f"""7f700e600000-7f700e659000 r--p 00000000 00:1d 28227                      /usr/local/lib/libpython3.10.so.1.0
7f700e659000-7f700e87e000 r-xp 00059000 00:1d 28227                      /usr/local/lib/libpython3.10.so.1.0
7f700e87e000-7f700e976000 r--p 0027e000 00:1d 28227                      /usr/local/lib/libpython3.10.so.1.0
7f700e976000-7f700e97b000 r--p 00375000 00:1d 28227                      /usr/local/lib/libpython3.10.so.1.0
7f700e97b000-7f700e9ae000 rw-p 0037a000 00:1d 28227                      /usr/local/lib/libpython3.10.so.1.0
7f700e9ae000-7f700e9b4000 rw-p 00000000 00:00 0 
7f700e9b5000-7f700e9b6000 r--p 00000000 00:1d 28809                      /usr/local/lib/python3.10/lib-dynload/_uuid.cpython-310-x86_64-linux-gnu.so
7f700e9b6000-7f700e9b7000 r-xp 00001000 00:1d 28809                      /usr/local/lib/python3.10/lib-dynload/_uuid.cpython-310-x86_64-linux-gnu.so
7f700e9b7000-7f700e9b8000 r--p 00002000 00:1d 28809                      /usr/local/lib/python3.10/lib-dynload/_uuid.cpython-310-x86_64-linux-gnu.so
7f700e9b8000-7f700e9b9000 r--p 00002000 00:1d 28809                      /usr/local/lib/python3.10/lib-dynload/_uuid.cpython-310-x86_64-linux-gnu.so
7f700e9b9000-7f700e9ba000 rw-p 00003000 00:1d 28809                      /usr/local/lib/python3.10/lib-dynload/_uuid.cpython-310-x86_64-linux-gnu.so
7f700e9ba000-7f700e9bb000 r--p 00000000 00:1d 28788                      /usr/local/lib/python3.10/lib-dynload/_opcode.cpython-310-x86_64-linux-gnu.so
7f700e9bb000-7f700e9bc000 r-xp 00001000 00:1d 28788                      /usr/local/lib/python3.10/lib-dynload/_opcode.cpython-310-x86_64-linux-gnu.so
7f700e9bc000-7f700e9bd000 r--p 00002000 00:1d 28788                      /usr/local/lib/python3.10/lib-dynload/_opcode.cpython-310-x86_64-linux-gnu.so
7f700e9bd000-7f700e9be000 r--p 00002000 00:1d 28788                      /usr/local/lib/python3.10/lib-dynload/_opcode.cpython-310-x86_64-linux-gnu.so
7f700e9be000-7f700e9bf000 rw-p 00003000 00:1d 28788                      /usr/local/lib/python3.10/lib-dynload/_opcode.cpython-310-x86_64-linux-gnu.so
7f700e9bf000-7f700e9c1000 r--p 00000000 00:1d 28782                      /usr/local/lib/python3.10/lib-dynload/_json.cpython-310-x86_64-linux-gnu.so
7f700e9c1000-7f700e9c7000 r-xp 00002000 00:1d 28782                      /usr/local/lib/python3.10/lib-dynload/_json.cpython-310-x86_64-linux-gnu.so
7f700e9c7000-7f700e9c9000 r--p 00008000 00:1d 28782                      /usr/local/lib/python3.10/lib-dynload/_json.cpython-310-x86_64-linux-gnu.so
7f700e9c9000-7f700e9ca000 r--p 00009000 00:1d 28782                      /usr/local/lib/python3.10/lib-dynload/_json.cpython-310-x86_64-linux-gnu.so
7f700e9ca000-7f700e9cb000 rw-p 0000a000 00:1d 28782                      /usr/local/lib/python3.10/lib-dynload/_json.cpython-310-x86_64-linux-gnu.so
7f700e9cb000-7f700ea20000 r--p 00000000 00:1d 1025                       /usr/lib/locale/C.UTF-8/LC_CTYPE
7f700ea20000-7f700ea25000 rw-p 00000000 00:00 0 
7f700ea25000-7f700ea26000 r--p 00000000 00:1d 657                        /lib/x86_64-linux-gnu/libutil-2.31.so
7f700ea26000-7f700ea27000 r-xp 00001000 00:1d 657                        /lib/x86_64-linux-gnu/libutil-2.31.so
7f700ea27000-7f700ea28000 r--p 00002000 00:1d 657                        /lib/x86_64-linux-gnu/libutil-2.31.so
7f700ea28000-7f700ea29000 r--p 00002000 00:1d 657                        /lib/x86_64-linux-gnu/libutil-2.31.so
7f700ea29000-7f700ea2a000 rw-p 00003000 00:1d 657                        /lib/x86_64-linux-gnu/libutil-2.31.so
7f700ea2a000-7f700ea2b000 r--p 00000000 00:1d 604                        /lib/x86_64-linux-gnu/libdl-2.31.so
7f700ea2b000-7f700ea2d000 r-xp 00001000 00:1d 604                        /lib/x86_64-linux-gnu/libdl-2.31.so
7f700ea2d000-7f700ea2e000 r--p 00003000 00:1d 604                        /lib/x86_64-linux-gnu/libdl-2.31.so
7f700ea2e000-7f700ea2f000 r--p 00003000 00:1d 604                        /lib/x86_64-linux-gnu/libdl-2.31.so
7f700ea2f000-7f700ea30000 rw-p 00004000 00:1d 604                        /lib/x86_64-linux-gnu/libdl-2.31.so
"""
    if libpthread_path is not None:
        maps_data += f"""7f700ea30000-7f700ea36000 r--p 00000000 00:1d 641                        {libpthread_path}
7f700ea36000-7f700ea46000 r-xp 00006000 00:1d 641                        {libpthread_path}
7f700ea46000-7f700ea4c000 r--p 00016000 00:1d 641                        {libpthread_path}
7f700ea4c000-7f700ea4d000 r--p 0001b000 00:1d 641                        {libpthread_path}
7f700ea4d000-7f700ea4e000 rw-p 0001c000 00:1d 641                        {libpthread_path}
"""
    maps_data += """7f700ea4e000-7f700ea54000 rw-p 00000000 00:00 0 
7f700ea55000-7f700ea5c000 r--s 00000000 00:1d 1305                       /usr/lib/x86_64-linux-gnu/gconv/gconv-modules.cache
7f700ea5c000-7f700ea5d000 r--p 00000000 00:1d 584                        /lib/x86_64-linux-gnu/ld-2.31.so
7f700ea5d000-7f700ea7d000 r-xp 00001000 00:1d 584                        /lib/x86_64-linux-gnu/ld-2.31.so
7f700ea7d000-7f700ea85000 r--p 00021000 00:1d 584                        /lib/x86_64-linux-gnu/ld-2.31.so
7f700ea86000-7f700ea87000 r--p 00029000 00:1d 584                        /lib/x86_64-linux-gnu/ld-2.31.so
7f700ea87000-7f700ea88000 rw-p 0002a000 00:1d 584                        /lib/x86_64-linux-gnu/ld-2.31.so
7f700ea88000-7f700ea89000 rw-p 00000000 00:00 0 
7ffe71ec0000-7ffe71ee1000 rw-p 00000000 00:00 0                          [stack]
7ffe71f6d000-7ffe71f71000 r--p 00000000 00:00 0                          [vvar]
7ffe71f71000-7ffe71f73000 r-xp 00000000 00:00 0                          [vdso]
ffffffffff600000-ffffffffff601000 --xp 00000000 00:00 0                  [vsyscall]"""

    return mock_open(read_data=maps_data)
