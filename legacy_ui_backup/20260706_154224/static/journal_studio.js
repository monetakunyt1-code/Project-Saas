const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");

const journalForm = document.getElementById(
    "journal-form"
);

const journalSubmit = document.getElementById(
    "journal-submit"
);

const journalResult = document.getElementById(
    "journal-result"
);

const journalHistory = document.getElementById(
    "journal-history"
);

const journalTemplate = document.getElementById(
    "journal-template"
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
            loadHistory();
        }
    });
});


async function loadTemplates() {
    try {
        const response = await fetch("/api/templates");
        const data = await response.json();

        journalTemplate.innerHTML = `
            <option value="">
                Gunakan format jurnal bawaan
            </option>
        `;

        data.templates
            .filter((template) => {
                return (
                    template.document_type === "jurnal"
                    || template.document_type === "journal"
                );
            })
            .forEach((template) => {
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

                journalTemplate.appendChild(option);
            });

    } catch (error) {
        showToast(
            `Template gagal dimuat: ${error.message}`
        );
    }
}


journalForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const selectedFile =
        journalForm.elements.file.files[0];

    if (!selectedFile) {
        showToast(
            "Pilih dokumen Word terlebih dahulu."
        );

        return;
    }

    const formData = new FormData(journalForm);

    formData.set(
        "include_literature",
        journalForm.elements.include_literature.checked
            ? "true"
            : "false"
    );

    journalSubmit.disabled = true;
    journalSubmit.textContent =
        "Sedang Membuat Draft...";

    journalResult.className = "result";
    journalResult.innerHTML = `
        <div class="loading">
            Dokumen sedang dipetakan dan diringkas.
            Jangan tutup halaman.
        </div>
    `;

    try {
        const response = await fetch(
            "/api/journal/build",
            {
                method: "POST",
                body: formData,
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                "Draft jurnal gagal dibuat."
            );
        }

        const sectionRows = Object.entries(
            data.section_word_counts
        )
            .map(([section, words]) => {
                return `
                    <div class="word-item">
                        <span>
                            ${escapeHtml(section)}
                        </span>

                        <strong>
                            ${escapeHtml(words)} kata
                        </strong>
                    </div>
                `;
            })
            .join("");

        const warnings = data.warnings.length
            ? `
                <div class="warning-box">
                    <strong>Peringatan</strong>

                    <ul>
                        ${data.warnings
                            .map((warning) => {
                                return `
                                    <li>
                                        ${escapeHtml(warning)}
                                    </li>
                                `;
                            })
                            .join("")}
                    </ul>
                </div>
            `
            : "";

        journalResult.className = "result success";

        journalResult.innerHTML = `
            <div class="result-heading">
                <div>
                    <h3>Draft jurnal berhasil dibuat</h3>

                    <p>
                        ${escapeHtml(data.title)}
                    </p>
                </div>

                <div class="word-total">
                    <strong>
                        ${escapeHtml(
                            data.output_total_words
                        )}
                    </strong>

                    <span>kata hasil</span>
                </div>
            </div>

            <p>
                Dokumen sumber:
                <strong>
                    ${escapeHtml(
                        data.source_total_words
                    )} kata
                </strong>
            </p>

            <div class="word-grid">
                ${sectionRows}
            </div>

            ${warnings}

            <div class="result-actions">
                <a
                    class="action-link"
                    href="${data.download_url}"
                >
                    Unduh Draft Jurnal
                </a>

                <a
                    class="action-link secondary"
                    href="${data.report_url}"
                >
                    Unduh Laporan JSON
                </a>
            </div>
        `;

        await loadHistory();

    } catch (error) {
        journalResult.className = "result error";

        journalResult.innerHTML = `
            <h3>Transformasi gagal</h3>
            <p>${escapeHtml(error.message)}</p>
        `;

    } finally {
        journalSubmit.disabled = false;
        journalSubmit.textContent =
            "Buat Draft Artikel Jurnal";
    }
});


async function loadHistory() {
    journalHistory.innerHTML = `
        <div class="loading">
            Memuat riwayat draft jurnal...
        </div>
    `;

    try {
        const response = await fetch(
            "/api/journal/jobs"
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                "Riwayat jurnal gagal dimuat."
            );
        }

        if (!data.jobs.length) {
            journalHistory.innerHTML = `
                <div class="empty-state">
                    Belum ada draft jurnal yang dibuat.
                </div>
            `;

            return;
        }

        journalHistory.innerHTML = data.jobs
            .map((job) => {
                return `
                    <div class="history-item">
                        <div>
                            <h3>
                                ${escapeHtml(job.title)}
                            </h3>

                            <p>
                                Sumber:
                                ${escapeHtml(
                                    job.original_name
                                )}
                                ·
                                ${new Date(
                                    job.created_at
                                ).toLocaleString("id-ID")}
                            </p>

                            <div class="history-status">
                                <span>
                                    ${escapeHtml(
                                        job.reduction_mode
                                    )}
                                </span>

                                <span>
                                    ${escapeHtml(
                                        job.output_total_words
                                    )} kata
                                </span>

                                <span>
                                    ${escapeHtml(
                                        job.warnings_total
                                    )} peringatan
                                </span>
                            </div>
                        </div>

                        <div class="history-actions">
                            <a
                                class="small-button"
                                href="${job.download_url}"
                            >
                                Dokumen
                            </a>

                            <a
                                class="small-button secondary"
                                href="${job.report_url}"
                            >
                                Laporan
                            </a>

                            <button
                                class="danger-button"
                                type="button"
                                data-delete-job="${job.job_id}"
                            >
                                Hapus
                            </button>
                        </div>
                    </div>
                `;
            })
            .join("");

        document
            .querySelectorAll("[data-delete-job]")
            .forEach((button) => {
                button.addEventListener(
                    "click",
                    async () => {
                        const confirmed = window.confirm(
                            "Hapus riwayat dan draft jurnal ini?"
                        );

                        if (!confirmed) {
                            return;
                        }

                        const response = await fetch(
                            `/api/journal/jobs/${
                                button.dataset.deleteJob
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
                                "Riwayat gagal dihapus."
                            );

                            return;
                        }

                        await loadHistory();

                        showToast(
                            "Riwayat jurnal berhasil dihapus."
                        );
                    }
                );
            });

    } catch (error) {
        journalHistory.innerHTML = `
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
        loadHistory
    );


loadTemplates();