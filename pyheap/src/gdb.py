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

import contextlib
import os
import re
from pathlib import Path
from typing import List, Optional, Iterator

import mount
from proc import proc_maps


def solib_search_paths(pid: int, pid_in_ns: int) -> List[str]:
    # libc (isn't used in e.g. Alpine Linux) and libpthread (maybe not loaded) are optional.
    libc_path: Optional[str] = None
    libpthread_path: Optional[str] = None
    for parts in proc_maps(pid):
        if len(parts) != 6:
            continue
        path = parts[-1]
        if libc_path is None and re.search(r"libc(-[\d.]+)?\.so(\.|$)", path):
            libc_path = path
        if libpthread_path is None and re.search(
            r"libpthread(-[\d.]+)?\.so(\.|$)", path
        ):
            libpthread_path = path

    dirs = set()
    if libc_path is not None:
        dirs.add(str(Path(libc_path).parent))
    if libpthread_path is not None:
        dirs.add(str(Path(libpthread_path).parent))
    return [f"/proc/{pid_in_ns}/root{d}" for d in dirs]


@contextlib.contextmanager
def bind_gdb_exe(gdb_exe: str, temp_dir: str) -> Iterator[str]:
    gdb_mount_file = Path(temp_dir) / "gdb"
    gdb_mount_file.touch(
        mode=os.stat(gdb_exe).st_mode & 0o777,
        exist_ok=False,
    )
    mounted = str(gdb_mount_file)
    mount.mount(gdb_exe, mounted, "", mountflags=mount.MS_BIND)
    try:
        yield mounted
    finally:
        mount.umount(mounted)


def shadow_target_exe_dir_for_gdb(target_pid: int, temp_dir: str, force: bool) -> None:
    """Shadows the target executable directory for GDB.

    There may be a situation, where ``self/pid/exe`` points to an executable inside
    the target mount namespace, but which also exists in the dumper/GDB namespace. For example, ``/usr/bin/python3.11``.
    GDB (``canonicalize_file_name`` inside it) doesn't handle this nicely and uses the file in the dumper namespace
    for reading symbols. This doesn't work well. If GDB/``canonicalize_file_name`` sees the file doesn't exist,
    it reads from the ``self/pid/exe`` directly, which works fine.

    This function basically bind-mounts an empty directory over the target file parent directory (e.g. ``/usr/bin``) in
    the dumper namespace.
    """
    try:
        target_exe = os.readlink(f"/proc/{target_pid}/exe")
    except PermissionError as e:
        raise Exception(
            "Hint: the target process is likely run under a different user, use sudo"
        ) from e

    if os.path.exists(target_exe):
        print(
            f"Target exe link resolves to {target_exe}, which exists in our namespace"
        )
    elif force:
        print("Shadowing is forced")
    else:
        return
    dir_to_shadow = str(Path(target_exe).parent)
    print(f"Will shadow directory {dir_to_shadow}")

    shadow_dir = os.path.join(temp_dir, "shadow")
    os.mkdir(shadow_dir, mode=os.stat(dir_to_shadow).st_mode & 0o777)
    mount.mount(shadow_dir, dir_to_shadow, "", mountflags=mount.MS_BIND)
