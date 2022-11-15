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

.PHONY: clean
clean:
	(cd pyheap && $(MAKE) clean)

.PHONY: integration_tests
integration_tests: integration_tests_3_8 integration_tests_3_9 integration_tests_3_10 integration_tests_3_11

pyheap/dist/pyheap_dumper.pyz:
	(cd pyheap && $(MAKE) dist)

.PHONY: integration_tests_3_8
integration_tests_3_8: pyheap/dist/pyheap_dumper.pyz
	(cd integration_tests && \
	  PYENV_VERSION=3.8 poetry env use python && \
	  poetry run pip install -e ../pyheap-ui/ && \
	  poetry install && \
	  poetry run pytest -vv ./*.py)

.PHONY: integration_tests_3_9
integration_tests_3_9: pyheap/dist/pyheap_dumper.pyz
	(cd integration_tests && \
	  PYENV_VERSION=3.9 poetry env use python && \
	  poetry run pip install -e ../pyheap-ui/ && \
	  poetry install && \
	  poetry run pytest -vv ./*.py)

.PHONY: integration_tests_3_10
integration_tests_3_10: pyheap/dist/pyheap_dumper.pyz
	(cd integration_tests && \
	  PYENV_VERSION=3.10 poetry env use python && \
	  poetry run pip install -e ../pyheap-ui/ && \
	  poetry install && \
	  poetry run pytest -vv ./*.py)

.PHONY: integration_tests_3_11
integration_tests_3_11: pyheap/dist/pyheap_dumper.pyz
	(cd integration_tests && \
	  PYENV_VERSION=3.11 poetry env use python && \
	  poetry run pip install -e ../pyheap-ui/ && \
	  poetry install && \
	  poetry run pytest -vv ./*.py)
