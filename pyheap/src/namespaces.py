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
import ctypes
from ctypes.util import find_library
from typing import Iterator, Union

from mount import (
    set_propagation_on_root,
    MS_PRIVATE,
    MS_REC,
    mount,
    MS_NODEV,
    MS_NOEXEC,
    MS_NOSUID,
)

libc = ctypes.CDLL(find_library("c"), use_errno=True)

# linux/sched.h
CLONE_NEWNS = 0x00020000
CLONE_NEWPID = 0x20000000


def nsenter_to_pid_ns_with_fork(pid: int) -> None:
    """Does similar to ``nsenter -t <pid> -p``.

    In other words, it enters the PID namespace of the specified process and forks.
    The child continues. The parent waits for the child and propagates its return code.
    """

    # nsenter into the PID namespace
    with _pid_namespace(pid) as fd:
        if libc.setns(fd, CLONE_NEWPID) != 0:
            raise Exception(f"Failed on setns: {os.strerror(ctypes.get_errno())}")

    # Fork for the PID namespace to take effect. (See `man setns`).
    fork_pid = os.fork()
    if fork_pid < 0:
        # This won't be probably executed as fork() will raise OSError,
        # but still having it for completeness.
        raise Exception("Fork failed")
    elif fork_pid > 0:
        # --- The parent waits on the child here ---

        _, child_status = os.waitpid(fork_pid, 0)
        kill_signal = child_status & 0xFF
        if kill_signal != 0:
            print(f"Child killed by signal {kill_signal}")
            exit(1)
        else:
            return_code = child_status & 0xFF00
            exit(return_code)

    # --- The child continues here ---


def unshare_and_mount_proc() -> None:
    """Does similar to ``unshare --mount-proc``.

    In other words, this creates a new mount namespace and mounts /proc there.
    """

    # Unshare with new mount namespace.
    if libc.unshare(CLONE_NEWNS) != 0:
        raise Exception(f"Failed on unshare: {os.strerror(ctypes.get_errno())}")

    # Make mount propagation private.
    set_propagation_on_root(mountflags=MS_REC | MS_PRIVATE)

    # Mount /proc.
    mount(
        source="proc",
        target="/proc",
        fs_type="proc",
        mountflags=MS_NOSUID | MS_NOEXEC | MS_NODEV,
    )


@contextlib.contextmanager
def _pid_namespace(pid: int) -> Iterator[int]:
    fd = os.open(f"/proc/{pid}/ns/pid", os.O_RDONLY)
    yield fd
    os.close(fd)


def two_processes_in_same_pid_namespace(
    pid1: Union[int, str], pid2: Union[int, str]
) -> bool:
    return _read_pid_namespace_link(pid1) == _read_pid_namespace_link(pid2)


def _read_pid_namespace_link(pid: Union[int, str]) -> str:
    try:
        return os.readlink(f"/proc/{pid}/ns/pid")
    except PermissionError as e:
        print(e)
        print("Hint: the target process is likely run under a different user, use sudo")
        raise e


def pid_in_own_namespace(pid: Union[int, str]) -> int:
    """Finds the PID of a process in its own PID namespace."""
    with open(f"/proc/{pid}/status", "r") as f:
        for line in f.readlines():
            line = line.strip()
            if line.startswith("NStgid"):
                return int(line.split("\t")[-1].strip())
        else:
            raise Exception("Cannot determine target process PID in its namespace")
