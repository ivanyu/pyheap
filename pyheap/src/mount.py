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
import ctypes
import os
from ctypes.util import find_library
from typing import AnyStr

# linux/mount.h
MS_PRIVATE = 1 << 18
MS_NOSUID = 2  # Ignore suid and sgid bits
MS_NODEV = 4  # Disallow access to device special files
MS_NOEXEC = 8  # Disallow program execution
MS_BIND = 4096
MS_REC = 16384


libc = ctypes.CDLL(find_library("c"), use_errno=True)
libc.mount.argtypes = [
    ctypes.c_char_p,  # source
    ctypes.c_char_p,  # target
    ctypes.c_char_p,  # filesystem_type
    ctypes.c_ulong,  # mount_flags
    ctypes.c_void_p,  # data
]
libc.umount.argtypes = [ctypes.c_char_p]  # target


def set_propagation_on_root(mountflags: int) -> None:
    if libc.mount(b"none", b"/", None, mountflags, None) != 0:
        raise Exception(
            f"Failed on mount when setting propagation: {os.strerror(ctypes.get_errno())}"
        )


def mount(source: AnyStr, target: AnyStr, fs_type: AnyStr, mountflags: int) -> None:
    if isinstance(source, str):
        source = source.encode("utf-8")
    if isinstance(target, str):
        target = target.encode("utf-8")
    if isinstance(fs_type, str):
        fs_type = fs_type.encode("utf-8")
    if libc.mount(source, target, fs_type, mountflags, None) != 0:
        raise Exception(
            f"Failed on mount {source} -> {target} with FS type {fs_type}: {os.strerror(ctypes.get_errno())}"
        )


def umount(target: AnyStr) -> None:
    if isinstance(target, str):
        target = target.encode("utf-8")
    if libc.umount(target) != 0:
        raise Exception(f"Failed on umount {target}: {os.strerror(ctypes.get_errno())}")
