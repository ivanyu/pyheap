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
import hashlib
import json
import random
import string
from dataclasses import dataclass
from typing import Optional

import pytest
from pathlib import Path

from pyheap_ui.heap import RetainedHeap, RetainedHeapCache


@dataclass
class HeapFile:
    file_path: str
    digest: str


@pytest.fixture(scope="function")
def heap_file(tmp_path: Path) -> HeapFile:
    file_name = f"{tmp_path}/{''.join(random.choice(string.ascii_lowercase) for _ in range(10))}"

    content = b"""The Zen of Python, by Tim Peters
Beautiful is better than ugly.
Explicit is better than implicit.
Simple is better than complex.
Complex is better than complicated.
Flat is better than nested.
Sparse is better than dense.
Readability counts.
Special cases aren't special enough to break the rules.
Although practicality beats purity.
Errors should never pass silently.
Unless explicitly silenced.
In the face of ambiguity, refuse the temptation to guess.
There should be one-- and preferably only one --obvious way to do it.
Although that way may not be obvious at first unless you're Dutch.
Now is better than never.
Although never is often better than *right* now.
If the implementation is hard to explain, it's a bad idea.
If the implementation is easy to explain, it may be a good idea.
Namespaces are one honking great idea -- let's do more of those!
"""

    m = hashlib.sha1()
    with open(file_name, "wb") as f:
        f.write(content)
    m.update(content)
    return HeapFile(file_path=file_name, digest=m.hexdigest())


@pytest.mark.parametrize("set_cache_dir", [False, True])
def test_cache_not_exist(
    heap_file: HeapFile, set_cache_dir: bool, tmp_path: Path
) -> None:
    cache = RetainedHeapCache(
        heap_file.file_path, cache_dir=_cache_dir(set_cache_dir, tmp_path)
    )
    assert cache.load_if_cache_exists() is None


@pytest.mark.parametrize("set_cache_dir", [False, True])
def test_store(heap_file: HeapFile, set_cache_dir: bool, tmp_path: Path) -> None:
    retained_heap = RetainedHeap(
        object_retained_heap={111111: 42}, thread_retained_heap={"main": 100500}
    )

    cache_dir = _cache_dir(set_cache_dir, tmp_path)
    cache = RetainedHeapCache(heap_file.file_path, cache_dir=cache_dir)
    cache.store(retained_heap)

    with open(_expected_cache_file(heap_file, cache_dir), "r") as f:
        cache_content = json.load(f)
    assert cache_content == {"objects": {"111111": 42}, "threads": {"main": 100500}}


@pytest.mark.parametrize("set_cache_dir", [False, True])
def test_load(heap_file: HeapFile, set_cache_dir: bool, tmp_path: Path) -> None:
    object_retained_heap = {111111: 42}
    thread_retained_heap = {"main": 100500}
    retained_heap = RetainedHeap(
        object_retained_heap=object_retained_heap,
        thread_retained_heap=thread_retained_heap,
    )

    cache_dir = _cache_dir(set_cache_dir, tmp_path)
    with open(_expected_cache_file(heap_file, cache_dir), "w") as f:
        json.dump({"objects": object_retained_heap, "threads": thread_retained_heap}, f)

    cache = RetainedHeapCache(heap_file.file_path, cache_dir=cache_dir)
    assert cache.load_if_cache_exists() == retained_heap


@pytest.mark.parametrize("set_cache_dir", [False, True])
def test_store_and_load(
    heap_file: HeapFile, set_cache_dir: bool, tmp_path: Path
) -> None:
    object_retained_heap = {111111: 42}
    thread_retained_heap = {"main": 100500}
    retained_heap = RetainedHeap(
        object_retained_heap=object_retained_heap,
        thread_retained_heap=thread_retained_heap,
    )

    cache = RetainedHeapCache(
        heap_file.file_path, cache_dir=_cache_dir(set_cache_dir, tmp_path)
    )
    cache.store(retained_heap)

    cache = RetainedHeapCache(
        heap_file.file_path, cache_dir=_cache_dir(set_cache_dir, tmp_path)
    )
    assert cache.load_if_cache_exists() == retained_heap


def _expected_cache_file(heap_file: HeapFile, cache_dir: Optional[str]) -> str:
    suffix = f".{heap_file.digest}.{RetainedHeapCache.VERSION}.retained_heap"
    if cache_dir is None:
        return f"{heap_file.file_path}{suffix}"
    else:
        return str(Path(cache_dir) / f"{Path(heap_file.file_path).name}{suffix}")


def _cache_dir(set_cache_dir: bool, tmp_path: Path) -> Optional[str]:
    if set_cache_dir:
        d = tmp_path / "retained-heap-cache"
        d.mkdir(exist_ok=True)
        return str(tmp_path / "retained-heap-cache")
    else:
        return None
