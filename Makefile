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
	(cd integration_tests && $(MAKE) clean)

pyheap/dist/pyheap_dump:
	(cd pyheap && $(MAKE) dist)

.PHONY: dumper-docker-image
dumper-docker-image:
	(cd pyheap && $(MAKE) docker-image)

.PHONY: integration-tests
integration-tests: integration-tests-3-8 integration-tests-3-9 integration-tests-3-10 integration-tests-3-11

define run_integration_test
	cd integration_tests && \
		  $(MAKE) "$2" && \
		  PYENV_VERSION="$1" poetry env use python && \
		  poetry run pip install -e ../pyheap-ui/ && \
		  poetry install && \
		  poetry run pytest -vv ./*.py
endef

.PHONY: integration-tests-3-8
integration-tests-3-8: pyheap/dist/pyheap_dump dumper-docker-image
	$(call run_integration_test,3.8,test-target-docker-images-3-8)

.PHONY: integration-tests-3-9
integration-tests-3-9: pyheap/dist/pyheap_dump dumper-docker-image
	$(call run_integration_test,3.9,test-target-docker-images-3-9)

.PHONY: integration-tests-3-10
integration-tests-3-10: pyheap/dist/pyheap_dump dumper-docker-image
	$(call run_integration_test,3.10,test-target-docker-images-3-10)

.PHONY: integration-tests-3-11
integration-tests-3-11: pyheap/dist/pyheap_dump dumper-docker-image
	$(call run_integration_test,3.11,test-target-docker-images-3-11)
