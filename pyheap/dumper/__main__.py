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
import argparse
import os.path
import subprocess
from pathlib import Path


def dump_heap(args: argparse.Namespace) -> None:
    abs_file_path = os.path.abspath(args.file)
    print(f"Dumping heap from process {args.pid} into {abs_file_path}")
    print(f"Max length of string representation is {args.string_length}")

    code_path = Path(__file__).parent
    injector_path = code_path / "injector.py"
    print(f"Code path: {code_path}")
    print(f"Injector path: {injector_path}")

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
        f'print $dump_python_heap("{code_path}", "{abs_file_path}", {args.string_length})',
        "-ex",
        "detach",
        "-ex",
        "quit",
        "-p",
        str(args.pid),
    ]
    result = subprocess.run(cmd, capture_output=True, check=True, encoding="utf-8")
    print(result.stdout)
    print(result.stderr)


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
