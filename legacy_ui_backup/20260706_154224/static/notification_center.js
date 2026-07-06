const notificationList = document.getElementById(
    "notification-list"
);

const unreadCount = document.getElementById(
    "unread-count"
);

const toast = document.getElementById(
    "toast"
);


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


function formatDate(value) {
    if (!value) {
        return "-";
    }

    return new Date(value).toLocaleString(
        "id-ID"
    );
}


async function ensureLogin() {
    const response = await fetch(
        "/api/auth/me"
    );

    if (!response.ok) {
        window.location.href = "/login";
        return false;
    }

    return true;
}


function renderNotifications(data) {
    unreadCount.textContent = (
        data.unread_count || 0
    );

    if (!data.notifications.length) {
        notificationList.innerHTML = `
            <div class="empty-state">
                Tidak ada notifikasi pada filter ini.
            </div>
        `;

        return;
    }

    notificationList.innerHTML = (
        data.notifications
            .map((item) => {
                const unreadClass = (
                    item.read_at
                    ? ""
                    : "unread"
                );

                const action = item.action_url
                    ? `
                        <a
                            href="${escapeHtml(
                                item.action_url
                            )}"
                            class="notification-action"
                        >
                            Buka
                        </a>
                    `
                    : "";

                return `
                    <article
                        class="notification-item ${unreadClass}"
                    >
                        <div class="notification-icon">
                            ${escapeHtml(
                                item.notification_type
                                    .slice(0, 1)
                                    .toUpperCase()
                            )}
                        </div>

                        <div class="notification-content">
                            <div class="notification-heading">
                                <strong>
                                    ${escapeHtml(
                                        item.title
                                    )}
                                </strong>

                                <span>
                                    ${formatDate(
                                        item.created_at
                                    )}
                                </span>
                            </div>

                            <p>
                                ${escapeHtml(
                                    item.message
                                )}
                            </p>

                            <div class="notification-actions">
                                ${action}

                                ${
                                    item.read_at
                                    ? ""
                                    : `
                                        <button
                                            type="button"
                                            data-read="${
                                                item.notification_id
                                            }"
                                            class="secondary-button"
                                        >
                                            Tandai Dibaca
                                        </button>
                                    `
                                }

                                <button
                                    type="button"
                                    data-delete="${
                                        item.notification_id
                                    }"
                                    class="danger-button"
                                >
                                    Hapus
                                </button>
                            </div>
                        </div>
                    </article>
                `;
            })
            .join("")
    );

    document
        .querySelectorAll("[data-read]")
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const response = await fetch(
                        `/api/notifications/${
                            button.dataset.read
                        }/read`,
                        {
                            method: "POST",
                            body: new FormData(),
                        }
                    );

                    const result = await response.json();

                    showToast(
                        result.detail
                        || result.message
                    );

                    await loadNotifications();
                }
            );
        });

    document
        .querySelectorAll("[data-delete]")
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const response = await fetch(
                        `/api/notifications/${
                            button.dataset.delete
                        }`,
                        {
                            method: "DELETE",
                        }
                    );

                    const result = await response.json();

                    showToast(
                        result.detail
                        || result.message
                    );

                    await loadNotifications();
                }
            );
        });
}


async function loadNotifications() {
    const unreadOnly = document.getElementById(
        "unread-only"
    ).checked;

    const response = await fetch(
        "/api/notifications"
        + `?unread_only=${unreadOnly}`
    );

    if (response.status === 401) {
        window.location.href = "/login";
        return;
    }

    const data = await response.json();

    if (!response.ok) {
        notificationList.innerHTML = `
            <div class="error-state">
                ${escapeHtml(
                    data.detail
                    || "Notifikasi gagal dimuat."
                )}
            </div>
        `;

        return;
    }

    renderNotifications(data);
}


async function loadEmailStatus() {
    const response = await fetch(
        "/api/email/verification/status"
    );

    const data = await response.json();

    const container = document.getElementById(
        "email-status"
    );

    if (!response.ok) {
        container.textContent = (
            data.detail
            || "Status email gagal dimuat."
        );

        return;
    }

    container.innerHTML = `
        <strong>
            ${data.verified
                ? "Terverifikasi"
                : "Belum terverifikasi"}
        </strong>

        <span>
            ${escapeHtml(data.email)}
        </span>
    `;
}


async function loadDeliveryHealth() {
    const response = await fetch(
        "/api/notifications/health"
    );

    const data = await response.json();

    document.getElementById(
        "delivery-health"
    ).innerHTML = `
        <strong>
            Mode ${escapeHtml(
                data.delivery_mode
            )}
        </strong>

        <span>
            SMTP:
            ${data.smtp_configured
                ? "terkonfigurasi"
                : "belum dikonfigurasi"}
        </span>
    `;
}


async function confirmVerificationToken() {
    const parameters = new URLSearchParams(
        window.location.search
    );

    const token = parameters.get(
        "verify_token"
    );

    if (!token) {
        return;
    }

    const response = await fetch(
        "/api/email/verification/confirm"
        + `?token=${encodeURIComponent(token)}`
    );

    const data = await response.json();

    showToast(
        data.detail
        || data.message
    );

    window.history.replaceState(
        {},
        "",
        "/notifications"
    );

    await Promise.all([
        loadEmailStatus(),
        loadNotifications(),
    ]);
}


document
    .getElementById("unread-only")
    .addEventListener(
        "change",
        loadNotifications
    );


document
    .getElementById("mark-all-read")
    .addEventListener(
        "click",
        async () => {
            const response = await fetch(
                "/api/notifications/read-all",
                {
                    method: "POST",
                    body: new FormData(),
                }
            );

            const data = await response.json();

            showToast(
                data.detail
                || data.message
            );

            await loadNotifications();
        }
    );


document
    .getElementById("test-notification")
    .addEventListener(
        "click",
        async () => {
            const response = await fetch(
                "/api/notifications/test",
                {
                    method: "POST",
                    body: new FormData(),
                }
            );

            const data = await response.json();

            showToast(
                data.detail
                || "Notifikasi uji dibuat."
            );

            await loadNotifications();
        }
    );


document
    .getElementById("send-verification")
    .addEventListener(
        "click",
        async () => {
            const response = await fetch(
                "/api/email/verification/request",
                {
                    method: "POST",
                    body: new FormData(),
                }
            );

            const data = await response.json();

            showToast(
                data.detail
                || data.message
            );
        }
    );


async function initialize() {
    const loggedIn = await ensureLogin();

    if (!loggedIn) {
        return;
    }

    await Promise.all([
        loadNotifications(),
        loadEmailStatus(),
        loadDeliveryHealth(),
    ]);

    await confirmVerificationToken();
}


initialize();
