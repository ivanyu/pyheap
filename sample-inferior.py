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

# Circular reference
a = ["a"]
a.append(a)

huge_string = "x" * 1_000_000

huge_list = ["x" * 100_000]


# Thread.
class MyThread(Thread):
    def _x(self, bbb, cccc):
        time.sleep(1)

    def run(self) -> None:
        while True:
            self._x({"aaa"}, 222)


MyThread().start()


# Function calls.
def f(a, b):
    print("Calling")
    time.sleep(1)


while True:
    f(["xxxx"], 123)
