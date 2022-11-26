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
import { notifications } from "./notifications.js";

const escapeReplacements = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&apos;",
    "/": "&frasl;",
    "`": "&#x60;",
    "=": "&#x3D;"
};
function escapeHtml(string) {
    return String(string).replace(/[&<>"'`=\/]/g, s => escapeReplacements[s]);
}

function bigNumber(string) {
    string = string.toString();
    const maxChunkSize = 3;
    const chunks = [];
    for (var i = string.length; i > 0; i -= maxChunkSize) {
        const left = Math.max(0, i - maxChunkSize);
        chunks.push(string.substring(left, i));
    }
    chunks.reverse();
    return chunks.join("&nbsp;");
}

async function getObjects(addresses) {
    const responseJson = await fetch(
        "/api/objects/",
        {
            "method": "POST",
            "body": JSON.stringify({"addresses": addresses}),
            "headers": {"Accept": "application/json", "Content-Type": "application/json"}
        })
        .then((response) => {
            if (response.ok) {
                return response.json();
            }

            const message = response.status + " " + response.statusText;
            notifications.showError(message);
            throw new Error(message);
        });
    return (await responseJson)["objects"];
}

async function getObject(addr) {
    return (await getObjects([addr]))[0];
}

class ObjectTreeView {
    #topLevelObjects;
    constructor(root) {
        this.#topLevelObjects = this.fetchTopLevelObjects(root);
    }

    async render() {
        const topLevelList = this.createTreeList(false);
        for (const obj of (await this.#topLevelObjects)) {
            if (obj === null) {
                continue;
            }
            const treeNode = this.createTreeNode(obj, null);
            topLevelList.append(treeNode);
        }
        return topLevelList;
    }

    createExpandButton(li, onExpand) {
        const iconCollapsed = $(`<i class="bi bi-caret-right-fill"></i>`);
        const iconExpanded = $(`<i class="bi bi-caret-down-fill"></i>`);

        const button = $(`<span style="cursor: pointer; "><span>`).append(iconCollapsed);
        button.collapsed = true;
        button.disabled = false;

        const tree = this;
        button.click(async function() {
            if (button.disabled) {
                return;
            }

            button.disabled = true;
            if (button.collapsed) {
                const empty = await tree.onExpand(li);
                if (empty) {
                    button.css("visibility", "hidden");
                } else {
                    button.empty();
                    button.append(iconExpanded);
                }
            } else {
                button.empty();
                button.append(iconCollapsed);
                await tree.onCollapse(li);
            }
            button.collapsed = !button.collapsed;
            button.disabled = false;
        });

        return button;
    }

    createTreeList(pad) {
        const style = pad ? "padding-left: 1em;" : "";
        return $(`<ul id="referents-list" style="${style}" class="list-unstyled"></ul>`);
    }

    createTreeNode(object, treeParent) {
        const li = $(`<li></li>`);
        if (treeParent === null) {
            li.treeLevel = 0;
        } else {
            li.treeLevel = treeParent.treeLevel + 1;
        }
        li.object = object;
        const expandButton = this.createExpandButton(li);
        li.append(expandButton);
        li.append(`
            <a href="/objects/${escapeHtml(object.address)}" title="Address: ${escapeHtml(object.address)}"><i class="bi bi-link-45deg"></i></a>
            <span title="Retained heap, B" class="text-muted">
                [<i class="bi bi-lock"></i>
                ${bigNumber(escapeHtml(object.retained_heap))}]
            </span>
            <code>${escapeHtml(object.type)}</code>
        `);
        if (object.str_repr !== null) {
            li.append(`<span class="inline-object-str text-muted">${escapeHtml(object.str_repr)}</span>`);
        }
        return li;
    }

    async onExpand(li) {
        if (li.treeChildrenList == undefined) {
            const spinner = $(`
                <li style="padding-left: 1em;"><div class="spinner-border spinner-border-sm" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div></li>`);
            li.after(spinner);

            li.treeChildrenList = this.createTreeList(true);
            const objects = await this.getChildObjects(li);
            for (const obj of objects) {
                const treeChild = this.createTreeNode(obj, li);
                li.treeChildrenList.append(treeChild);
            }

            spinner.remove();
        }

        const empty = li.treeChildrenList.children().length === 0;
        if (!empty) {
            li.after(li.treeChildrenList);
        }
        return empty;
    }

    async onCollapse(li) {
        li.treeChildrenList.detach();
    }
}

export { ObjectTreeView, getObjects, getObject };
