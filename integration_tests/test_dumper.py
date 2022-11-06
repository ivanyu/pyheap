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
import inspect
import mmap
import os
import subprocess
import sys
from contextlib import closing
from datetime import datetime, timezone
from threading import Thread
from unittest.mock import ANY
from pathlib import Path
import dateutil.parser
import pytest
from pyheap_ui.heap_reader import HeapReader
from pyheap_ui.heap_types import HeapThread, HeapObject, Heap

_ATTRS_FOR_INT = set(dir(1))
_ATTRS_FOR_FLOAT = set(dir(1.0))
_ATTRS_FOR_STR = set(dir(""))


@pytest.mark.parametrize("dump_str_repr", [True, False])
def test_dumper(tmp_path: Path, dump_str_repr: bool) -> None:
    heap_file = str(tmp_path / "test_heap.pyheap")
    mock_inferior_file = str(Path(__file__).parent / "resources" / "mock_inferior.py")
    r = subprocess.run(
        ["python", mock_inferior_file, heap_file, str(dump_str_repr)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    print(r.stdout.decode("utf-8"))
    print(r.stderr.decode("utf-8"))

    # Not all errors may be propagated as return code
    assert r.returncode == 0
    assert not r.stdout
    assert not r.stderr

    try:
        with open(heap_file, "rb") as f:
            mm = mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)
            with closing(mm):
                reader = HeapReader(mm)
                heap = reader.read()

                # Check that we have read everything.
                assert reader._offset == mm.size()

                _check_threads_and_objects(heap, mock_inferior_file, dump_str_repr)
                _check_header(heap, dump_str_repr)
                _check_common_types(heap, reader)
    finally:
        os.remove(heap_file)


def _check_threads_and_objects(
    heap: Heap, mock_inferior_file: str, dump_str_repr: bool
) -> None:
    _check_no_pyheap_frames(heap)

    under_debugger = sys.gettrace() is not None
    python_3_11 = (sys.version_info.major, sys.version_info.minor) == (3, 11)
    assert len(heap.threads) == (2 if not under_debugger or python_3_11 else 5)

    main_thread = next(t for t in heap.threads if t.name == "MainThread")
    assert main_thread == HeapThread(
        name="MainThread", is_alive=True, is_daemon=False, stack_trace=ANY
    )

    assert len(main_thread.stack_trace) == (
        4 if not under_debugger or python_3_11 else 9
    )

    frame = main_thread.stack_trace[0]
    assert frame.co_filename == mock_inferior_file
    assert frame.lineno == 95
    assert frame.co_name == "function3"
    assert set(frame.locals.keys()) == {
        "a",
        "f",
        "code",
        "dumper_path",
        "progress_file_path",
    }

    obj = heap.objects[frame.locals["a"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "int"), size=28, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_INT
    assert obj.str_repr == ("42" if dump_str_repr else None)

    obj = heap.objects[frame.locals["dumper_path"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "str"), size=110, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_STR
    assert obj.str_repr == (
        str(Path(__file__).parent.parent / "pyheap" / "src" / "dumper_inferior.py")
        if dump_str_repr
        else None
    )

    assert heap.objects[frame.locals["code"]].type == _find_type_by_name(heap, "code")

    frame = main_thread.stack_trace[1]
    assert frame.co_filename == mock_inferior_file
    assert frame.lineno == 107
    assert frame.co_name == "function2"
    assert set(frame.locals.keys()) == {"a", "b"}
    obj = heap.objects[frame.locals["a"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "int"), size=28, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_INT
    assert obj.str_repr == ("42" if dump_str_repr else None)

    obj = heap.objects[frame.locals["b"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "str"), size=53, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_STR
    assert obj.str_repr == ("leaf" if dump_str_repr else None)

    frame = main_thread.stack_trace[2]
    assert frame.co_filename == mock_inferior_file
    assert frame.lineno == 111
    assert frame.co_name == "function1"
    assert set(frame.locals.keys()) == {"a", "b", "c"}

    obj = heap.objects[frame.locals["a"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "int"), size=28, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_INT
    assert obj.str_repr == ("42" if dump_str_repr else None)

    obj = heap.objects[frame.locals["b"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "str"), size=53, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_STR
    assert obj.str_repr == ("leaf" if dump_str_repr else None)

    obj = heap.objects[frame.locals["c"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "float"), size=24, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_FLOAT
    assert obj.str_repr == ("12.5" if dump_str_repr else None)

    frame = main_thread.stack_trace[3]
    assert frame.co_filename == mock_inferior_file
    assert frame.lineno == 114
    assert frame.co_name == "<module>"
    expected_locals = {
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
        "os",
        "tempfile",
        "dump_str_repr",
        "time",
        "Path",
        "Any",
        "NoReturn",
        "Thread",
        "Event",
        "heap_file",
        "MyThread",
        "my_thread",
        "DisabledOperations",
        "disabled_operations",
        "some_string",
        "some_list",
        "some_tuple",
        "function3",
        "function2",
        "function1",
    }
    if under_debugger:
        expected_locals.remove("__cached__")
        expected_locals.remove("__annotations__")
    assert set(frame.locals.keys()) == expected_locals
    obj = heap.objects[frame.locals["some_string"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "str"), size=60, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_STR
    assert obj.str_repr == ("hello world" if dump_str_repr else None)

    obj = heap.objects[frame.locals["disabled_operations"]]
    disabled_operations_type = _find_type_by_name(heap, "DisabledOperations")
    assert obj == HeapObject(
        type=disabled_operations_type, size=0, referents={disabled_operations_type}
    )
    assert obj.attributes == {}
    assert obj.str_repr == ("<ERROR on __str__>" if dump_str_repr else None)

    obj = heap.objects[frame.locals["some_list"]]
    # assert obj.address == frame.locals["some_list"]
    assert obj.type == _find_type_by_name(heap, "list")
    assert obj.size in {120, 88, 80}  # depends on Python version
    assert obj.str_repr == ("[1, 2, 3]" if dump_str_repr else None)
    if dump_str_repr:
        assert {heap.objects[r].str_repr for r in obj.referents} == {"1", "2", "3"}
    else:
        assert {heap.objects[r].str_repr for r in obj.referents} == {None}

    obj = heap.objects[frame.locals["some_tuple"]]
    # assert obj.address == frame.locals["some_tuple"]
    assert obj.type == _find_type_by_name(heap, "tuple")
    assert obj.size == 64
    assert obj.str_repr == ("('a', 'b', 'c')" if dump_str_repr else None)
    if dump_str_repr:
        assert {heap.objects[r].str_repr for r in obj.referents} == {"a", "b", "c"}
    else:
        assert {heap.objects[r].str_repr for r in obj.referents} == {None}

    # Check some attributes of an object.
    obj = heap.objects[frame.locals["my_thread"]]
    # Should have the same attributes that a normal Thread + some specific.
    expected_attrs = set(dir(Thread()))
    expected_attrs.update({"_thread_inner", "reached"})
    if under_debugger:
        expected_attrs.update(
            {"__pydevd_id__", "_top_level_thread_tracer", "_tracer", "additional_info"}
        )
    assert set(obj.attributes) == expected_attrs
    if dump_str_repr:
        assert heap.objects[obj.attributes["setDaemon"]].str_repr.startswith(
            "<function Thread.setDaemon"
        )
        assert heap.objects[obj.attributes["_name"]].str_repr == "MyThread"

    second_thread = next(t for t in heap.threads if t.name == "MyThread")
    assert second_thread == HeapThread(
        name="MyThread", is_alive=True, is_daemon=True, stack_trace=ANY
    )

    assert len(second_thread.stack_trace) == (4 if not under_debugger else 5)

    frame = second_thread.stack_trace[0]
    assert frame.co_filename == mock_inferior_file
    assert frame.lineno == 65
    assert frame.co_name == "_thread_inner"
    assert set(frame.locals.keys()) == {
        "self",
        "local_1",
        "local_2",
    }
    obj = heap.objects[frame.locals["local_1"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "str"), size=62, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_STR
    assert obj.str_repr == ("local_1 value" if dump_str_repr else None)

    obj = heap.objects[frame.locals["local_2"]]
    # assert obj.address == frame.locals["local_2"]
    assert obj.type == _find_type_by_name(heap, "list")
    assert obj.size == 64
    assert obj.str_repr == ("['local_2 value']" if dump_str_repr else None)
    if dump_str_repr:
        assert {heap.objects[r].str_repr for r in obj.referents} == {"local_2 value"}
    else:
        assert {heap.objects[r].str_repr for r in obj.referents} == {None}

    frame = second_thread.stack_trace[1]
    assert frame.co_filename == mock_inferior_file
    assert frame.lineno == 68
    assert frame.co_name == "run"
    assert set(frame.locals.keys()) == {"self", "__class__"}

    assert second_thread.stack_trace[2].co_filename.endswith("threading.py")
    assert second_thread.stack_trace[3].co_filename.endswith("threading.py")

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
        assert t in heap.types.values()


def _check_no_pyheap_frames(heap: Heap) -> None:
    assert not [
        f for t in heap.threads for f in t.stack_trace if f.co_filename == "<string>"
    ]


def _find_type_by_name(heap: Heap, type_name: str) -> int:
    for type_address, type_name0 in heap.types.items():
        if type_name0 == type_name:
            return int(type_address)
    else:
        raise ValueError("not found")


def _check_header(heap: Heap, dump_str_repr: bool) -> None:
    assert heap.header.version == 1
    x = dateutil.parser.isoparse(heap.header.created_at)
    assert (datetime.now(timezone.utc) - x).total_seconds() < 5 * 60
    assert heap.header.flags.with_str_repr is dump_str_repr


def _check_common_types(heap: Heap, reader: HeapReader) -> None:
    expected_common_types_with_examples = {
        int: 0,
        float: 0.0,
        bool: False,
        str: "",
        bytes: b"",
        list: [],
        set: set(),
        dict: {},
    }
    assert len(expected_common_types_with_examples.keys()) == len(
        reader._common_types.keys()
    )

    for type_, example in expected_common_types_with_examples.items():
        type_name = type_.__name__
        type_address = _find_type_by_name(heap, type_name)
        assert heap.types[type_address] == type_name

        common_type = reader._common_types[_find_type_by_name(heap, type_name)]

        object_in_heap = next(
            o for o in heap.objects.values() if o.type == type_address
        )

        assert list(common_type.attributes.keys()) == dir(example)
        for attr in dir(example):
            attr_value = inspect.getattr_static(example, attr)
            assert (
                type(attr_value).__name__
                == heap.types[heap.objects[object_in_heap.attributes[attr]].type]
            )
