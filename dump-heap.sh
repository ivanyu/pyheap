#!/usr/bin/env bash
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
set -e
set -o pipefail

PID=$1
HEAP_DUMP_PATH=$2
echo "Dumping heap from $PID into $HEAP_DUMP_PATH"

CODE_PATH="$(realpath .)/pyheap"
INJECTOR_PATH="$CODE_PATH/injector.py"

echo "Injector path: $INJECTOR_PATH"

gdb --readnow \
  -ex "set debuginfod enabled off" \
  -ex "break _PyEval_EvalFrameDefault" \
  -ex "continue" \
  -ex "del 1" \
  -ex "source $INJECTOR_PATH" \
  -ex "set print elements 0" \
  -ex "print \$dump_python_heap(\"$CODE_PATH\", \"$HEAP_DUMP_PATH\")" \
  -ex "detach" \
  -ex "quit" \
  -p $PID
