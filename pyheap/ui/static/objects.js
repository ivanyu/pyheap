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

async function getObjects(addresses) {
    const response = await fetch(
        "/api/objects/",
        {
            "method": "POST",
            "body": JSON.stringify({"addresses": addresses}),
            "headers": {"Accept": "application/json", "Content-Type": "application/json"}
        });
    return (await response.json())["objects"];
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
            const treeNode = this.createTreeNode(obj, null);
            topLevelList.append(treeNode);
        }
        return topLevelList;
    }

    createExpandButton(li, onExpand) {
        const iconCollapsed = $(`
            <svg xmlns="http://www.w3.org/2000/svg" width="0.9em" height="0.9em" fill="currentColor" class="bi bi-caret-right" viewBox="0 0 16 16">
                <path d="m12.14 8.753-5.482 4.796c-.646.566-1.658.106-1.658-.753V3.204a1 1 0 0 1 1.659-.753l5.48 4.796a1 1 0 0 1 0 1.506z"/>
            </svg>
        `);
        const iconExpanded = $(`
            <svg xmlns="http://www.w3.org/2000/svg" width="0.9em" height="0.9em" fill="currentColor" class="bi bi-caret-down-fill" viewBox="0 0 16 16">
                <path d="M7.247 11.14 2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z"/>
            </svg>
        `);

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
        li.append(expandButton).append(`
            <a href="/objects/${escapeHtml(object.address)}" title="Address: ${escapeHtml(object.address)}">
                <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" class="bi bi-box-arrow-up-right" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8.636 3.5a.5.5 0 0 0-.5-.5H1.5A1.5 1.5 0 0 0 0 4.5v10A1.5 1.5 0 0 0 1.5 16h10a1.5 1.5 0 0 0 1.5-1.5V7.864a.5.5 0 0 0-1 0V14.5a.5.5 0 0 1-.5.5h-10a.5.5 0 0 1-.5-.5v-10a.5.5 0 0 1 .5-.5h6.636a.5.5 0 0 0 .5-.5z"/>
                    <path fill-rule="evenodd" d="M16 .5a.5.5 0 0 0-.5-.5h-5a.5.5 0 0 0 0 1h3.793L6.146 9.146a.5.5 0 1 0 .708.708L15 1.707V5.5a.5.5 0 0 0 1 0v-5z"/>
                </svg></a>
            <code>${escapeHtml(object.type)}</code>
            <span class="inline-object-str text-muted">${escapeHtml(object.str)}</span>
        `);
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

class ReferentsObjectTreeView extends ObjectTreeView {
    async fetchTopLevelObjects(root) {
        return await getObjects(root.referents);
    }

    async getChildObjects(li) {
        return await getObjects(li.object.referents);
    }
}

class InboundReferencesObjectTreeView extends ObjectTreeView {
    async fetchTopLevelObjects(root) {
        return await getObjects(root.inbound_references);
    }

    async getChildObjects(li) {
        return await getObjects(li.object.inbound_references);
    }
}

$( document ).ready(async function() {
    const rootObject = await getObject(rootAddr);
    const rotv = new ReferentsObjectTreeView(rootObject);
    const irotv = new InboundReferencesObjectTreeView(rootObject);

    $("#referent-tree-panel").append(await rotv.render());
    $("#referent-tree-spinner").remove();

    $("#inbound-references-tree-panel").append(await irotv.render());
    $("#inbound-references-tree-spinner").remove();
});
