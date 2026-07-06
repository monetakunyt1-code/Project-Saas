const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");

const auditForm = document.getElementById("audit-form");
const auditSubmit = document.getElementById("audit-submit");
const auditResult = document.getElementById("audit-result");
const auditHistory = document.getElementById("audit-history");
const documentType = document.getElementById("document-type");
const toast = document.getElementById("toast");


const defaultPolicies = {
    skripsi: {
        font: "Times New Roman",
        font_size: 12,
        line_spacing: 2,
        margin_top_cm: 4,
        margin_bottom_cm: 3,
        margin_left_cm: 4,
        margin_right_cm: 3,
    },
    laporan: {
        font: "Arial",
        font_size: 11,
        line_spacing: 1.5,
        margin_top_cm: 3,
        margin_bottom_cm: 3,
        margin_left_cm: 3,
        margin_right_cm: 3,
    },
    jurnal: {
        font: "Times New Roman",
        font_size: 11,
        line_spacing: 1.15,
        margin_top_cm: 2.5,
        margin_bottom_cm: 2.5,
        margin_left_cm: 2.5,
        margin_right_cm: 2.5,
    },
};


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


tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
        const target = tab.dataset.panel;

        tabs.forEach((item) => {
            item.classList.toggle(
                "active",
                item === tab
            );
        });

        panels.forEach((panel) => {
            panel.classList.toggle(
                "active",
                panel.id === `panel-${target}`
            );
        });

        if (target === "history") {
            loadAuditHistory();
        }
    });
});


documentType.addEventListener("change", () => {
    const policy = defaultPolicies[
        documentType.value
    ];

    if (!policy) {
        return;
    }

    document.getElementById("font").value =
        policy.font;

    document.getElementById("font-size").value =
        policy.font_size;

    document.getElementById("line-spacing").value =
        policy.line_spacing;

    document.getElementById("margin-top").value =
        policy.margin_top_cm;

    document.getElementById("margin-bottom").value =
        policy.margin_bottom_cm;

    document.getElementById("margin-left").value =
        policy.margin_left_cm;

    document.getElementById("margin-right").value =
        policy.margin_right_cm;
});


function findingPreview(findings) {
    if (!findings.length) {
        return `
            <div class="empty-state">
                Tidak ditemukan masalah utama.
            </div>
        `;
    }

    return findings
        .map((finding) => {
            return `
                <div class="finding">
                    <span class="severity ${
                        escapeHtml(finding.severity)
                    }">
                        ${escapeHtml(finding.severity)}
                    </span>

                    <div>
                        <strong>
                            ${escapeHtml(finding.title)}
                        </strong>

                        <p>
                            ${escapeHtml(finding.message)}
                        </p>
                    </div>
                </div>
            `;
        })
        .join("");
}


auditForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const formData = new FormData(auditForm);
    const file = auditForm.elements.file.files[0];

    if (!file) {
        showToast("Pilih dokumen Word terlebih dahulu.");
        return;
    }

    auditSubmit.disabled = true;
    auditSubmit.textContent = "Sedang Melakukan Audit...";

    auditResult.className = "result";
    auditResult.innerHTML = `
        <div class="loading">
            Dokumen sedang dianalisis. Jangan tutup halaman.
        </div>
    `;

    try {
        const response = await fetch(
            "/api/audit/document",
            {
                method: "POST",
                body: formData,
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Audit gagal."
            );
        }

        auditResult.className = "result success";

        auditResult.innerHTML = `
            <div class="score-summary">
                <div class="score-circle">
                    ${escapeHtml(data.score.score)}
                </div>

                <div>
                    <h3>
                        ${escapeHtml(data.score.grade)}
                    </h3>

                    <p>
                        Error:
                        <strong>
                            ${escapeHtml(data.score.errors)}
                        </strong>
                        · Warning:
                        <strong>
                            ${escapeHtml(data.score.warnings)}
                        </strong>
                        · Informasi:
                        <strong>
                            ${escapeHtml(data.score.information)}
                        </strong>
                    </p>
                </div>
            </div>

            <div class="result-actions">
                <a
                    class="action-link"
                    href="${data.html_report_url}"
                    target="_blank"
                >
                    Buka Laporan Visual
                </a>

                <a
                    class="action-link secondary"
                    href="${data.json_report_url}"
                >
                    Unduh JSON
                </a>
            </div>

            <h3>Temuan Utama</h3>

            <div class="finding-list">
                ${findingPreview(
                    data.findings_preview
                )}
            </div>
        `;

        await loadAuditHistory();

    } catch (error) {
        auditResult.className = "result error";

        auditResult.innerHTML = `
            <h3>Audit gagal</h3>
            <p>${escapeHtml(error.message)}</p>
        `;

    } finally {
        auditSubmit.disabled = false;
        auditSubmit.textContent =
            "Jalankan Audit Akademik";
    }
});


async function loadAuditHistory() {
    auditHistory.innerHTML = `
        <div class="loading">
            Memuat riwayat audit...
        </div>
    `;

    try {
        const response = await fetch("/api/audits");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                "Riwayat audit gagal dimuat."
            );
        }

        if (!data.audits.length) {
            auditHistory.innerHTML = `
                <div class="empty-state">
                    Belum ada dokumen yang diaudit.
                </div>
            `;

            return;
        }

        auditHistory.innerHTML = data.audits
            .map((audit) => {
                return `
                    <div class="history-item">
                        <div>
                            <h3>
                                ${escapeHtml(
                                    audit.original_name
                                )}
                            </h3>

                            <p>
                                ${escapeHtml(
                                    audit.document_type
                                )}
                                ·
                                ${new Date(
                                    audit.created_at
                                ).toLocaleString("id-ID")}
                            </p>

                            <div class="history-status">
                                <span>
                                    Skor ${escapeHtml(audit.score)}
                                </span>

                                <span>
                                    ${escapeHtml(audit.grade)}
                                </span>

                                <span>
                                    ${escapeHtml(
                                        audit.findings_total
                                    )} temuan
                                </span>
                            </div>
                        </div>

                        <div class="history-actions">
                            <a
                                class="small-button"
                                href="${audit.html_report_url}"
                                target="_blank"
                            >
                                Laporan
                            </a>

                            <a
                                class="small-button secondary"
                                href="${audit.json_report_url}"
                            >
                                JSON
                            </a>

                            <button
                                class="danger-button"
                                type="button"
                                data-delete-audit="${
                                    audit.audit_id
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
            .querySelectorAll("[data-delete-audit]")
            .forEach((button) => {
                button.addEventListener(
                    "click",
                    async () => {
                        const confirmed = window.confirm(
                            "Hapus riwayat audit ini?"
                        );

                        if (!confirmed) {
                            return;
                        }

                        const response = await fetch(
                            `/api/audits/${
                                button.dataset.deleteAudit
                            }`,
                            {
                                method: "DELETE",
                            }
                        );

                        if (!response.ok) {
                            const data =
                                await response.json();

                            showToast(
                                data.detail ||
                                "Audit gagal dihapus."
                            );

                            return;
                        }

                        await loadAuditHistory();
                        showToast(
                            "Riwayat audit berhasil dihapus."
                        );
                    }
                );
            });

    } catch (error) {
        auditHistory.innerHTML = `
            <div class="error-state">
                ${escapeHtml(error.message)}
            </div>
        `;
    }
}


document
    .getElementById("refresh-history")
    .addEventListener(
        "click",
        loadAuditHistory
    );