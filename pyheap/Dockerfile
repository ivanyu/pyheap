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
FROM python:3.10.8-alpine3.16

RUN apk add --no-cache gdb

# Prevent Python 3.10 from being discoverable by GDB.
RUN mkdir /pyheap_python \
    && mv /usr/bin/python3 /pyheap_python \
    && mv /usr/bin/python3.10 /pyheap_python

ADD /dist/pyheap_dump /pyheap_dump
RUN /pyheap_python/python3 /pyheap_dump >/dev/null 2>&1 || true  # unzip (warm up cache)

ENTRYPOINT ["/pyheap_python/python3", "/pyheap_dump"]
