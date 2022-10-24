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
from datetime import datetime, timezone
from unittest.mock import ANY
from pathlib import Path
import dateutil.parser
from pyheap_ui.heap_reader import HeapReader
from pyheap_ui.heap_types import HeapThread, HeapObject, Heap

_ATTRS_FOR_INT = set(dir(1))
_ATTRS_FOR_FLOAT = set(dir(1.0))
_ATTRS_FOR_STR = set(dir(""))


def test_dumper(tmp_path: Path) -> None:
    heap_file = str(tmp_path / "test_heap.pyheap")
    mock_inferior_file = str(Path(__file__).parent / "resources" / "mock_inferior.py")
    r = subprocess.run(["python", mock_inferior_file, heap_file])
    assert r.returncode == 0  # not all errors may be propagated as return code

    try:
        with open(heap_file, "rb") as f:
            mm = mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)
            reader = HeapReader(mm)
            heap = reader.read()

            # Check that we have read everything.
            assert reader._offset == mm.size()
    finally:
        os.remove(heap_file)

    assert heap.header.version == 1
    x = dateutil.parser.isoparse(heap.header.created_at)
    assert (datetime.now(timezone.utc) - x).total_seconds() < 5 * 60
    assert heap.header.flags.str_repr_present is True

    under_debugger = sys.gettrace() is not None
    assert len(heap.threads) == (2 if not under_debugger else 5)

    main_thread = next(t for t in heap.threads if t.name == "MainThread")
    assert main_thread == HeapThread(
        name="MainThread", is_alive=True, is_daemon=False, stack_trace=ANY
    )

    assert len(main_thread.stack_trace) == (7 if not under_debugger else 12)

    frame = main_thread.stack_trace[0]
    assert frame.co_filename.endswith("/runpy.py")
    frame = main_thread.stack_trace[1]
    assert frame.co_filename.endswith("/runpy.py")
    frame = main_thread.stack_trace[2]
    assert frame.co_filename.endswith("/runpy.py")
    assert frame.co_name == "run_path"

    frame = main_thread.stack_trace[3]
    assert frame.co_filename == mock_inferior_file
    assert frame.lineno == 62
    assert frame.co_name == "function3"
    assert set(frame.locals.keys()) == {
        "a",
        "dumper_path",
        "runpy",
        "progress_file_path",
    }

    obj = heap.objects[frame.locals["a"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "int"), size=28, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_INT
    assert obj.str_repr == "42"

    obj = heap.objects[frame.locals["dumper_path"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "str"), size=110, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_STR
    assert obj.str_repr == str(
        Path(__file__).parent.parent / "pyheap" / "src" / "dumper_inferior.py"
    )

    assert heap.objects[frame.locals["runpy"]].type == _find_type_by_name(
        heap, "module"
    )

    frame = main_thread.stack_trace[4]
    assert frame.co_filename == mock_inferior_file
    assert frame.lineno == 73
    assert frame.co_name == "function2"
    assert set(frame.locals.keys()) == {"a", "b"}
    obj = heap.objects[frame.locals["a"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "int"), size=28, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_INT
    assert obj.str_repr == "42"

    obj = heap.objects[frame.locals["b"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "str"), size=53, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_STR
    assert obj.str_repr == "leaf"

    frame = main_thread.stack_trace[5]
    assert frame.co_filename == mock_inferior_file
    assert frame.lineno == 77
    assert frame.co_name == "function1"
    assert set(frame.locals.keys()) == {"a", "b", "c"}

    obj = heap.objects[frame.locals["a"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "int"), size=28, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_INT
    assert obj.str_repr == "42"

    obj = heap.objects[frame.locals["b"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "str"), size=53, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_STR
    assert obj.str_repr == "leaf"

    obj = heap.objects[frame.locals["c"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "float"), size=24, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_FLOAT
    assert obj.str_repr == "12.5"

    frame = main_thread.stack_trace[6]
    assert frame.co_filename == mock_inferior_file
    assert frame.lineno == 80
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
        "time",
        "Path",
        "Any",
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
    if under_debugger:
        expected_locals.remove("__cached__")
        expected_locals.remove("__annotations__")
    assert set(frame.locals.keys()) == expected_locals
    obj = heap.objects[frame.locals["some_string"]]
    assert obj == HeapObject(
        type=_find_type_by_name(heap, "str"), size=60, referents=set()
    )
    assert obj.attributes.keys() == _ATTRS_FOR_STR
    assert obj.str_repr == "hello world"

    obj = heap.objects[frame.locals["some_list"]]
    # assert obj.address == frame.locals["some_list"]
    assert obj.type == _find_type_by_name(heap, "list")
    assert obj.size in {120, 88, 80}  # depends on Python version
    assert obj.str_repr == "[1, 2, 3]"
    assert {heap.objects[r].str_repr for r in obj.referents} == {"1", "2", "3"}

    obj = heap.objects[frame.locals["some_tuple"]]
    # assert obj.address == frame.locals["some_tuple"]
    assert obj.type == _find_type_by_name(heap, "tuple")
    assert obj.size == 64
    assert obj.str_repr == "('a', 'b', 'c')"
    assert {heap.objects[r].str_repr for r in obj.referents} == {"a", "b", "c"}

    second_thread = next(t for t in heap.threads if t.name == "MyThread")
    assert second_thread == HeapThread(
        name="MyThread", is_alive=True, is_daemon=True, stack_trace=ANY
    )

    assert len(second_thread.stack_trace) == (4 if not under_debugger else 5)

    frame = second_thread.stack_trace[0]
    assert frame.co_filename == mock_inferior_file
    assert frame.lineno == 34
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
    assert obj.str_repr == "local_1 value"

    obj = heap.objects[frame.locals["local_2"]]
    # assert obj.address == frame.locals["local_2"]
    assert obj.type == _find_type_by_name(heap, "list")
    assert obj.size == 64
    assert obj.str_repr == "['local_2 value']"
    assert {heap.objects[r].str_repr for r in obj.referents} == {"local_2 value"}

    frame = second_thread.stack_trace[1]
    assert frame.co_filename == mock_inferior_file
    assert frame.lineno == 37
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


def _find_type_by_name(heap: Heap, type_name: str) -> int:
    for type_address, type_name0 in heap.types.items():
        if type_name0 == type_name:
            return int(type_address)
    else:
        raise ValueError("not found")
