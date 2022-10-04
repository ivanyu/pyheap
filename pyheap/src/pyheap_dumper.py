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
from subprocess import Popen
import tempfile
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable


def dump_heap(args: argparse.Namespace) -> None:
    abs_file_path = os.path.abspath(args.file)
    print(f"Dumping heap from process {args.pid} into {abs_file_path}")
    print(f"Max length of string representation is {args.string_length}")

    module_path = Path(__file__).parent
    dumper_inferior_path = module_path / "dumper_inferior.py"
    injector_path = module_path / "injector.py"
    print(f"Code path: {dumper_inferior_path}")
    print(f"Injector path: {injector_path}")

    progress_file_path = os.path.join(
        tempfile.mkdtemp(prefix="pyheap-"), "progress.json"
    )
    Path(progress_file_path).touch(mode=0o622, exist_ok=False)  # rw--w--w-

    cmd = [
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
        f"source {injector_path}",
        "-ex",
        "set print elements 0",
        "-ex",
        f'print $dump_python_heap("{dumper_inferior_path}", "{abs_file_path}", {args.string_length}, "{progress_file_path}")',
        "-ex",
        "detach",
        "-ex",
        "quit",
        "-p",
        str(args.pid),
    ]
    p = Popen(cmd, shell=False)
    progress_tracker = ProgressTracker(
        progress_file_path=progress_file_path, should_continue=lambda: p.poll() is None
    )
    progress_tracker.track_progress()
    p.communicate()
    os.remove(progress_file_path)


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
        with open(self._progress_file_path, "r") as f:
            content = f.read()
            # We check that the record is properly finalized as writes are not expected to be atomic.
            if content.endswith("\n"):
                try:
                    progress = Progress.from_json(json.loads(content))
                except json.decoder.JSONDecodeError:
                    pass  # intentionally no-op
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dump heap.", allow_abbrev=False)
    parser.add_argument(
        "--pid", "-p", type=int, required=True, help="target process PID"
    )
    parser.add_argument("--file", "-f", type=str, required=True, help="heap file name")
    parser.add_argument(
        "--string-length",
        type=int,
        required=False,
        help="length of string representations",
        default=1000,
    )
    parser.set_defaults(func=dump_heap)

    args = parser.parse_args()
    args.func(args)
