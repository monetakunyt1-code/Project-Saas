const overallStatus = document.getElementById(
    "overall-status"
);

const toast = document.getElementById(
    "toast"
);

let currentHealth = null;
let currentBackups = [];


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


function formatBytes(value) {
    let number = Number(value || 0);

    const units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ];

    let unitIndex = 0;

    while (
        number >= 1024
        && unitIndex < units.length - 1
    ) {
        number /= 1024;
        unitIndex += 1;
    }

    return (
        `${number.toFixed(
            unitIndex ? 1 : 0
        )} ${units[unitIndex]}`
    );
}


function formatDuration(seconds) {
    const value = Number(seconds || 0);

    const days = Math.floor(
        value / 86400
    );

    const hours = Math.floor(
        (value % 86400) / 3600
    );

    const minutes = Math.floor(
        (value % 3600) / 60
    );

    return `${days}h ${hours}j ${minutes}m`;
}


function formatDate(value) {
    if (!value) {
        return "-";
    }

    return new Date(value).toLocaleString(
        "id-ID"
    );
}


async function requireAdmin() {
    const response = await fetch(
        "/api/auth/me"
    );

    if (!response.ok) {
        window.location.href = "/login";
        return false;
    }

    const data = await response.json();

    if (data.user.role !== "admin") {
        document.querySelector(
            "main"
        ).innerHTML = `
            <article class="card">
                <h1>Akses administrator diperlukan</h1>

                <p>
                    Halaman ini hanya tersedia untuk
                    administrator sistem.
                </p>
            </article>
        `;

        return false;
    }

    return true;
}


function renderSummary() {
    const metrics = (
        currentHealth.requests_24h
    );

    const disk = currentHealth.disk;

    document.getElementById(
        "summary-grid"
    ).innerHTML = `
        <article>
            <span>Uptime</span>

            <strong>
                ${formatDuration(
                    currentHealth.uptime_seconds
                )}
            </strong>
        </article>

        <article>
            <span>Request 24 Jam</span>

            <strong>
                ${escapeHtml(
                    metrics.request_count
                )}
            </strong>
        </article>

        <article>
            <span>Rata-rata Respons</span>

            <strong>
                ${Number(
                    metrics.average_duration_ms
                ).toFixed(1)} ms
            </strong>
        </article>

        <article>
            <span>Server Error</span>

            <strong>
                ${escapeHtml(
                    metrics.server_error_count
                )}
            </strong>
        </article>

        <article>
            <span>Database</span>

            <strong>
                ${escapeHtml(
                    currentHealth.database_count
                )}
            </strong>
        </article>

        <article>
            <span>Disk Tersisa</span>

            <strong>
                ${formatBytes(
                    disk.free_bytes
                )}
            </strong>
        </article>
    `;
}


function renderDatabases() {
    const container = document.getElementById(
        "database-health"
    );

    if (!currentHealth.databases.length) {
        container.innerHTML = `
            <div class="empty-state">
                Tidak ada database terdeteksi.
            </div>
        `;

        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Database</th>
                    <th>Status</th>
                    <th>Ukuran</th>
                    <th>Keterangan</th>
                </tr>
            </thead>

            <tbody>
                ${currentHealth.databases
                    .map((database) => {
                        return `
                            <tr>
                                <td>
                                    <code>
                                        ${escapeHtml(
                                            database.database
                                        )}
                                    </code>
                                </td>

                                <td>
                                    <span class="status ${
                                        escapeHtml(
                                            database.status
                                        )
                                    }">
                                        ${escapeHtml(
                                            database.status
                                        )}
                                    </span>
                                </td>

                                <td>
                                    ${formatBytes(
                                        database.size_bytes
                                    )}
                                </td>

                                <td>
                                    ${escapeHtml(
                                        database.message
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


function renderMetrics() {
    const paths = (
        currentHealth
            .requests_24h
            .top_paths
        || []
    );

    const container = document.getElementById(
        "endpoint-metrics"
    );

    if (!paths.length) {
        container.innerHTML = `
            <div class="empty-state">
                Belum ada metrik request.
            </div>
        `;

        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Method</th>
                    <th>Endpoint</th>
                    <th>Request</th>
                    <th>Rata-rata</th>
                    <th>Maksimum</th>
                </tr>
            </thead>

            <tbody>
                ${paths.map((item) => {
                    return `
                        <tr>
                            <td>
                                ${escapeHtml(
                                    item.method
                                )}
                            </td>

                            <td>
                                <code>
                                    ${escapeHtml(
                                        item.path
                                    )}
                                </code>
                            </td>

                            <td>
                                ${escapeHtml(
                                    item.request_count
                                )}
                            </td>

                            <td>
                                ${Number(
                                    item.average_duration_ms
                                ).toFixed(1)}
                                ms
                            </td>

                            <td>
                                ${Number(
                                    item.maximum_duration_ms
                                ).toFixed(1)}
                                ms
                            </td>
                        </tr>
                    `;
                }).join("")}
            </tbody>
        </table>
    `;
}


function renderBackgroundJobs() {
    const jobs = currentHealth.background_jobs;

    const container = document.getElementById(
        "background-summary"
    );

    if (!jobs.available) {
        container.innerHTML = `
            <div class="empty-state">
                Database background job belum tersedia.
            </div>
        `;

        return;
    }

    container.innerHTML = `
        <div class="mini-grid">
            <div>
                <span>Menunggu</span>
                <strong>${jobs.queued || 0}</strong>
            </div>

            <div>
                <span>Berjalan</span>
                <strong>${jobs.running || 0}</strong>
            </div>

            <div>
                <span>Selesai</span>
                <strong>${jobs.completed || 0}</strong>
            </div>

            <div>
                <span>Gagal</span>
                <strong>${jobs.failed || 0}</strong>
            </div>
        </div>
    `;
}


async function loadErrors() {
    const unresolvedOnly = (
        document.getElementById(
            "unresolved-only"
        ).checked
    );

    const response = await fetch(
        "/api/system/errors"
        + "?limit=100"
        + `&unresolved_only=${unresolvedOnly}`
    );

    const data = await response.json();

    const container = document.getElementById(
        "error-list"
    );

    if (!response.ok) {
        container.innerHTML = `
            <div class="error-state">
                ${escapeHtml(
                    data.detail
                    || "Error gagal dimuat."
                )}
            </div>
        `;

        return;
    }

    if (!data.errors.length) {
        container.innerHTML = `
            <div class="empty-state">
                Tidak ada error pada filter ini.
            </div>
        `;

        return;
    }

    container.innerHTML = data.errors
        .map((error) => {
            return `
                <article class="error-item">
                    <div>
                        <div class="error-heading">
                            <strong>
                                ${escapeHtml(
                                    error.error_type
                                )}
                            </strong>

                            <span>
                                ${formatDate(
                                    error.created_at
                                )}
                            </span>
                        </div>

                        <p>
                            ${escapeHtml(
                                error.message
                            )}
                        </p>

                        <code>
                            ${escapeHtml(
                                error.method
                            )}
                            ${escapeHtml(
                                error.path
                            )}
                        </code>
                    </div>

                    ${
                        error.resolved
                            ? `
                                <span class="resolved">
                                    Selesai
                                </span>
                            `
                            : `
                                <button
                                    type="button"
                                    class="secondary-button"
                                    data-resolve-error="${
                                        error.error_id
                                    }"
                                >
                                    Tandai Selesai
                                </button>
                            `
                    }
                </article>
            `;
        })
        .join("");

    document
        .querySelectorAll(
            "[data-resolve-error]"
        )
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const formData = new FormData();

                    const response = await fetch(
                        `/api/system/errors/${
                            button.dataset
                                .resolveError
                        }/resolve`,
                        {
                            method: "POST",
                            body: formData,
                        }
                    );

                    const result = await response.json();

                    showToast(
                        result.detail
                        || result.message
                    );

                    await loadErrors();
                }
            );
        });
}


function renderBackups() {
    const container = document.getElementById(
        "backup-list"
    );

    if (!currentBackups.length) {
        container.innerHTML = `
            <div class="empty-state">
                Belum ada backup.
            </div>
        `;

        return;
    }

    container.innerHTML = currentBackups
        .map((backup) => {
            return `
                <article class="backup-item">
                    <div>
                        <strong>
                            ${escapeHtml(
                                backup.label
                            )}
                        </strong>

                        <span>
                            ${formatDate(
                                backup.created_at
                            )}
                        </span>

                        <small>
                            ${escapeHtml(
                                backup.database_count
                            )}
                            database ·
                            ${formatBytes(
                                backup.archive_size_bytes
                            )}
                        </small>
                    </div>

                    <div class="backup-actions">
                        <a
                            href="/api/system/backups/${
                                backup.backup_id
                            }/download"
                        >
                            Unduh
                        </a>

                        <button
                            type="button"
                            data-verify-backup="${
                                backup.backup_id
                            }"
                        >
                            Verifikasi
                        </button>

                        <button
                            type="button"
                            data-restore-plan="${
                                backup.backup_id
                            }"
                        >
                            Restore
                        </button>

                        <button
                            type="button"
                            class="danger-button"
                            data-delete-backup="${
                                backup.backup_id
                            }"
                        >
                            Hapus
                        </button>
                    </div>
                </article>
            `;
        })
        .join("");

    document
        .querySelectorAll(
            "[data-verify-backup]"
        )
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const response = await fetch(
                        `/api/system/backups/${
                            button.dataset
                                .verifyBackup
                        }/verify`
                    );

                    const data = await response.json();

                    if (!response.ok) {
                        showToast(
                            data.detail
                            || "Verifikasi gagal."
                        );

                        return;
                    }

                    showToast(
                        data.valid
                            ? (
                                "Backup valid. "
                                + `${data.verified_databases}`
                                + " database terverifikasi."
                            )
                            : (
                                "Backup bermasalah: "
                                + data.problems.join("; ")
                            )
                    );
                }
            );
        });

    document
        .querySelectorAll(
            "[data-restore-plan]"
        )
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const response = await fetch(
                        `/api/system/backups/${
                            button.dataset
                                .restorePlan
                        }/restore-plan`
                    );

                    const data = await response.json();

                    if (!response.ok) {
                        showToast(
                            data.detail
                            || "Restore plan gagal."
                        );

                        return;
                    }

                    window.prompt(
                        "Hentikan server, lalu jalankan perintah berikut:",
                        data.restore_command
                    );
                }
            );
        });

    document
        .querySelectorAll(
            "[data-delete-backup]"
        )
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const confirmed = window.confirm(
                        "Hapus backup ini secara permanen?"
                    );

                    if (!confirmed) {
                        return;
                    }

                    const response = await fetch(
                        `/api/system/backups/${
                            button.dataset
                                .deleteBackup
                        }`,
                        {
                            method: "DELETE",
                        }
                    );

                    const data = await response.json();

                    if (!response.ok) {
                        showToast(
                            data.detail
                            || "Backup gagal dihapus."
                        );

                        return;
                    }

                    showToast(data.message);

                    await loadBackups();
                }
            );
        });
}


async function loadHealth() {
    const response = await fetch(
        "/api/system/health/detail"
    );

    if (response.status === 401) {
        window.location.href = "/login";
        return;
    }

    const data = await response.json();

    if (!response.ok) {
        showToast(
            data.detail
            || "System health gagal dimuat."
        );

        return;
    }

    currentHealth = data;

    overallStatus.textContent =
        data.status;

    overallStatus.className = (
        `overall-status ${data.status}`
    );

    renderSummary();
    renderDatabases();
    renderMetrics();
    renderBackgroundJobs();
}


async function loadBackups() {
    const response = await fetch(
        "/api/system/backups"
    );

    const data = await response.json();

    if (!response.ok) {
        showToast(
            data.detail
            || "Backup gagal dimuat."
        );

        return;
    }

    currentBackups = data.backups || [];

    renderBackups();
}


document
    .getElementById("backup-form")
    .addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const message = document.getElementById(
                "backup-message"
            );

            message.className = "message";
            message.textContent = (
                "Membuat backup database..."
            );

            const response = await fetch(
                "/api/system/backups",
                {
                    method: "POST",
                    body: new FormData(
                        event.currentTarget
                    ),
                }
            );

            const data = await response.json();

            if (!response.ok) {
                message.className =
                    "message error";

                message.textContent = (
                    data.detail
                    || "Backup gagal."
                );

                return;
            }

            message.className =
                "message success";

            message.textContent = (
                data.message
            );

            await Promise.all([
                loadHealth(),
                loadBackups(),
            ]);
        }
    );


document
    .getElementById("prune-form")
    .addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const confirmed = window.confirm(
                "Hapus backup yang melebihi jumlah simpan?"
            );

            if (!confirmed) {
                return;
            }

            const response = await fetch(
                "/api/system/backups/prune",
                {
                    method: "POST",
                    body: new FormData(
                        event.currentTarget
                    ),
                }
            );

            const data = await response.json();

            if (!response.ok) {
                showToast(
                    data.detail
                    || "Pembersihan gagal."
                );

                return;
            }

            showToast(
                `${data.removed_total} backup lama dihapus.`
            );

            await loadBackups();
        }
    );


document
    .getElementById("unresolved-only")
    .addEventListener(
        "change",
        loadErrors
    );


document
    .getElementById("refresh-system")
    .addEventListener(
        "click",
        async () => {
            await Promise.all([
                loadHealth(),
                loadErrors(),
                loadBackups(),
            ]);

            showToast(
                "Status sistem diperbarui."
            );
        }
    );


async function initialize() {
    const allowed = await requireAdmin();

    if (!allowed) {
        return;
    }

    await Promise.all([
        loadHealth(),
        loadErrors(),
        loadBackups(),
    ]);
}


initialize();

setInterval(
    loadHealth,
    15000
);