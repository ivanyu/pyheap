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
from typing import Iterator, List
import pytest
from _pytest.tmpdir import TempPathFactory
from pyheap_ui.heap_reader import HeapReader


def test_e2e_target_host_dumper_host(test_heap_path: str) -> None:
    with _target_process_host() as pid:
        _dumper_on_host_for_host(test_heap_path, pid)
        _check_heap_file(test_heap_path)


@pytest.mark.parametrize("target_docker_base", ["alpine", "debian", "ubuntu", "fedora"])
def test_e2e_target_docker_dumper_host(
    target_docker_base: str, test_heap_path: str
) -> None:
    with _target_process_docker(target_docker_base) as container_id:
        _dumper_on_host_for_docker(test_heap_path, container_id)
        _check_heap_file(test_heap_path)


def test_e2e_target_host_dumper_docker(test_heap_path: str) -> None:
    with _target_process_host() as pid:
        _dumper_on_docker_for_host(test_heap_path, pid)
        _check_heap_file(test_heap_path)


@pytest.mark.parametrize("target_docker_base", ["alpine", "debian", "ubuntu", "fedora"])
def test_e2e_target_docker_dumper_docker(
    target_docker_base: str, test_heap_path: str
) -> None:
    with _target_process_docker(target_docker_base) as container_id:
        _dumper_on_docker_for_docker(test_heap_path, container_id)
        _check_heap_file(test_heap_path)


@pytest.fixture(scope="function")
def test_heap_path(tmp_path_factory: TempPathFactory) -> str:
    r = tmp_path_factory.mktemp("pyheap-integration-test") / "heap.pyheap"
    try:
        yield r
    finally:
        os.remove(r)


def _check_heap_file(test_heap_path: str) -> None:
    assert os.path.exists(test_heap_path)
    with open(test_heap_path, "rb") as f:
        mm = mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)
        with closing(mm):
            reader = HeapReader(mm)
            reader.read()
            # Check that we have read everything.
            assert reader._offset == mm.size()


@contextmanager
def _target_process_host() -> Iterator[int]:
    inferior_proc = subprocess.Popen(
        [sys.executable, "inferior-simple.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="../test_inferiors",
    )
    time.sleep(1)
    try:
        yield inferior_proc.pid
    finally:
        inferior_proc.kill()


@contextmanager
def _target_process_docker(docker_base: str) -> Iterator[str]:
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    docker_proc = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--detach",
            f"ivanyu/pyheap-e2e-test-target:{docker_base}-{python_version}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if docker_proc.returncode != 0:
        print(docker_proc.stdout)
        print(docker_proc.stderr)
    assert docker_proc.returncode == 0

    container_id = docker_proc.stdout.strip()

    try:
        yield container_id
    finally:
        subprocess.check_call(["docker", "kill", container_id])


@contextmanager
def _dumper_on_host_for_host(test_heap_path: str, pid: int) -> None:
    cmd = [sys.executable, "../pyheap/dist/pyheap_dump"]
    cmd += ["--pid", str(pid)]
    cmd += ["--file", test_heap_path]
    _run_dumper(cmd, False, test_heap_path)


@contextmanager
def _dumper_on_host_for_docker(test_heap_path: str, container_id: str) -> None:
    cmd = ["sudo"]
    cmd += [sys.executable, "../pyheap/dist/pyheap_dump"]
    cmd += ["--docker-container", container_id]
    cmd += ["--file", test_heap_path]
    _run_dumper(cmd, True, test_heap_path)


@contextmanager
def _dumper_on_docker_for_host(test_heap_path: str, pid: int) -> None:
    test_heap_path_dir = Path(test_heap_path).parent
    cmd = [
        "docker",
        "run",
        "--rm",
        "--pid=host",
        "--cap-add=SYS_PTRACE",
        "--volume",
        f"{test_heap_path_dir}:/heap-dir",
        "ivanyu/pyheap-dumper",
        "--pid",
        str(pid),
        "--file",
        "/heap-dir/heap.pyheap",
    ]
    _run_dumper(cmd, True, test_heap_path)


@contextmanager
def _dumper_on_docker_for_docker(test_heap_path: str, container_id: str) -> None:
    test_heap_path_dir = Path(test_heap_path).parent
    cmd = ["docker", "run", "--rm"]
    cmd += [
        f"--pid=container:{container_id}",
        "--cap-add=SYS_PTRACE",
        "--volume",
        f"{test_heap_path_dir}:/heap-dir",
        "ivanyu/pyheap-dumper",
        "--pid",
        "1",
        "--file",
        "/heap-dir/heap.pyheap",
    ]
    _run_dumper(cmd, True, test_heap_path)


def _run_dumper(cmd: List[str], chown: bool, test_heap_path: str) -> None:
    print(cmd)
    dumper_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    try:
        dumper_proc.wait(10)
    except subprocess.TimeoutExpired as e:
        dumper_proc.kill()
        raise e

    if dumper_proc.returncode != 0:
        print(dumper_proc.stdout.read())
        print(dumper_proc.stderr.read())
    assert dumper_proc.returncode == 0

    if chown:
        subprocess.check_call(
            ["sudo", "chown", f"{os.getuid()}:{os.getgid()}", test_heap_path]
        )
