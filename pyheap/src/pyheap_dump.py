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
import subprocess
import uuid
from contextlib import closing
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
from subprocess import Popen
import tempfile
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Union, Tuple


def dump_heap(args: argparse.Namespace) -> None:
    target_pid: int
    gdb_pid: int
    nsenter_needed: bool
    if args.docker_container is not None:
        print("Target is Docker container")
        target_pid = _get_container_pid(args.docker_container)
        gdb_pid = 1
        nsenter_needed = True
    elif _pid_namespace(args.pid) == _pid_namespace(os.getpid()):
        print("Dumper and target are in same PID namespace")
        target_pid = args.pid
        gdb_pid = target_pid
        nsenter_needed = False
    else:
        target_pid = args.pid
        gdb_pid = _target_pid_in_own_namespace(args.pid)
        print(f"Target process PID in its namespace: {gdb_pid}")
        nsenter_needed = True

    print(f"Dumping heap from process {target_pid} into {args.file}")
    print(f"Max length of string representation is {args.str_repr_len}")

    injector_code = _load_code("injector.py")
    dumper_code = _prepare_dumper_code()

    tmp_dir: CrossNamespaceTmpDir
    progress_file: CrossNamespaceFile
    heap_file: CrossNamespaceFile
    with closing(CrossNamespaceTmpDir(target_pid)) as tmp_dir, closing(
        tmp_dir.create_file("progress.json", 0o600)
    ) as progress_file, closing(
        tmp_dir.create_file(f"{uuid.uuid4()}.pyheap", 0o600)
    ) as heap_file:
        cmd = []
        if nsenter_needed:
            cmd += ["nsenter", "-t", str(target_pid), "-a"]
        cmd += [
            "gdb",
            "--readnow",
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
            f'set $dump_success = $dump_python_heap("{dumper_code}", "{heap_file.target_path}", {args.str_repr_len}, "{progress_file.target_path}")',
            "-ex",
            "detach",
            "-ex",
            "quit $dump_success",
            "-p",
            str(gdb_pid),
        ]
        p = Popen(cmd, shell=False)
        progress_tracker = ProgressTracker(
            progress_file=progress_file, should_continue=lambda: p.poll() is None
        )
        progress_tracker.track_progress()
        p.communicate()

        if p.returncode != 0:
            print("Dumping finished with error")
        else:
            _move_heap_file(heap_file, args.file)

    exit(p.returncode)


def _get_container_pid(container: str) -> int:
    proc = subprocess.run(
        ["docker", "inspect", container],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        print("Cannot determine target PID:")
        print(f"`docker inspect {container}` returned:")
        print(proc.stderr)
        exit(1)

    inspect_obj = json.loads(proc.stdout)
    if len(inspect_obj) != 1:
        print("Cannot determine target PID:")
        print(
            f"Expected 1 object in `docker inspect {container}`, but got {len(inspect_obj)}"
        )
        exit(1)

    state = inspect_obj[0]["State"]
    if state["Status"] != "running":
        print("Cannot determine target PID:")
        print(f"Container is not running")
        exit(1)

    pid = int(state["Pid"])
    print(f"Target PID: {pid}")
    return pid


def _pid_namespace(pid: Union[int, str]) -> str:
    try:
        return os.readlink(f"/proc/{pid}/ns/pid")
    except PermissionError as e:
        print(e)
        print("Hint: the target process is likely run under a different user, use sudo")
        exit(1)


def _target_pid_in_own_namespace(target_pid: Union[int, str]) -> int:
    with open(f"/proc/{target_pid}/status", "r") as f:
        for l in f.readlines():
            l = l.strip()
            if l.startswith("NStgid"):
                return int(l.split("\t")[-1].strip())
        else:
            print("Cannot determine target process PID in its namespace")
            exit(1)


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


class CrossNamespaceTmpDir:
    def __init__(self, target_pid: int) -> None:
        self._target_root_fs = f"/proc/{target_pid}/root"
        self._target_uid, self._target_gid = self._target_fs_uid_gid(target_pid)
        self._path = tempfile.mkdtemp(
            prefix="pyheap-", dir=f"{self._target_root_fs}/tmp"
        )
        os.chown(self._path, self._target_uid, self._target_gid)

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

    def create_file(self, name: str, mode: int) -> CrossNamespaceFile:
        dumper_path = os.path.join(self._path, name)
        path_obj = Path(dumper_path)
        path_obj.touch(mode=mode, exist_ok=False)
        os.chown(dumper_path, self._target_uid, self._target_gid)
        target_path = "/" + str(path_obj.relative_to(self._target_root_fs))
        return CrossNamespaceFile(dumper_path=dumper_path, target_path=target_path)

    def close(self) -> None:
        try:
            os.rmdir(self._path)
        except OSError as e:  # not exist or not empty
            print(f"Cannot delete {self._path}: {e}")


class CrossNamespaceFile:
    def __init__(self, dumper_path: str, target_path: str) -> None:
        self._dumper_path = dumper_path
        self._target_path = target_path

    @property
    def dumper_path(self) -> str:
        return self._dumper_path

    @property
    def target_path(self) -> str:
        return self._target_path

    def close(self) -> None:
        try:
            os.remove(self._dumper_path)
        except FileNotFoundError:
            pass  # it's ok if it doesn't exist already
        except OSError as e:
            print(f"Cannot delete {self._dumper_path}: {e}")


class ProgressTracker:
    def __init__(
        self, *, progress_file: CrossNamespaceFile, should_continue: Callable[[], bool]
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
        progress_file_path = self._progress_file.dumper_path
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


def _move_heap_file(heap_file: CrossNamespaceFile, final_path: str) -> None:
    final_path_unambiguous = final_path
    i = -1
    while os.path.exists(final_path_unambiguous):
        i += 1
        final_path_unambiguous = f"{final_path}.{i}"
    print(f"Moving from {heap_file.dumper_path} to {final_path_unambiguous}")
    shutil.move(heap_file.dumper_path, final_path_unambiguous)
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
    args.func(args)


if __name__ == "__main__":
    main()
