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
from __future__ import annotations

import json
import subprocess


def get_container_pid(container: str) -> int:
    proc = subprocess.run(
        ["docker", "inspect", container],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise Exception(
            f"Cannot determine target PID: "
            f"`docker inspect {container}` returned: {proc.stderr}"
        )

    inspect_obj = json.loads(proc.stdout)
    if len(inspect_obj) != 1:
        raise Exception(
            f"Cannot determine target PID: "
            f"Expected 1 object in `docker inspect {container}`, but got {len(inspect_obj)}"
        )

    state = inspect_obj[0]["State"]
    if state["Status"] != "running":
        raise Exception(f"Cannot determine target PID: Container is not running")

    pid = int(state["Pid"])
    return pid
