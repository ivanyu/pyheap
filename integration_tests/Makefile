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
	rm e2e_docker/inferior-simple.py

.PHONY: test_target_docker_image_3_8
test_target_docker_image_3_8: e2e_docker/inferior-simple.py
	docker build e2e_docker \
		--build-arg BASE_VERSION="3.8.15-bullseye" \
		--tag ivanyu/pyheap-e2e-test-target:3.8

.PHONY: test_target_docker_image_3_9
test_target_docker_image_3_9: e2e_docker/inferior-simple.py
	docker build e2e_docker \
		--build-arg BASE_VERSION="3.9.15-bullseye" \
		--tag ivanyu/pyheap-e2e-test-target:3.9

.PHONY: test_target_docker_image_3_10
test_target_docker_image_3_10: e2e_docker/inferior-simple.py
	docker build e2e_docker \
		--build-arg BASE_VERSION="3.10.8-bullseye" \
		--tag ivanyu/pyheap-e2e-test-target:3.10

.PHONY: test_target_docker_image_3_11
test_target_docker_image_3_11: e2e_docker/inferior-simple.py
	docker build e2e_docker \
		--build-arg BASE_VERSION="3.11.0-bullseye" \
		--tag ivanyu/pyheap-e2e-test-target:3.11

e2e_docker/inferior-simple.py:
	cp ../test_inferiors/inferior-simple.py $@
