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
import json
import subprocess
from pathlib import Path
from typing import Mapping, Any


def test_dumper(tmp_path: Path) -> None:
    heap_file = str(tmp_path / "test_heap.json")
    mock_inferior_file = str(Path(__file__).parent / "resources" / "mock_inferior.py_")
    r = subprocess.run(["python", mock_inferior_file, heap_file])
    assert r.returncode == 0

    with open(heap_file, "r") as f:
        heap = json.load(f)

    assert "threads" in heap
    assert "objects" in heap
    assert "types" in heap

    threads = heap["threads"]
    # This will fail in PyCharm debugging.
    assert len(threads) == 2

    main_thread = next(t for t in threads if t["thread_name"] == "MainThread")
    assert main_thread["thread_name"] == "MainThread"
    assert main_thread["alive"] is True
    assert main_thread["daemon"] is False

    assert len(main_thread["stack_trace"]) == 4

    frame = main_thread["stack_trace"][0]
    assert frame["file"] == mock_inferior_file
    assert frame["lineno"] == 54
    assert frame["name"] == "function3"
    assert set(frame["locals"].keys()) == {
        "a",
        "dumper_dir",
        "dumper",
    }
    _assert_object(
        heap,
        frame["locals"]["a"],
        {"type": "int", "size": 28, "str": "42", "referents": []},
    )
    _assert_object(
        heap,
        frame["locals"]["dumper_dir"],
        {
            "type": "str",
            "size": 87,
            "str": str(Path(__file__).parent.parent.parent / "pyheap"),
            "referents": [],
        },
    )
    assert _get_object(heap, frame["locals"]["dumper"])["type"] == "module"

    frame = main_thread["stack_trace"][1]
    assert frame["file"] == mock_inferior_file
    assert frame["lineno"] == 58
    assert frame["name"] == "function2"
    assert set(frame["locals"].keys()) == {"a", "b"}
    _assert_object(
        heap,
        frame["locals"]["a"],
        {"type": "int", "size": 28, "str": "42", "referents": []},
    )
    _assert_object(
        heap,
        frame["locals"]["b"],
        {"type": "str", "size": 53, "str": "leaf", "referents": []},
    )

    frame = main_thread["stack_trace"][2]
    assert frame["file"] == mock_inferior_file
    assert frame["lineno"] == 62
    assert frame["name"] == "function1"
    assert set(frame["locals"].keys()) == {"a", "b", "c"}
    _assert_object(
        heap,
        frame["locals"]["a"],
        {"type": "int", "size": 28, "str": "42", "referents": []},
    )
    _assert_object(
        heap,
        frame["locals"]["b"],
        {"type": "str", "size": 53, "str": "leaf", "referents": []},
    )
    _assert_object(
        heap,
        frame["locals"]["c"],
        {"type": "float", "size": 24, "str": "12.5", "referents": []},
    )

    frame = main_thread["stack_trace"][3]
    assert frame["file"] == mock_inferior_file
    assert frame["lineno"] == 65
    assert frame["name"] == "<module>"
    assert set(frame["locals"].keys()) == {
        "__name__",
        "__doc__",
        "__package__",
        "__loader__",
        "__spec__",
        "__annotations__",
        "__builtins__",
        "__file__",
        "__cached__",
        "sys",
        "time",
        "Path",
        "Thread",
        "Event",
        "heap_file",
        "MyThread",
        "my_thread",
        "some_string",
        "some_list",
        "some_tuple",
        "function3",
        "function2",
        "function1",
    }
    _assert_object(
        heap,
        frame["locals"]["some_string"],
        {"type": "str", "size": 60, "str": "hello world", "referents": []},
    )

    obj = _get_object(heap, frame["locals"]["some_list"])
    assert obj["address"] == frame["locals"]["some_list"]
    assert obj["type"] == "list"
    assert obj["size"] in {120, 88}  # depends on Python minor version
    assert obj["str"] == "[1, 2, 3]"
    assert {_get_object(heap, r)["str"] for r in obj["referents"]} == {"1", "2", "3"}

    obj = _get_object(heap, frame["locals"]["some_tuple"])
    assert obj["address"] == frame["locals"]["some_tuple"]
    assert obj["type"] == "tuple"
    assert obj["size"] == 64
    assert obj["str"] == "('a', 'b', 'c')"
    assert {_get_object(heap, r)["str"] for r in obj["referents"]} == {"a", "b", "c"}

    second_thread = next(t for t in threads if t["thread_name"] != "MainThread")
    assert second_thread["thread_name"] == "MyThread"
    assert second_thread["alive"] is True
    assert second_thread["daemon"] is True

    assert len(second_thread["stack_trace"]) == 4

    frame = second_thread["stack_trace"][0]
    assert frame["file"] == mock_inferior_file
    assert frame["lineno"] == 31
    assert frame["name"] == "_thread_inner"
    assert set(frame["locals"].keys()) == {
        "self",
        "local_1",
        "local_2",
    }
    _assert_object(
        heap,
        frame["locals"]["local_1"],
        {"type": "str", "size": 62, "str": "local_1 value", "referents": []},
    )

    obj = _get_object(heap, frame["locals"]["local_2"])
    assert obj["address"] == frame["locals"]["local_2"]
    assert obj["type"] == "list"
    assert obj["size"] == 64
    assert obj["str"] == "['local_2 value']"
    assert {_get_object(heap, r)["str"] for r in obj["referents"]} == {"local_2 value"}

    assert second_thread["stack_trace"][1]["file"] == mock_inferior_file
    assert second_thread["stack_trace"][1]["lineno"] == 34
    assert second_thread["stack_trace"][1]["name"] == "run"
    assert set(second_thread["stack_trace"][1]["locals"].keys()) == {
        "self",
        "__class__",
    }

    assert second_thread["stack_trace"][2]["file"].endswith("threading.py")
    assert second_thread["stack_trace"][3]["file"].endswith("threading.py")

    # Test some types to be present.
    expected_types = {
        "type",
        "int",
        "float",
        "str",
        "bytes",
        "bool",
        "tuple",
        "list",
        "set",
        "dict",
        "NoneType",
        "object",
        "module",
        "code",
        "function",
        "builtin_function_or_method",
        "method",
        "cell",
        "property",
        "classmethod",
        "staticmethod",
        "MyThread",
    }
    for t in expected_types:
        assert t in heap["types"].values()


def _get_object(heap: Mapping[str, Any], addr: int) -> Mapping[str, Any]:
    return heap["objects"][str(addr)]


def _assert_object(
    heap: Mapping[str, Any], addr: int, expected: Mapping[str, Any]
) -> None:
    actual = dict(heap["objects"][str(addr)])
    expected_with_adds = dict(expected)
    expected_with_adds["address"] = addr
    assert actual == expected_with_adds
