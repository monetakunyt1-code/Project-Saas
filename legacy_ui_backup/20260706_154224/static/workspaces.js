const workspaceList = document.getElementById(
    "workspace-list"
);

const memberList = document.getElementById(
    "member-list"
);

const inviteCard = document.getElementById(
    "invite-card"
);

const toast = document.getElementById(
    "toast"
);

let activeWorkspace = null;
let workspaces = [];


function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function showToast(message) {
    toast.textContent = message;
    toast.classList.remove("hidden");

    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3500);
}


function showMessage(
    element,
    message,
    error = false
) {
    element.className = (
        error
            ? "message error"
            : "message success"
    );

    element.textContent = message;
}


async function loadWorkspaces() {
    const response = await fetch(
        "/api/workspaces"
    );

    if (response.status === 401) {
        window.location.href = "/login";
        return;
    }

    const data = await response.json();

    if (!response.ok) {
        workspaceList.innerHTML = `
            <div class="error-state">
                ${escapeHtml(
                    data.detail ||
                    "Workspace gagal dimuat."
                )}
            </div>
        `;

        return;
    }

    workspaces = data.workspaces || [];
    activeWorkspace = data.active_workspace;

    renderActiveWorkspace();
    renderWorkspaceList();

    await Promise.all([
        loadMembers(),
        loadResourceSummary(),
    ]);
}


function renderActiveWorkspace() {
    document.getElementById(
        "active-workspace-name"
    ).textContent = (
        activeWorkspace?.name
        || "Workspace belum tersedia"
    );

    document.getElementById(
        "active-workspace-detail"
    ).textContent = activeWorkspace
        ? (
            `${activeWorkspace.workspace_type}`
            + ` · Peran ${activeWorkspace.role}`
        )
        : "Workspace belum tersedia.";

    const canInvite = [
        "owner",
        "admin",
    ].includes(
        activeWorkspace?.role
    );

    inviteCard.classList.toggle(
        "hidden",
        !canInvite
    );
}


function renderWorkspaceList() {
    if (!workspaces.length) {
        workspaceList.innerHTML = `
            <div class="empty-state">
                Belum ada workspace.
            </div>
        `;

        return;
    }

    workspaceList.innerHTML = workspaces
        .map((workspace) => {
            const active = (
                workspace.workspace_id
                === activeWorkspace?.workspace_id
            );

            return `
                <div class="workspace-item ${
                    active ? "active" : ""
                }">
                    <div>
                        <h3>
                            ${escapeHtml(workspace.name)}
                        </h3>

                        <p>
                            ${escapeHtml(
                                workspace.workspace_type
                            )}
                            ·
                            ${escapeHtml(workspace.role)}
                            ·
                            ${escapeHtml(
                                workspace.member_count
                            )}
                            anggota
                        </p>
                    </div>

                    <button
                        type="button"
                        data-switch-workspace="${
                            workspace.workspace_id
                        }"
                        ${active ? "disabled" : ""}
                    >
                        ${
                            active
                                ? "Sedang Aktif"
                                : "Aktifkan"
                        }
                    </button>
                </div>
            `;
        })
        .join("");

    document
        .querySelectorAll(
            "[data-switch-workspace]"
        )
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const formData = new FormData();

                    formData.append(
                        "workspace_id",
                        button.dataset
                            .switchWorkspace
                    );

                    const response = await fetch(
                        "/api/workspaces/switch",
                        {
                            method: "POST",
                            body: formData,
                        }
                    );

                    const data = await response.json();

                    if (!response.ok) {
                        showToast(
                            data.detail ||
                            "Workspace gagal diaktifkan."
                        );

                        return;
                    }

                    showToast(
                        "Workspace aktif berhasil diubah."
                    );

                    await loadWorkspaces();
                }
            );
        });
}


async function loadMembers() {
    if (!activeWorkspace) {
        return;
    }

    const response = await fetch(
        `/api/workspaces/${
            activeWorkspace.workspace_id
        }/members`
    );

    const data = await response.json();

    if (!response.ok) {
        memberList.innerHTML = `
            <div class="error-state">
                ${escapeHtml(
                    data.detail ||
                    "Anggota gagal dimuat."
                )}
            </div>
        `;

        return;
    }

    memberList.innerHTML = data.members
        .map((member) => {
            const editable = (
                activeWorkspace.role === "owner"
                || activeWorkspace.role === "admin"
            ) && member.role !== "owner";

            return `
                <div class="member-item">
                    <div>
                        <strong>
                            ${escapeHtml(
                                member.display_name
                            )}
                        </strong>

                        <span>
                            ${escapeHtml(member.email)}
                        </span>
                    </div>

                    ${
                        editable
                            ? `
                                <select
                                    data-member-role="${
                                        member.user_id
                                    }"
                                >
                                    <option value="admin">
                                        Admin
                                    </option>

                                    <option value="member">
                                        Member
                                    </option>

                                    <option value="viewer">
                                        Viewer
                                    </option>
                                </select>

                                <button
                                    type="button"
                                    class="small-button"
                                    data-save-member="${
                                        member.user_id
                                    }"
                                >
                                    Simpan
                                </button>

                                <button
                                    type="button"
                                    class="danger-button"
                                    data-remove-member="${
                                        member.user_id
                                    }"
                                >
                                    Hapus
                                </button>
                            `
                            : `
                                <span class="role-badge">
                                    ${escapeHtml(member.role)}
                                </span>
                            `
                    }
                </div>
            `;
        })
        .join("");

    data.members.forEach((member) => {
        const select = document.querySelector(
            `[data-member-role="${
                member.user_id
            }"]`
        );

        if (select) {
            select.value = member.role;
        }
    });

    document
        .querySelectorAll(
            "[data-save-member]"
        )
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const userId =
                        button.dataset.saveMember;

                    const select =
                        document.querySelector(
                            `[data-member-role="${userId}"]`
                        );

                    const formData = new FormData();

                    formData.append(
                        "role",
                        select.value
                    );

                    const response = await fetch(
                        `/api/workspaces/${
                            activeWorkspace.workspace_id
                        }/members/${userId}/role`,
                        {
                            method: "POST",
                            body: formData,
                        }
                    );

                    const data = await response.json();

                    if (!response.ok) {
                        showToast(
                            data.detail ||
                            "Peran gagal diperbarui."
                        );

                        return;
                    }

                    showToast(
                        "Peran anggota diperbarui."
                    );

                    await loadMembers();
                }
            );
        });

    document
        .querySelectorAll(
            "[data-remove-member]"
        )
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const confirmed = window.confirm(
                        "Keluarkan anggota ini?"
                    );

                    if (!confirmed) {
                        return;
                    }

                    const response = await fetch(
                        `/api/workspaces/${
                            activeWorkspace.workspace_id
                        }/members/${
                            button.dataset.removeMember
                        }`,
                        {
                            method: "DELETE",
                        }
                    );

                    const data = await response.json();

                    if (!response.ok) {
                        showToast(
                            data.detail ||
                            "Anggota gagal dihapus."
                        );

                        return;
                    }

                    showToast(
                        "Anggota berhasil dikeluarkan."
                    );

                    await loadMembers();
                }
            );
        });
}


async function loadResourceSummary() {
    const container = document.getElementById(
        "resource-summary"
    );

    if (!activeWorkspace) {
        container.innerHTML = "";
        return;
    }

    const response = await fetch(
        `/api/workspaces/${
            activeWorkspace.workspace_id
        }/summary`
    );

    const data = await response.json();

    if (!response.ok) {
        container.innerHTML = "";
        return;
    }

    const labels = {
        job: "Dokumen",
        template: "Template",
        profile: "Profil",
        batch: "Batch",
        audit: "Audit",
        journal: "Jurnal",
    };

    container.innerHTML = Object.entries(
        labels
    )
        .map(([key, label]) => {
            return `
                <article>
                    <span>${label}</span>

                    <strong>
                        ${escapeHtml(
                            data.resource_counts[key]
                            || 0
                        )}
                    </strong>
                </article>
            `;
        })
        .join("");
}


document
    .getElementById(
        "create-workspace-form"
    )
    .addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const response = await fetch(
                "/api/workspaces",
                {
                    method: "POST",
                    body: new FormData(
                        event.currentTarget
                    ),
                }
            );

            const data = await response.json();

            const message = document.getElementById(
                "create-workspace-message"
            );

            if (!response.ok) {
                showMessage(
                    message,
                    data.detail ||
                    "Workspace gagal dibuat.",
                    true
                );

                return;
            }

            showMessage(
                message,
                data.message
            );

            event.currentTarget.reset();

            await loadWorkspaces();
        }
    );


document
    .getElementById(
        "join-workspace-form"
    )
    .addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const response = await fetch(
                "/api/workspaces/join",
                {
                    method: "POST",
                    body: new FormData(
                        event.currentTarget
                    ),
                }
            );

            const data = await response.json();

            const message = document.getElementById(
                "join-workspace-message"
            );

            if (!response.ok) {
                showMessage(
                    message,
                    data.detail ||
                    "Gagal bergabung.",
                    true
                );

                return;
            }

            showMessage(
                message,
                data.message
            );

            event.currentTarget.reset();

            await loadWorkspaces();
        }
    );


document
    .getElementById("invite-form")
    .addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const response = await fetch(
                `/api/workspaces/${
                    activeWorkspace.workspace_id
                }/invites`,
                {
                    method: "POST",
                    body: new FormData(
                        event.currentTarget
                    ),
                }
            );

            const data = await response.json();

            const result = document.getElementById(
                "invite-result"
            );

            if (!response.ok) {
                showMessage(
                    result,
                    data.detail ||
                    "Undangan gagal dibuat.",
                    true
                );

                return;
            }

            result.className =
                "message success";

            result.innerHTML = `
                <strong>Kode undangan:</strong>

                <code>
                    ${escapeHtml(data.invite_code)}
                </code>

                <button
                    id="copy-invite"
                    type="button"
                    class="secondary-button"
                >
                    Salin Kode
                </button>
            `;

            document.getElementById(
                "copy-invite"
            ).addEventListener(
                "click",
                async () => {
                    await navigator.clipboard.writeText(
                        data.invite_code
                    );

                    showToast(
                        "Kode undangan disalin."
                    );
                }
            );
        }
    );


document
    .getElementById(
        "refresh-workspaces"
    )
    .addEventListener(
        "click",
        loadWorkspaces
    );


loadWorkspaces();