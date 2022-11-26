/*
 * Copyright 2022 Ivan Yurchenko
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

var notifications = null;
export { notifications };

class Notifications {
    #notificationsArea;
    constructor(notificationsArea) {
        this.#notificationsArea = notificationsArea;
    }

    showError(text) {
        const toastEl = $(`
            <div class="toast text-bg-danger" role="alert" aria-live="assertive" aria-atomic="true" data-bs-autohide="false">
                <div class="toast-header">
                    <strong class="me-auto">Error</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                  ${text}
                </div>
            </div>
        `);
        toastEl.on("hidden.bs.toast", () => {
            toastEl.remove();
        });
        this.#notificationsArea.append(toastEl);
        const toast = new bootstrap.Toast(toastEl);
        toast.show();
    }
}

$( document ).ready(async function() {
    notifications = new Notifications($("#notifications-area"));
});
