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
import mmap
import os
import subprocess
import sys
import time
from contextlib import contextmanager, closing
from pathlib import Path
from typing import Iterator
import pytest
from pyheap_ui.heap_reader import HeapReader


def test_e2e(test_heap_path: str) -> None:
    with _inferior_process() as ip, _dumper_process(test_heap_path, ip.pid) as dp:
        print(f"Inferior process {ip.pid}")
        print(f"Dumper process {dp.pid}")
        dp.wait(10)
        assert dp.returncode == 0
        assert os.path.exists(test_heap_path)

        with open(test_heap_path, "rb") as f:
            mm = mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)
            with closing(mm):
                reader = HeapReader(mm)
                reader.read()
                # Check that we have read everything.
                assert reader._offset == mm.size()


@pytest.fixture
def test_heap_path(tmp_path: Path) -> str:
    r = tmp_path / "heap.pyheap"
    try:
        yield r
    finally:
        try:
            os.remove(r)
        except Exception as e:
            print(e)


@contextmanager
def _inferior_process() -> Iterator[subprocess.Popen]:
    inferior_proc = subprocess.Popen(
        [sys.executable, "inferior-simple.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="../test_inferiors",
    )
    time.sleep(1)
    try:
        yield inferior_proc
    finally:
        inferior_proc.kill()


@contextmanager
def _dumper_process(
    test_heap_path: str, inferiod_pid: int
) -> Iterator[subprocess.Popen]:
    dumper_proc = subprocess.Popen(
        [
            sys.executable,
            "dist/pyheap_dumper.pyz",
            "--pid",
            str(inferiod_pid),
            "--file",
            test_heap_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="../pyheap",
    )
    try:
        yield dumper_proc
    finally:
        dumper_proc.kill()
        out, err = dumper_proc.communicate(timeout=5)
        print(out.decode("utf-8"))
        print(err.decode("utf-8"))
