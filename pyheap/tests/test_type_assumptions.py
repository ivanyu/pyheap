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
from typing import Any, Type

import pytest


@pytest.mark.parametrize(
    "type_, example, hashable",
    [
        (int, 0, True),
        (float, 0.0, True),
        (bool, False, True),
        (str, "", True),
        (bytes, b"", True),
        (list, [], False),
        (set, set(), False),
        (dict, {}, False),
    ],
)
def test_types(type_: Type, example: Any, hashable: bool) -> None:
    for attr_name in dir(example):
        attr = inspect.getattr_static(example, attr_name)
        if attr_name == "__doc__":
            assert type(attr) == str
        elif attr_name == "__hash__":
            if hashable:
                assert type(attr).__name__ == "wrapper_descriptor"
            else:
                assert attr is None
        else:
            assert type(attr).__name__ in {
                "classmethod_descriptor",
                "method_descriptor",
                "wrapper_descriptor",
                "builtin_function_or_method",
                "getset_descriptor",
                "staticmethod",
            }
