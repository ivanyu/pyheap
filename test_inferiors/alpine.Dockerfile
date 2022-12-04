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

RUN addgroup -g 10042 testgroup && adduser --uid 10123 testuser -g testgroup -D

RUN set -eux; \
    apk add --no-cache --virtual .build-deps \
        gcc \
        g++ \
        linux-headers \
        libc-dev \
        openssl-dev

ADD --chown=testuser:testgroup https://install.python-poetry.org /home/testuser/poetry-install.py

USER testuser
RUN python3 /home/testuser/poetry-install.py

COPY ./ /inferiors/
WORKDIR /inferiors

ENV PATH="/home/testuser/.local/bin:$PATH"

RUN poetry install

USER root
RUN set -eux; \
    apk del --no-network .build-deps

USER testuser
