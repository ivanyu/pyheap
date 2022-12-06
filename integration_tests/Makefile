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
	rm -f e2e_docker/inferior-simple.py

define build_image
	docker build e2e_docker \
		-f "e2e_docker/$2.Dockerfile" \
		--build-arg BASE_IMAGE_VERSION="$3" \
		--build-arg PYHEAP_PYTHON_VERSION="$1" \
		--tag "ivanyu/pyheap-e2e-test-target:$2-$1"
endef

.PHONY: test-target-docker-images-3-8
test-target-docker-images-3-8: e2e_docker/inferior-simple.py
	$(call build_image,3.8,alpine,3.8.15-alpine3.16)
	$(call build_image,3.8,debian,3.8.15-slim-bullseye)
	$(call build_image,3.8,ubuntu,22.04)
	$(call build_image,3.8,fedora,36)

.PHONY: test-target-docker-images-3-9
test-target-docker-images-3-9: e2e_docker/inferior-simple.py
	$(call build_image,3.9,alpine,3.9.15-alpine3.16)
	$(call build_image,3.9,debian,3.9.15-slim-bullseye)
	$(call build_image,3.9,ubuntu,22.04)
	$(call build_image,3.9,fedora,36)

.PHONY: test-target-docker-images-3-10
test-target-docker-images-3-10: e2e_docker/inferior-simple.py
	$(call build_image,3.10,alpine,3.10.8-alpine3.16)
	$(call build_image,3.10,debian,3.10.8-slim-bullseye)
	$(call build_image,3.10,ubuntu,22.04)
	$(call build_image,3.10,fedora,36)

.PHONY: test-target-docker-images-3-11
test-target-docker-images-3-11: e2e_docker/inferior-simple.py
	$(call build_image,3.11,alpine,3.11.0-alpine3.16)
	$(call build_image,3.11,debian,3.11.0-slim-bullseye)
	$(call build_image,3.11,ubuntu,22.04)
	$(call build_image,3.11,fedora,36)

e2e_docker/inferior-simple.py:
	cp ../test_inferiors/inferior-simple.py $@
