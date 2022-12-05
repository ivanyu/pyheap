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
import re
from typing import Iterator, Tuple


def proc_maps(pid: int) -> Iterator[Tuple[str, ...]]:
    try:
        with open(f"/proc/{pid}/maps", "r") as f:
            for l in f.readlines():
                parts = re.split("\s+", l.strip())
                yield parts
    except PermissionError as e:
        raise Exception(
            "Hint: the target process is likely run under a different user, use sudo"
        ) from e
