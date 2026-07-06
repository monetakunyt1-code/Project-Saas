const jobList = document.getElementById(
    "job-list"
);

const statusFilter = document.getElementById(
    "status-filter"
);

const toast = document.getElementById(
    "toast"
);

let jobs = [];


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


function operationLabel(operation) {
    const labels = {
        process: "Format Dokumen",
        batch: "Batch Processing",
        audit: "Audit Akademik",
        journal: "Journal Studio",
    };

    return labels[operation] || operation;
}


function statusLabel(status) {
    const labels = {
        queued: "Menunggu",
        running: "Berjalan",
        canceling: "Membatalkan",
        completed: "Selesai",
        failed: "Gagal",
        canceled: "Dibatalkan",
    };

    return labels[status] || status;
}


function formatDate(value) {
    if (!value) {
        return "-";
    }

    return new Date(value).toLocaleString(
        "id-ID"
    );
}


function renderSummary() {
    const statuses = {
        queued: 0,
        running: 0,
        completed: 0,
        failed: 0,
        canceled: 0,
    };

    jobs.forEach((job) => {
        if (
            job.status === "canceling"
        ) {
            statuses.running += 1;
        }
        else if (
            Object.hasOwn(
                statuses,
                job.status
            )
        ) {
            statuses[job.status] += 1;
        }
    });

    document.getElementById(
        "job-summary"
    ).innerHTML = `
        <article>
            <span>Total</span>
            <strong>${jobs.length}</strong>
        </article>

        <article>
            <span>Menunggu</span>
            <strong>${statuses.queued}</strong>
        </article>

        <article>
            <span>Berjalan</span>
            <strong>${statuses.running}</strong>
        </article>

        <article>
            <span>Selesai</span>
            <strong>${statuses.completed}</strong>
        </article>

        <article>
            <span>Gagal</span>
            <strong>${statuses.failed}</strong>
        </article>

        <article>
            <span>Dibatalkan</span>
            <strong>${statuses.canceled}</strong>
        </article>
    `;
}


function renderJobs() {
    const selectedStatus =
        statusFilter.value;

    const filteredJobs = jobs.filter(
        (job) => {
            if (!selectedStatus) {
                return true;
            }

            if (
                selectedStatus === "running"
            ) {
                return [
                    "running",
                    "canceling",
                ].includes(job.status);
            }

            return (
                job.status
                === selectedStatus
            );
        }
    );

    if (!filteredJobs.length) {
        jobList.innerHTML = `
            <div class="empty-state">
                Tidak ada pekerjaan pada filter ini.
            </div>
        `;

        return;
    }

    jobList.innerHTML = filteredJobs
        .map((job) => {
            const terminal = [
                "completed",
                "failed",
                "canceled",
            ].includes(job.status);

            const fileNames = (
                job.request_summary?.files
                || []
            )
                .map((file) => {
                    return escapeHtml(
                        file.filename
                    );
                })
                .join(", ");

            return `
                <article class="job-item">
                    <div class="job-main">
                        <div class="job-heading">
                            <div>
                                <h3>
                                    ${escapeHtml(
                                        operationLabel(
                                            job.operation
                                        )
                                    )}
                                </h3>

                                <p>
                                    ${
                                        fileNames
                                        || "Tanpa nama file"
                                    }
                                </p>
                            </div>

                            <span class="status ${
                                escapeHtml(job.status)
                            }">
                                ${escapeHtml(
                                    statusLabel(
                                        job.status
                                    )
                                )}
                            </span>
                        </div>

                        <p class="job-message">
                            ${escapeHtml(
                                job.message
                            )}
                        </p>

                        <div class="progress-row">
                            <div class="progress-track">
                                <div
                                    class="progress-bar"
                                    style="width:${
                                        Number(
                                            job.progress
                                            || 0
                                        )
                                    }%"
                                ></div>
                            </div>

                            <strong>
                                ${Number(
                                    job.progress
                                    || 0
                                )}%
                            </strong>
                        </div>

                        <div class="job-meta">
                            <span>
                                Dibuat:
                                ${formatDate(
                                    job.created_at
                                )}
                            </span>

                            <span>
                                Selesai:
                                ${formatDate(
                                    job.finished_at
                                )}
                            </span>
                        </div>

                        ${
                            job.error_message
                                ? `
                                    <div class="error-message">
                                        ${escapeHtml(
                                            job.error_message
                                        )}
                                    </div>
                                `
                                : ""
                        }
                    </div>

                    <div class="job-actions">
                        ${
                            !terminal
                                ? `
                                    <button
                                        type="button"
                                        class="danger-button"
                                        data-cancel="${
                                            job.job_id
                                        }"
                                    >
                                        Batalkan
                                    </button>
                                `
                                : ""
                        }

                        ${
                            job.artifact_path
                                ? `
                                    <a
                                        class="small-link"
                                        href="/api/background/jobs/${
                                            job.job_id
                                        }/artifact"
                                    >
                                        Unduh Hasil
                                    </a>
                                `
                                : ""
                        }

                        ${
                            terminal
                                ? `
                                    <button
                                        type="button"
                                        class="secondary-button"
                                        data-delete="${
                                            job.job_id
                                        }"
                                    >
                                        Hapus
                                    </button>
                                `
                                : ""
                        }
                    </div>
                </article>
            `;
        })
        .join("");

    document
        .querySelectorAll("[data-cancel]")
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const formData = new FormData();

                    const response = await fetch(
                        `/api/background/jobs/${
                            button.dataset.cancel
                        }/cancel`,
                        {
                            method: "POST",
                            body: formData,
                        }
                    );

                    const data = await response.json();

                    showToast(
                        data.detail
                        || data.message
                    );

                    await loadJobs();
                }
            );
        });

    document
        .querySelectorAll("[data-delete]")
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const confirmed = window.confirm(
                        "Hapus riwayat pekerjaan ini?"
                    );

                    if (!confirmed) {
                        return;
                    }

                    const response = await fetch(
                        `/api/background/jobs/${
                            button.dataset.delete
                        }`,
                        {
                            method: "DELETE",
                        }
                    );

                    const data = await response.json();

                    if (!response.ok) {
                        showToast(
                            data.detail
                            || "Riwayat gagal dihapus."
                        );

                        return;
                    }

                    showToast(data.message);

                    await loadJobs();
                }
            );
        });
}


async function loadJobs() {
    const response = await fetch(
        "/api/background/jobs?limit=200"
    );

    if (response.status === 401) {
        window.location.href = "/login";
        return;
    }

    const data = await response.json();

    if (!response.ok) {
        jobList.innerHTML = `
            <div class="error-state">
                ${escapeHtml(
                    data.detail
                    || "Pekerjaan gagal dimuat."
                )}
            </div>
        `;

        return;
    }

    jobs = data.jobs || [];

    document.getElementById(
        "workspace-label"
    ).textContent = (
        `Workspace: ${data.workspace.name}`
    );

    renderSummary();
    renderJobs();
}


statusFilter.addEventListener(
    "change",
    renderJobs
);

document
    .getElementById("refresh-jobs")
    .addEventListener(
        "click",
        loadJobs
    );

loadJobs();

setInterval(
    loadJobs,
    3000
);