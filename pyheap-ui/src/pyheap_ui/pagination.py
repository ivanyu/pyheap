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
from typing import List, Optional


class Pagination:
    _WINDOW = 3
    _MIN_PAGES_TO_COLLAPSE = 15

    def __init__(self, total_pages: int, page: int) -> None:
        if page > total_pages:
            raise ValueError(f"Invalid page number: {page}")
        self._total_pages = total_pages
        self._page = page

    @property
    def total_pages(self) -> int:
        return self._total_pages

    @property
    def page(self) -> int:
        return self._page

    @property
    def layout(self) -> List[Optional[int]]:
        result = [None] + list(range(1, self._total_pages + 1))

        if self._total_pages < self._MIN_PAGES_TO_COLLAPSE:
            return result[1:]

        right_distance = self._total_pages - self._page
        if right_distance > self._WINDOW * 2:
            del result[self._page + self._WINDOW : self._total_pages - self._WINDOW + 1]
            result.insert(self._page + self._WINDOW, None)

        left_distance = self._page - 1
        if left_distance > self._WINDOW * 2:
            del result[1 + self._WINDOW : self._page - self._WINDOW + 1]
            result.insert(1 + self._WINDOW, None)

        return result[1:]

    @property
    def prev_enabled(self) -> bool:
        return self._page > 1

    @property
    def next_enabled(self) -> bool:
        return self._page < self._total_pages
