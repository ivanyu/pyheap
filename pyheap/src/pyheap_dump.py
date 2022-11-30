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

import argparse
import json
import os.path
import shutil
import uuid
from contextlib import closing, ExitStack
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
from subprocess import Popen
from tempfile import TemporaryDirectory
import time
from pathlib import Path
from typing import (
    Optional,
    Dict,
    Any,
    Callable,
    Union,
    Tuple,
    cast,
    ContextManager,
)

from docker import get_container_pid
from gdb import solib_search_paths, bind_gdb_exe, shadow_target_exe_dir_for_gdb
from namespaces import (
    unshare_and_mount_proc,
    nsenter_to_pid_ns_with_fork,
    two_processes_in_same_pid_namespace,
    pid_in_own_namespace,
)


def dump_heap(args: argparse.Namespace) -> int:
    target_pid: int
    target_pid_in_ns: int
    nsenter_needed: bool
    if args.docker_container is not None:
        print("Target is Docker container")
        target_pid = get_container_pid(args.docker_container)
        target_pid_in_ns = 1
        print(
            f"Target process PID: {target_pid}, in its own namespace: {target_pid_in_ns}"
        )
        nsenter_needed = True
    elif two_processes_in_same_pid_namespace(args.pid, os.getpid()):
        print("Dumper and target are in same PID namespace")
        target_pid = args.pid
        target_pid_in_ns = target_pid
        nsenter_needed = False
    else:
        target_pid = args.pid
        target_pid_in_ns = pid_in_own_namespace(target_pid)
        print(f"Target process PID in its own namespace: {target_pid_in_ns}")
        nsenter_needed = True

    solid_search_paths = ":".join(solib_search_paths(target_pid, target_pid_in_ns))

    injector_code = _load_code("injector.py")
    dumper_code = _prepare_dumper_code()

    if nsenter_needed:
        nsenter_to_pid_ns_with_fork(target_pid)
        unshare_and_mount_proc()

    with ExitStack() as stack:
        dumper_temp_dir = stack.enter_context(TemporaryDirectory(prefix="pyheap-"))

        gdb_exe = os.path.realpath(shutil.which("gdb"))
        if nsenter_needed:
            gdb_exe = stack.enter_context(
                cast(ContextManager[str], bind_gdb_exe(gdb_exe, dumper_temp_dir))
            )

        if nsenter_needed:
            shadow_target_exe_dir_for_gdb(target_pid_in_ns, dumper_temp_dir)

        target_temp_dir = stack.enter_context(
            closing(TargetTemporaryDirectory(target_pid_in_ns))
        )
        progress_file = target_temp_dir.create_file("progress.json", 0o600)
        heap_file = target_temp_dir.create_file(f"{uuid.uuid4()}.pyheap", 0o600)

        # TODO exlpore solib-absolute-prefix vs solib-search-path

        print(f"Dumping heap from process {target_pid} into {args.file}")
        print(f"Max length of string representation is {args.str_repr_len}")

        cmd = [
            gdb_exe,
            "--readnow",
            "-iex",
            "set verbose on",
            "-iex",
            f"set sysroot /proc/{target_pid_in_ns}/root",
            "-iex",
            f"set auto-load safe-path {solid_search_paths}",
            "-iex",
            f"set solib-search-path {solid_search_paths}",
            "-iex",
            "set debuginfod enabled off",
            "-ex",
            "break _PyEval_EvalFrameDefault",
            "-ex",
            "continue",
            "-ex",
            "del 1",
            "-ex",
            f"python {injector_code}",
            "-ex",
            "set print elements 0",
            "-ex",
            "set max-value-size unlimited",
            "-ex",
            f'set $dump_success = $dump_python_heap("{dumper_code}", "{heap_file}", {args.str_repr_len}, "{progress_file}")',
            "-ex",
            "detach",
            "-ex",
            "quit $dump_success",
            "-p",
            str(target_pid_in_ns),
        ]
        p = Popen(cmd, shell=False)
        progress_tracker = ProgressTracker(
            progress_file=progress_file, should_continue=lambda: p.poll() is None
        )
        progress_tracker.track_progress()
        p.communicate()

        if p.returncode == 0:
            _move_heap_file(heap_file, args.file)
            return 0
        else:
            print("Dumping finished with error")
            return p.returncode


def _load_code(filename: str) -> str:
    if isinstance(__loader__, SourceFileLoader):
        filepath = str(Path(__loader__.path).parent / filename)
        return __loader__.get_data(filepath).decode("utf-8")
    else:
        return __loader__.get_data(filename).decode("utf-8")


def _prepare_dumper_code() -> str:
    code = _load_code("dumper_inferior.py")
    # Encode as hexadecimal characters (\x42), which is understandable by C.
    return "".join([hex(b).replace("0x", r"\\x") for b in code.encode("utf-8")])


@dataclass
class Progress:
    since_start_sec: float
    done: int
    remain: int

    @staticmethod
    def from_json(progress_json: Dict[str, Any]) -> Progress:
        return Progress(
            since_start_sec=progress_json["since_start_sec"],
            done=progress_json["done"],
            remain=progress_json["remain"],
        )


class TargetTemporaryDirectory:
    def __init__(self, target_pid: int) -> None:
        self._target_root_fs = f"/proc/{target_pid}/root"
        self._target_uid, self._target_gid = self._target_fs_uid_gid(target_pid)
        self._tempdir = TemporaryDirectory(
            prefix="pyheap-", dir=f"{self._target_root_fs}/tmp"
        )
        os.chown(self._tempdir.name, self._target_uid, self._target_gid)

    @staticmethod
    def _target_fs_uid_gid(target_pid: Union[int, str]) -> Tuple[int, int]:
        uid: Optional[int] = None
        gid: Optional[int] = None
        with open(f"/proc/{target_pid}/status", "r") as f:
            for l in f.readlines():
                l = l.strip()
                if l.startswith("Uid"):
                    uid = int(l.strip().split("\t")[-1])
                if l.startswith("Gid"):
                    gid = int(l.strip().split("\t")[-1])

                if uid is not None and gid is not None:
                    return uid, gid
            else:
                raise Exception("Cannot determine target process FS UID and GID")

    def create_file(self, name: str, mode: int) -> str:
        path = Path(self._tempdir.name) / name
        path.touch(mode=mode, exist_ok=False)
        os.chown(str(path), self._target_uid, self._target_gid)
        return str(path)

    def close(self) -> None:
        self._tempdir.cleanup()


class ProgressTracker:
    def __init__(
        self, *, progress_file: str, should_continue: Callable[[], bool]
    ) -> None:
        self._progress_file = progress_file
        self._should_continue = should_continue
        self._last_progress_displayed = -1

    def track_progress(self) -> None:
        first_iteration = True
        while first_iteration or self._should_continue():
            first_iteration = False

            progress = self._read_progress()
            if progress is not None:
                self._display(progress)

            time.sleep(0.1)

        progress = self._read_progress()
        if progress is not None:
            self._display(progress)

    def _read_progress(self) -> Optional[Progress]:
        progress: Optional[Progress] = None
        progress_file_path = self._progress_file
        try:
            with open(progress_file_path, "r") as f:
                content = f.read()
                # We check that the record is properly finalized as writes are not expected to be atomic.
                if content.endswith("\n"):
                    try:
                        progress = Progress.from_json(json.loads(content))
                    except json.decoder.JSONDecodeError:
                        pass  # intentionally no-op
        except OSError as e:
            print(f"Error reading progress file '{progress_file_path}': {e}")
        return progress

    def _display(self, progress: Progress) -> None:
        if progress.done > self._last_progress_displayed:
            self._last_progress_displayed = progress.done
            print(
                f"{progress.since_start_sec:.2f} seconds passed, "
                f"{progress.done} objects done, "
                f"{progress.remain} remain (more may be added)",
                end="\r",
            )


def _move_heap_file(heap_file: str, final_path: str) -> None:
    final_path_unambiguous = final_path
    i = -1
    while os.path.exists(final_path_unambiguous):
        i += 1
        final_path_unambiguous = f"{final_path}.{i}"
    print(f"Moving from {heap_file} to {final_path_unambiguous}")
    shutil.move(heap_file, final_path_unambiguous)
    print(f"Heap file saved: {final_path_unambiguous}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump heap.", allow_abbrev=False)

    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--pid", "-p", type=int, help="target process PID")
    target_group.add_argument(
        "--docker-container", type=str, help="target Docker container"
    )

    parser.add_argument("--file", "-f", type=str, required=True, help="heap file name")
    parser.add_argument(
        "--str-repr-len",
        type=int,
        required=False,
        help="max length of string representation of objects (-1 disables it)",
        default=1000,
    )
    parser.set_defaults(func=dump_heap)

    args = parser.parse_args()
    try:
        return_code = args.func(args)
    except SystemExit as e:
        exit(e.code)
    except:
        import traceback

        traceback.print_exc()
        exit(1)
    else:
        exit(return_code)


if __name__ == "__main__":
    main()
