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
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
from subprocess import Popen
import tempfile
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Union


def dump_heap(args: argparse.Namespace) -> None:
    gdb_pid: int
    nsenter_needed: bool
    if _pid_namespace(args.pid) == _pid_namespace(os.getpid()):
        print("Dumper and target are in same PID namespace")
        gdb_pid = args.pid
        nsenter_needed = False
    else:
        gdb_pid = _target_pid_in_own_namespace(args.pid)
        print(f"Target process PID in its namespace: {gdb_pid}")
        nsenter_needed = True

    heap_file_path = args.file
    print(f"Dumping heap from process {args.pid} into {heap_file_path}")
    print(f"Max length of string representation is {args.str_repr_len}")

    injector_code = _load_code("injector.py")
    dumper_code = _prepare_dumper_code()

    try:
        progress_file_path = os.path.join(
            tempfile.mkdtemp(prefix="pyheap-"), "progress.json"
        )
        Path(progress_file_path).touch(mode=0o622, exist_ok=False)  # rw--w--w-
    except OSError as e:
        print(f"Error creating progress file: {e}, progress will not be reported")
        progress_file_path = ""

    cmd = []
    if nsenter_needed:
        cmd += ["nsenter", "-t", str(args.pid), "-a"]
    cmd += [
        "gdb",
        "--readnow",
        "-ex",
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
        f'set $dump_success = $dump_python_heap("{dumper_code}", "{heap_file_path}", {args.str_repr_len}, "{progress_file_path}")',
        "-ex",
        "detach",
        "-ex",
        "quit $dump_success",
        "-p",
        str(gdb_pid),
    ]
    p = Popen(cmd, shell=False)
    progress_tracker = ProgressTracker(
        progress_file_path=progress_file_path, should_continue=lambda: p.poll() is None
    )
    progress_tracker.track_progress()
    p.communicate()

    if progress_file_path:
        try:
            os.remove(progress_file_path)
        except OSError as e:
            print(f"Error deleting progress file '{progress_file_path}': {e}")

    if p.returncode != 0:
        print("Dumping finished with error")
    exit(p.returncode)


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


class ProgressTracker:
    def __init__(
        self, *, progress_file_path: str, should_continue: Callable[[], bool]
    ) -> None:
        self._progress_file_path = progress_file_path
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

        if not self._progress_file_path:
            return progress

        try:
            with open(self._progress_file_path, "r") as f:
                content = f.read()
                # We check that the record is properly finalized as writes are not expected to be atomic.
                if content.endswith("\n"):
                    try:
                        progress = Progress.from_json(json.loads(content))
                    except json.decoder.JSONDecodeError:
                        pass  # intentionally no-op
        except OSError as e:
            print(f"Error reading progress file '{self._progress_file_path}': {e}")
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump heap.", allow_abbrev=False)
    parser.add_argument(
        "--pid", "-p", type=int, required=True, help="target process PID"
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
