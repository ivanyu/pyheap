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
from pyheap_ui.__main__ import big_number


def test_big_number() -> None:
    assert big_number(1) == "1"
    assert big_number(12) == "12"
    assert big_number(123) == "123"
    assert big_number(1234) == "1&nbsp;234"
    assert big_number(12345) == "12&nbsp;345"
    assert big_number(123456) == "123&nbsp;456"
    assert big_number(1234567) == "1&nbsp;234&nbsp;567"
