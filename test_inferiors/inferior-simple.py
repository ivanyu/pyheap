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
import time
from threading import Thread
from typing import Any, NoReturn

# Circular reference
a = ["a"]
a.append(a)

huge_string = "x" * 1_000_000

huge_list = ["x" * 100_000]


class DisabledOperations:
    def __new__(cls) -> "DisabledOperations":
        prohibited = {
            "__dir__",
            "__str__",
            "__repr__",
            "__doc__",
            "__eq__",
            "__ge__",
            "__gt__",
            "__getattribute__",
            "__hash__",
            "__le__",
            "__lt__",
            "__ne__",
            "__setattr__",
            "__sizeof__",
        }
        for attr in prohibited:

            def error(*args: Any, **kwargs: Any) -> NoReturn:
                raise ValueError(f"prohibited to call {attr}")

            setattr(cls, attr, error)
        return super().__new__(cls)


disabled_operations = DisabledOperations()


# Thread.
class MyThread(Thread):
    def _x(self, bbb, cccc):
        time.sleep(1)

    def run(self) -> None:
        while True:
            self._x({"local-1"}, "local-2")


MyThread().start()


# Function calls.
def f2(a, b, c):
    print("Calling")
    time.sleep(1)


def f1(a, b):
    eval("123")  # prevent frame optimizations`
    f2(a, b, None)


while True:
    f1(["local-3"], "local-4")
