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

all: check dist

dist: dist/pyheap_dump
	@echo "Distribution built: $^"

dist/pyheap_dump: build/requirements.txt build-src
	mkdir -p dist
	poetry run pex \
		--requirement=build/requirements.txt \
		--sources-directory=build/src \
		--entry-point=pyheap_dump:main \
		--output-file=$@

build/requirements.txt: poetry.lock
	mkdir -p build/
	poetry export --without-hashes --format=requirements.txt > build/requirements.txt

.PHONY: build-src
build-src: src/*.py
	git ls-files --error-unmatch $^
	rm -rf build/src
	mkdir -p build/src
	cp $^ build/src

.PHONY: docker-image
docker-image: dist/pyheap_dump
	docker build . -f Dockerfile -t ivanyu/pyheap-dumper

clean:
	rm -rf build
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
