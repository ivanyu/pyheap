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
ARG BASE_IMAGE_VERSION
FROM fedora:$BASE_IMAGE_VERSION

ARG PYHEAP_PYTHON_VERSION

RUN dnf -y update && dnf install -y \
        "python${PYHEAP_PYTHON_VERSION}" \
        which \
    && dnf clean all

COPY inferior-simple.py /inferior-simple.py

RUN ln -s $(which "python${PYHEAP_PYTHON_VERSION}") /test-python
CMD ["/test-python", "/inferior-simple.py"]
