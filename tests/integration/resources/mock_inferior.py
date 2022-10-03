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
import os
import sys
import tempfile
import time
from pathlib import Path
from threading import Thread, Event

heap_file = sys.argv[1]


class MyThread(Thread):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.reached = Event()

    def _thread_inner(self, local_1: str, local_2: []) -> None:
        self.reached.set()
        time.sleep(10_000_000)

    def run(self) -> None:
        self._thread_inner("local_1 value", ["local_2 value"])
        super().run()


my_thread = MyThread(name="MyThread")
my_thread.daemon = True
my_thread.start()
my_thread.reached.wait(2)


some_string = "hello world"
some_list = [1, 2, 3]
some_tuple = ("a", "b", "c")


def function3(a: int) -> None:
    dumper_path = str(
        Path(__file__).parent.parent.parent.parent
        / "pyheap"
        / "dumper"
        / "dumper_inferior.py"
    )
    import runpy

    progress_file_path = os.path.join(
        tempfile.mkdtemp(prefix="pyheap-"), "progress.json"
    )
    Path(progress_file_path).touch(mode=0o622, exist_ok=False)  # rw--w--w-
    runpy.run_path(
        path_name=dumper_path,
        init_globals={
            "heap_file": heap_file,
            "str_len": 1000,
            "progress_file": progress_file_path,
        },
    )


def function2(a: int, b: str) -> None:
    function3(a)


def function1(a: int, b: str, c: float) -> None:
    function2(a, b)


function1(42, "leaf", 12.5)
