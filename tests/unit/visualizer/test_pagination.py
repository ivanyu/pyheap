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
from pyheap.ui.__main__ import Pagination


def test_minimal() -> None:
    pagination = Pagination(1, 1)
    assert not pagination.prev_enabled
    assert not pagination.next_enabled
    assert pagination.layout == [1]


def test_simple_1() -> None:
    pagination = Pagination(10, 1)
    assert not pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    for p in range(2, 9 + 1):
        pagination = Pagination(10, p)
        assert pagination.prev_enabled
        assert pagination.next_enabled
        assert pagination.layout == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    pagination = Pagination(10, 10)
    assert pagination.prev_enabled
    assert not pagination.next_enabled
    assert pagination.layout == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def test_long_1() -> None:
    pagination = Pagination(20, 1)
    assert not pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 18, 19, 20]

    pagination = Pagination(20, 2)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, 4, None, 18, 19, 20]

    pagination = Pagination(20, 3)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, 4, 5, None, 18, 19, 20]

    pagination = Pagination(20, 4)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, 4, 5, 6, None, 18, 19, 20]

    pagination = Pagination(20, 5)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, 4, 5, 6, 7, None, 18, 19, 20]

    pagination = Pagination(20, 6)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, 4, 5, 6, 7, 8, None, 18, 19, 20]

    pagination = Pagination(20, 7)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, 4, 5, 6, 7, 8, 9, None, 18, 19, 20]

    pagination = Pagination(20, 8)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 6, 7, 8, 9, 10, None, 18, 19, 20]

    pagination = Pagination(20, 9)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 7, 8, 9, 10, 11, None, 18, 19, 20]

    pagination = Pagination(20, 10)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 8, 9, 10, 11, 12, None, 18, 19, 20]

    pagination = Pagination(20, 11)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 9, 10, 11, 12, 13, None, 18, 19, 20]

    pagination = Pagination(20, 12)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 10, 11, 12, 13, 14, None, 18, 19, 20]

    pagination = Pagination(20, 13)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 11, 12, 13, 14, 15, None, 18, 19, 20]

    pagination = Pagination(20, 14)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 12, 13, 14, 15, 16, 17, 18, 19, 20]

    pagination = Pagination(20, 15)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 13, 14, 15, 16, 17, 18, 19, 20]

    pagination = Pagination(20, 16)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 14, 15, 16, 17, 18, 19, 20]

    pagination = Pagination(20, 17)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 15, 16, 17, 18, 19, 20]

    pagination = Pagination(20, 18)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 16, 17, 18, 19, 20]

    pagination = Pagination(20, 19)
    assert pagination.prev_enabled
    assert pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 17, 18, 19, 20]

    pagination = Pagination(20, 20)
    assert pagination.prev_enabled
    assert not pagination.next_enabled
    assert pagination.layout == [1, 2, 3, None, 18, 19, 20]
