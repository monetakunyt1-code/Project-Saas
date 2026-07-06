const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");

const adminLink = document.getElementById(
    "admin-link"
);

const adminTab = document.getElementById(
    "admin-tab"
);

const toast = document.getElementById(
    "toast"
);

let currentUser = null;


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
    isError = false
) {
    element.className = (
        isError
            ? "message error"
            : "message success"
    );

    element.textContent = message;
}


function activatePanel(name) {
    tabs.forEach((tab) => {
        tab.classList.toggle(
            "active",
            tab.dataset.panel === name
        );
    });

    panels.forEach((panel) => {
        panel.classList.toggle(
            "active",
            panel.id === `panel-${name}`
        );
    });

    if (name === "admin") {
        loadAuditEvents();
    }
}


tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
        activatePanel(
            tab.dataset.panel
        );
    });
});


async function loadCurrentUser() {
    const response = await fetch(
        "/api/auth/me"
    );

    if (!response.ok) {
        currentUser = null;
        return;
    }

    const data = await response.json();

    currentUser = data.user;

    const isAdmin = (
        currentUser.role === "admin"
    );

    adminLink.classList.toggle(
        "hidden",
        !isAdmin
    );

    adminTab.classList.toggle(
        "hidden",
        !isAdmin
    );
}


document
    .getElementById("change-password-form")
    .addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const message = document.getElementById(
                "change-password-message"
            );

            const response = await fetch(
                "/api/security/password/change",
                {
                    method: "POST",
                    body: new FormData(
                        event.currentTarget
                    ),
                }
            );

            const data = await response.json();

            if (!response.ok) {
                showMessage(
                    message,
                    data.detail ||
                    "Kata sandi gagal diubah.",
                    true
                );

                return;
            }

            showMessage(
                message,
                data.message
            );

            setTimeout(() => {
                window.location.href = "/login";
            }, 1500);
        }
    );


document
    .getElementById("request-reset-form")
    .addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const result = document.getElementById(
                "reset-token-result"
            );

            const response = await fetch(
                "/api/security/password/reset/request",
                {
                    method: "POST",
                    body: new FormData(
                        event.currentTarget
                    ),
                }
            );

            const data = await response.json();

            if (!response.ok) {
                showMessage(
                    result,
                    data.detail ||
                    "Token gagal dibuat.",
                    true
                );

                return;
            }

            if (
                data.development_reset_token
            ) {
                result.className =
                    "message success";

                result.innerHTML = `
                    <strong>Token reset lokal:</strong>
                    <code>
                        ${escapeHtml(
                            data.development_reset_token
                        )}
                    </code>
                `;

                document.querySelector(
                    '#confirm-reset-form [name="token"]'
                ).value =
                    data.development_reset_token;
            }
            else {
                showMessage(
                    result,
                    data.message
                );
            }
        }
    );


document
    .getElementById("confirm-reset-form")
    .addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const message = document.getElementById(
                "confirm-reset-message"
            );

            const response = await fetch(
                "/api/security/password/reset/confirm",
                {
                    method: "POST",
                    body: new FormData(
                        event.currentTarget
                    ),
                }
            );

            const data = await response.json();

            showMessage(
                message,
                data.detail || data.message,
                !response.ok
            );
        }
    );


async function loadPrivacy() {
    const response = await fetch(
        "/api/security/privacy"
    );

    if (!response.ok) {
        return;
    }

    const data = await response.json();
    const form = document.getElementById(
        "privacy-form"
    );

    form.elements.retention_days.value =
        String(
            data.settings.retention_days
        );

    form.elements.analytics_enabled.checked =
        Boolean(
            data.settings.analytics_enabled
        );
}


document
    .getElementById("privacy-form")
    .addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const formData = new FormData(
                event.currentTarget
            );

            formData.set(
                "analytics_enabled",
                event.currentTarget.elements
                    .analytics_enabled.checked
                    ? "true"
                    : "false"
            );

            const response = await fetch(
                "/api/security/privacy",
                {
                    method: "POST",
                    body: formData,
                }
            );

            const data = await response.json();

            showMessage(
                document.getElementById(
                    "privacy-message"
                ),
                data.detail || data.message,
                !response.ok
            );
        }
    );


document
    .getElementById("delete-account-form")
    .addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const confirmed = window.confirm(
                "Akun akan dihapus permanen. Lanjutkan?"
            );

            if (!confirmed) {
                return;
            }

            const response = await fetch(
                "/api/security/account/delete",
                {
                    method: "POST",
                    body: new FormData(
                        event.currentTarget
                    ),
                }
            );

            const data = await response.json();

            if (!response.ok) {
                showMessage(
                    document.getElementById(
                        "delete-account-message"
                    ),
                    data.detail ||
                    "Akun gagal dihapus.",
                    true
                );

                return;
            }

            window.location.href = "/register";
        }
    );


function formatBytes(bytes) {
    const value = Number(
        bytes || 0
    );

    if (value < 1024) {
        return `${value} B`;
    }

    if (value < 1024 * 1024) {
        return `${(
            value / 1024
        ).toFixed(1)} KB`;
    }

    return `${(
        value / (1024 * 1024)
    ).toFixed(1)} MB`;
}


async function loadAuditEvents() {
    const container = document.getElementById(
        "audit-events"
    );

    container.innerHTML = `
        <div class="loading">
            Memuat log aktivitas...
        </div>
    `;

    const response = await fetch(
        "/api/security/admin/audit-events?limit=250"
    );

    const data = await response.json();

    if (!response.ok) {
        container.innerHTML = `
            <div class="error-state">
                ${escapeHtml(
                    data.detail ||
                    "Log gagal dimuat."
                )}
            </div>
        `;

        return;
    }

    if (!data.events.length) {
        container.innerHTML = `
            <div class="empty-state">
                Belum ada aktivitas tercatat.
            </div>
        `;

        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Waktu</th>
                    <th>Pengguna</th>
                    <th>Metode</th>
                    <th>Endpoint</th>
                    <th>Status</th>
                    <th>IP</th>
                </tr>
            </thead>

            <tbody>
                ${data.events
                    .map((event) => {
                        return `
                            <tr>
                                <td>
                                    ${new Date(
                                        event.created_at
                                    ).toLocaleString(
                                        "id-ID"
                                    )}
                                </td>

                                <td>
                                    ${escapeHtml(
                                        event.email ||
                                        "Anonim"
                                    )}
                                </td>

                                <td>
                                    ${escapeHtml(
                                        event.method
                                    )}
                                </td>

                                <td>
                                    <code>
                                        ${escapeHtml(
                                            event.path
                                        )}
                                    </code>
                                </td>

                                <td>
                                    ${escapeHtml(
                                        event.status_code
                                    )}
                                </td>

                                <td>
                                    ${escapeHtml(
                                        event.ip_address
                                    )}
                                </td>
                            </tr>
                        `;
                    })
                    .join("")}
            </tbody>
        </table>
    `;
}


document
    .getElementById("refresh-audit")
    .addEventListener(
        "click",
        loadAuditEvents
    );


document
    .getElementById("preview-retention")
    .addEventListener(
        "click",
        async () => {
            const form = document.getElementById(
                "retention-form"
            );

            const days = (
                form.elements.retention_days.value
            );

            const response = await fetch(
                `/api/security/admin/retention/preview`
                + `?retention_days=${encodeURIComponent(days)}`
            );

            const data = await response.json();

            const result = document.getElementById(
                "retention-result"
            );

            if (!response.ok) {
                showMessage(
                    result,
                    data.detail ||
                    "Pratinjau gagal.",
                    true
                );

                return;
            }

            result.className =
                "message success";

            result.innerHTML = `
                Ditemukan
                <strong>
                    ${data.candidates_total}
                </strong>
                item dengan total ukuran
                <strong>
                    ${formatBytes(data.size_bytes)}
                </strong>.
            `;
        }
    );


document
    .getElementById("retention-form")
    .addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const confirmed = window.confirm(
                "Hapus seluruh data lama yang terdeteksi?"
            );

            if (!confirmed) {
                return;
            }

            const response = await fetch(
                "/api/security/admin/retention/apply",
                {
                    method: "POST",
                    body: new FormData(
                        event.currentTarget
                    ),
                }
            );

            const data = await response.json();

            const result = document.getElementById(
                "retention-result"
            );

            if (!response.ok) {
                showMessage(
                    result,
                    data.detail ||
                    "Pembersihan gagal.",
                    true
                );

                return;
            }

            result.className =
                "message success";

            result.innerHTML = `
                Berhasil menghapus
                <strong>
                    ${data.removed_total}
                </strong>
                item dengan total ukuran
                <strong>
                    ${formatBytes(data.size_bytes)}
                </strong>.
            `;
        }
    );


async function initialize() {
    await loadCurrentUser();

    if (!currentUser) {
        document
            .getElementById("panel-privacy")
            .innerHTML = `
                <article class="card">
                    <h1>Login diperlukan</h1>

                    <p>
                        <a href="/login">
                            Masuk ke akun DocuRapi
                        </a>
                    </p>
                </article>
            `;

        document
            .getElementById("panel-data")
            .innerHTML = `
                <article class="card">
                    <h1>Login diperlukan</h1>

                    <p>
                        <a href="/login">
                            Masuk ke akun DocuRapi
                        </a>
                    </p>
                </article>
            `;

        return;
    }

    await loadPrivacy();
}


initialize();