const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");

const dashboardMetrics = document.getElementById(
    "dashboard-metrics"
);

const recentJobs = document.getElementById(
    "recent-jobs"
);

const batchForm = document.getElementById(
    "batch-form"
);

const batchSubmit = document.getElementById(
    "batch-submit"
);

const batchResult = document.getElementById(
    "batch-result"
);

const profileForm = document.getElementById(
    "profile-form"
);

const profileMessage = document.getElementById(
    "profile-message"
);

const profileList = document.getElementById(
    "profile-list"
);

const batchList = document.getElementById(
    "batch-list"
);

const batchProfile = document.getElementById(
    "batch-profile"
);

const batchTemplate = document.getElementById(
    "batch-template"
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


function formatBytes(bytes) {
    const value = Number(bytes || 0);

    if (value < 1024) {
        return `${value} B`;
    }

    if (value < 1024 * 1024) {
        return `${(value / 1024).toFixed(1)} KB`;
    }

    if (value < 1024 * 1024 * 1024) {
        return `${(
            value / (1024 * 1024)
        ).toFixed(1)} MB`;
    }

    return `${(
        value / (1024 * 1024 * 1024)
    ).toFixed(2)} GB`;
}


function showToast(message) {
    toast.textContent = message;
    toast.classList.remove("hidden");

    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3500);
}


function setPanel(panelName) {
    tabs.forEach((tab) => {
        tab.classList.toggle(
            "active",
            tab.dataset.panel === panelName
        );
    });

    panels.forEach((panel) => {
        panel.classList.toggle(
            "active",
            panel.id === `panel-${panelName}`
        );
    });

    if (panelName === "dashboard") {
        loadDashboard();
    }

    if (panelName === "profiles") {
        loadProfiles();
    }

    if (panelName === "batches") {
        loadBatches();
    }

    if (panelName === "batch") {
        loadProfiles();
        loadTemplates();
    }
}


tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
        setPanel(tab.dataset.panel);
    });
});


function metricCard(label, value) {
    return `
        <article class="metric-card">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
        </article>
    `;
}


async function loadDashboard() {
    dashboardMetrics.innerHTML = `
        <div class="loading">
            Memuat statistik...
        </div>
    `;

    recentJobs.innerHTML = `
        <div class="loading">
            Memuat pekerjaan terbaru...
        </div>
    `;

    try {
        const response = await fetch("/api/dashboard");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Dashboard gagal dimuat."
            );
        }

        const summary = data.summary;

        dashboardMetrics.innerHTML = [
            metricCard(
                "Total Pekerjaan",
                summary.jobs_total
            ),
            metricCard(
                "Berhasil",
                summary.jobs_completed
            ),
            metricCard(
                "Gagal",
                summary.jobs_failed
            ),
            metricCard(
                "Profil Format",
                summary.profiles_total
            ),
            metricCard(
                "Template",
                summary.templates_total
            ),
            metricCard(
                "Batch",
                summary.batches_total
            ),
            metricCard(
                "File Batch Berhasil",
                summary.batch_files_success
            ),
            metricCard(
                "Penyimpanan Hasil",
                formatBytes(summary.output_size_bytes)
            ),
        ].join("");

        if (!data.recent_jobs.length) {
            recentJobs.innerHTML = `
                <div class="empty-state">
                    Belum ada dokumen yang diproses.
                </div>
            `;

            return;
        }

        recentJobs.innerHTML = data.recent_jobs
            .map((job) => {
                const actions = job.status === "completed"
                    ? `
                        <a
                            class="small-button"
                            href="${job.download_url}"
                        >
                            Dokumen
                        </a>

                        <a
                            class="small-button secondary"
                            href="${job.html_report_url}"
                            target="_blank"
                        >
                            Laporan Visual
                        </a>

                        <a
                            class="small-button secondary"
                            href="${job.json_report_url}"
                        >
                            JSON
                        </a>
                    `
                    : "";

                return `
                    <div class="list-item">
                        <div>
                            <h3>
                                ${escapeHtml(job.original_name)}
                            </h3>

                            <p>
                                ${escapeHtml(job.mode)}
                                ·
                                ${escapeHtml(job.preset)}
                                ·
                                ${new Date(
                                    job.created_at
                                ).toLocaleString("id-ID")}
                            </p>

                            <span class="status">
                                ${escapeHtml(job.status)}
                            </span>
                        </div>

                        <div class="list-actions">
                            ${actions}
                        </div>
                    </div>
                `;
            })
            .join("");

    } catch (error) {
        dashboardMetrics.innerHTML = `
            <div class="error-state">
                ${escapeHtml(error.message)}
            </div>
        `;

        recentJobs.innerHTML = "";
    }
}


function collectProfileRules(form) {
    const fields = [
        "font",
        "font_size",
        "table_font_size",
        "line_spacing",
        "first_line_indent_cm",
        "margin_top_cm",
        "margin_bottom_cm",
        "margin_left_cm",
        "margin_right_cm",
        "heading_1_size",
        "heading_2_size",
        "heading_3_size",
    ];

    const rules = {};

    fields.forEach((fieldName) => {
        const field = form.elements[fieldName];

        if (!field) {
            return;
        }

        const value = field.value.trim();

        if (!value) {
            return;
        }

        rules[fieldName] = fieldName === "font"
            ? value
            : Number(value);
    });

    return rules;
}


profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = {
        name: profileForm.elements.name.value.trim(),
        description:
            profileForm.elements.description.value.trim(),
        rules: collectProfileRules(profileForm),
    };

    profileMessage.classList.remove("hidden");
    profileMessage.textContent = "Menyimpan profil...";

    try {
        const response = await fetch(
            "/api/profiles",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(payload),
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Profil gagal disimpan."
            );
        }

        profileMessage.textContent =
            "Profil format berhasil disimpan.";

        profileForm.reset();

        profileForm.elements.font.value =
            "Times New Roman";

        profileForm.elements.font_size.value = "12";
        profileForm.elements.table_font_size.value = "10";
        profileForm.elements.line_spacing.value = "2";
        profileForm.elements.first_line_indent_cm.value =
            "1.25";
        profileForm.elements.margin_top_cm.value = "4";
        profileForm.elements.margin_bottom_cm.value = "3";
        profileForm.elements.margin_left_cm.value = "4";
        profileForm.elements.margin_right_cm.value = "3";
        profileForm.elements.heading_1_size.value = "14";
        profileForm.elements.heading_2_size.value = "12";
        profileForm.elements.heading_3_size.value = "12";

        await loadProfiles();

    } catch (error) {
        profileMessage.textContent = error.message;
    }
});


async function loadProfiles() {
    try {
        const response = await fetch("/api/profiles");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Profil gagal dimuat."
            );
        }

        batchProfile.innerHTML = `
            <option value="">
                Tanpa profil khusus
            </option>
        `;

        data.profiles.forEach((profile) => {
            const option = document.createElement(
                "option"
            );

            option.value = profile.profile_id;
            option.textContent = profile.name;

            batchProfile.appendChild(option);
        });

        if (!data.profiles.length) {
            profileList.innerHTML = `
                <div class="empty-state">
                    Belum ada profil format.
                </div>
            `;

            return;
        }

        profileList.innerHTML = data.profiles
            .map((profile) => {
                const ruleRows = Object.entries(
                    profile.rules || {}
                )
                    .map(([key, value]) => {
                        return `
                            <span class="rule-chip">
                                ${escapeHtml(key)}:
                                ${escapeHtml(value)}
                            </span>
                        `;
                    })
                    .join("");

                return `
                    <div class="list-item vertical">
                        <div>
                            <h3>
                                ${escapeHtml(profile.name)}
                            </h3>

                            <p>
                                ${escapeHtml(
                                    profile.description ||
                                    "Tanpa deskripsi"
                                )}
                            </p>

                            <div class="rule-list">
                                ${ruleRows}
                            </div>
                        </div>

                        <div class="list-actions">
                            <button
                                class="danger-button"
                                type="button"
                                data-delete-profile="${
                                    profile.profile_id
                                }"
                            >
                                Hapus
                            </button>
                        </div>
                    </div>
                `;
            })
            .join("");

        document
            .querySelectorAll("[data-delete-profile]")
            .forEach((button) => {
                button.addEventListener(
                    "click",
                    async () => {
                        const confirmed = window.confirm(
                            "Hapus profil format ini?"
                        );

                        if (!confirmed) {
                            return;
                        }

                        const response = await fetch(
                            `/api/profiles/${
                                button.dataset.deleteProfile
                            }`,
                            {
                                method: "DELETE",
                            }
                        );

                        if (!response.ok) {
                            const data = await response.json();

                            showToast(
                                data.detail ||
                                "Profil gagal dihapus."
                            );

                            return;
                        }

                        await loadProfiles();
                        showToast(
                            "Profil berhasil dihapus."
                        );
                    }
                );
            });

    } catch (error) {
        profileList.innerHTML = `
            <div class="error-state">
                ${escapeHtml(error.message)}
            </div>
        `;
    }
}


async function loadTemplates() {
    try {
        const response = await fetch("/api/templates");
        const data = await response.json();

        batchTemplate.innerHTML = `
            <option value="">
                Tanpa template khusus
            </option>
        `;

        data.templates.forEach((template) => {
            const option = document.createElement(
                "option"
            );

            option.value = template.template_id;

            option.textContent =
                template.template_name +
                (
                    template.institution_name
                        ? ` — ${template.institution_name}`
                        : ""
                );

            batchTemplate.appendChild(option);
        });

    } catch (error) {
        showToast(
            `Template gagal dimuat: ${error.message}`
        );
    }
}


function collectCustomRules() {
    const rules = {};

    document
        .querySelectorAll("[data-custom-rule]")
        .forEach((field) => {
            const value = field.value.trim();

            if (!value) {
                return;
            }

            const key = field.dataset.customRule;

            rules[key] = key === "font"
                ? value
                : Number(value);
        });

    return rules;
}


function setBooleanFormValue(
    formData,
    form,
    fieldName
) {
    const field = form.querySelector(
        `[name="${fieldName}"]`
    );

    formData.set(
        fieldName,
        field && field.checked ? "true" : "false"
    );
}


batchForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const selectedFiles =
        batchForm.elements.files.files;

    if (!selectedFiles.length) {
        showToast(
            "Pilih sedikitnya satu dokumen."
        );

        return;
    }

    if (selectedFiles.length > 20) {
        showToast(
            "Batch maksimal berisi 20 dokumen."
        );

        return;
    }

    const formData = new FormData();

    Array.from(selectedFiles).forEach((file) => {
        formData.append("files", file);
    });

    formData.append(
        "mode",
        batchForm.elements.mode.value
    );

    formData.append(
        "preset",
        batchForm.elements.preset.value
    );

    formData.append(
        "profile_id",
        batchForm.elements.profile_id.value
    );

    formData.append(
        "template_id",
        batchForm.elements.template_id.value
    );

    formData.append(
        "custom_rules_json",
        JSON.stringify(
            collectCustomRules()
        )
    );

    [
        "include_toc",
        "include_table_list",
        "include_figure_list",
        "include_appendix_list",
        "include_page_numbers",
    ].forEach((fieldName) => {
        setBooleanFormValue(
            formData,
            batchForm,
            fieldName
        );
    });

    batchSubmit.disabled = true;
    batchSubmit.textContent =
        "Sedang Memproses Batch...";

    batchResult.classList.remove("hidden");
    batchResult.className = "message";
    batchResult.textContent =
        "Dokumen sedang diproses. Jangan tutup halaman.";

    try {
        const response = await fetch(
            "/api/batch/process",
            {
                method: "POST",
                body: formData,
            }
        );

        const data = await response.json();

        if (!response.ok) {
            const detail = typeof data.detail === "string"
                ? data.detail
                : data.detail?.message ||
                  "Batch gagal diproses.";

            throw new Error(detail);
        }

        const failureText = data.failed_count
            ? `
                <p>
                    ${data.failed_count} file gagal.
                    Rincian tersedia dalam ringkasan ZIP.
                </p>
            `
            : "";

        batchResult.className = "message success";

        batchResult.innerHTML = `
            <h3>Batch berhasil diproses</h3>

            <p>
                Berhasil:
                <strong>${data.success_count}</strong>
                dari
                <strong>${data.total_files}</strong>
                dokumen.
            </p>

            ${failureText}

            <a
                class="primary-link"
                href="${data.download_url}"
            >
                Unduh Hasil ZIP
            </a>
        `;

        await loadDashboard();
        await loadBatches();

    } catch (error) {
        batchResult.className = "message error";

        batchResult.innerHTML = `
            <h3>Batch gagal diproses</h3>
            <p>${escapeHtml(error.message)}</p>
        `;

    } finally {
        batchSubmit.disabled = false;
        batchSubmit.textContent =
            "Proses Semua Dokumen";
    }
});


async function loadBatches() {
    batchList.innerHTML = `
        <div class="loading">
            Memuat riwayat batch...
        </div>
    `;

    try {
        const response = await fetch("/api/batches");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                "Riwayat batch gagal dimuat."
            );
        }

        if (!data.batches.length) {
            batchList.innerHTML = `
                <div class="empty-state">
                    Belum ada batch yang diproses.
                </div>
            `;

            return;
        }

        batchList.innerHTML = data.batches
            .map((batch) => {
                const failureInfo = batch.failed_count
                    ? `
                        <span class="status danger">
                            ${batch.failed_count} gagal
                        </span>
                    `
                    : "";

                return `
                    <div class="list-item">
                        <div>
                            <h3>
                                Batch ${escapeHtml(
                                    batch.batch_id.slice(0, 8)
                                )}
                            </h3>

                            <p>
                                Mode:
                                ${escapeHtml(batch.mode)}
                                · Preset:
                                ${escapeHtml(batch.preset)}
                                ·
                                ${new Date(
                                    batch.created_at
                                ).toLocaleString("id-ID")}
                            </p>

                            <span class="status">
                                ${batch.success_count} berhasil
                            </span>

                            ${failureInfo}
                        </div>

                        <div class="list-actions">
                            <a
                                class="small-button"
                                href="${batch.download_url}"
                            >
                                Unduh ZIP
                            </a>

                            <button
                                class="danger-button"
                                type="button"
                                data-delete-batch="${
                                    batch.batch_id
                                }"
                            >
                                Hapus
                            </button>
                        </div>
                    </div>
                `;
            })
            .join("");

        document
            .querySelectorAll("[data-delete-batch]")
            .forEach((button) => {
                button.addEventListener(
                    "click",
                    async () => {
                        const confirmed = window.confirm(
                            "Hapus riwayat dan ZIP batch ini?"
                        );

                        if (!confirmed) {
                            return;
                        }

                        const response = await fetch(
                            `/api/batches/${
                                button.dataset.deleteBatch
                            }`,
                            {
                                method: "DELETE",
                            }
                        );

                        if (!response.ok) {
                            const data = await response.json();

                            showToast(
                                data.detail ||
                                "Batch gagal dihapus."
                            );

                            return;
                        }

                        await loadBatches();
                        await loadDashboard();

                        showToast(
                            "Riwayat batch berhasil dihapus."
                        );
                    }
                );
            });

    } catch (error) {
        batchList.innerHTML = `
            <div class="error-state">
                ${escapeHtml(error.message)}
            </div>
        `;
    }
}


document
    .getElementById("refresh-dashboard")
    .addEventListener(
        "click",
        loadDashboard
    );

document
    .getElementById("refresh-profiles")
    .addEventListener(
        "click",
        loadProfiles
    );

document
    .getElementById("refresh-batches")
    .addEventListener(
        "click",
        loadBatches
    );


loadDashboard();
loadProfiles();
loadTemplates();