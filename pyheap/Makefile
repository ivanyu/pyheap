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

version := $(shell cat pyproject.toml | grep version | head -n 1 | sed -e 's/version = //g' | sed -e s/\"//g)

all: check dist

dist: dist/pyheap-$(version).tar.gz dist/pyheap_dump.pyz
	@echo "Distribution built: $^"

dist/pyheap-$(version).tar.gz: src/dumper_inferior.py src/injector.py src/pyheap_dump.py
	mkdir -p dist
	tar --transform='s/src\//pyheap\//g' -czf $@ $^

dist/pyheap_dump.pyz: src
	mkdir -p dist
	python3 -m zipapp src -m pyheap_dump:main --output=$@

clean:
	rm -rf dist

check: black-check test

.PHONY: black-check
black-check:
	poetry run black --check .

.PHONY: black-reformat
black-reformat:
	poetry run black .

.PHONY: test
test:
	poetry run pytest -vv tests
