const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".tab-panel");

const processForm = document.getElementById("process-form");
const processButton = document.getElementById("process-button");
const resultBox = document.getElementById("process-result");

const fileInput = document.getElementById("document-file");
const fileName = document.getElementById("file-name");
const dropZone = document.getElementById("drop-zone");

const templateForm = document.getElementById("template-form");
const templateMessage = document.getElementById("template-message");
const templateList = document.getElementById("template-list");
const templateSelect = document.getElementById("template-select");

const historyList = document.getElementById("history-list");
const toast = document.getElementById("toast");

function showToast(message) {
    toast.textContent = message;
    toast.classList.remove("hidden");

    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3500);
}

tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
        tabs.forEach((item) => {
            item.classList.remove("active");
        });

        panels.forEach((panel) => {
            panel.classList.remove("active");
        });

        tab.classList.add("active");

        document
            .getElementById(`tab-${tab.dataset.tab}`)
            .classList.add("active");

        if (tab.dataset.tab === "history") {
            loadHistory();
        }

        if (tab.dataset.tab === "templates") {
            loadTemplates();
        }
    });
});

document
    .querySelectorAll(".option-card input")
    .forEach((input) => {
        input.addEventListener("change", () => {
            document
                .querySelectorAll(".option-card")
                .forEach((card) => {
                    card.classList.remove("selected");
                });

            input
                .closest(".option-card")
                .classList.add("selected");
        });
    });

fileInput.addEventListener("change", () => {
    fileName.textContent = fileInput.files[0]
        ? fileInput.files[0].name
        : "Belum ada file dipilih";
});

["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.add("dragging");
    });
});

["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.remove("dragging");
    });
});

dropZone.addEventListener("drop", (event) => {
    const files = event.dataTransfer.files;

    if (!files.length) {
        return;
    }

    const transfer = new DataTransfer();
    transfer.items.add(files[0]);
    fileInput.files = transfer.files;
    fileName.textContent = files[0].name;
});

function appendBoolean(formData, formElement, fieldName) {
    const field = formElement.querySelector(
        `[name="${fieldName}"]`
    );

    formData.set(
        fieldName,
        field && field.checked ? "true" : "false"
    );
}

processForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!fileInput.files.length) {
        showToast("Pilih dokumen Word terlebih dahulu.");
        return;
    }

    const formData = new FormData(processForm);

    [
        "include_toc",
        "include_table_list",
        "include_figure_list",
        "include_appendix_list",
        "include_page_numbers",
    ].forEach((fieldName) => {
        appendBoolean(
            formData,
            processForm,
            fieldName
        );
    });

    processButton.disabled = true;
    processButton.textContent = "Sedang memproses...";

    resultBox.className = "result-card hidden";
    resultBox.innerHTML = "";

    try {
        const response = await fetch(
            "/api/process",
            {
                method: "POST",
                body: formData,
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Pemrosesan gagal."
            );
        }

        resultBox.className = "result-card success";

        resultBox.innerHTML = `
            <h3>Dokumen berhasil diproses</h3>

            <p>
                Paragraf:
                <strong>${data.summary.paragraphs_total}</strong>
                &nbsp;·&nbsp;
                Tabel:
                <strong>${data.summary.tables_total}</strong>
                &nbsp;·&nbsp;
                BAB:
                <strong>${data.summary.chapters_total}</strong>
                &nbsp;·&nbsp;
                Temuan:
                <strong>${data.summary.issues_total}</strong>
            </p>

            <div class="result-actions">
                <a
                    class="action-link"
                    href="${data.download_url}"
                >
                    Unduh Dokumen
                </a>

                <a
                    class="action-link secondary"
                    href="${data.report_url}"
                >
                    Unduh Laporan JSON
                </a>
            </div>
        `;

        processForm.reset();
        fileName.textContent = "Belum ada file dipilih";

        document
            .querySelectorAll(".option-card")
            .forEach((card, index) => {
                card.classList.toggle(
                    "selected",
                    index === 0
                );
            });

        loadHistory();
    } catch (error) {
        resultBox.className = "result-card error";
        resultBox.innerHTML = `
            <h3>Pemrosesan gagal</h3>
            <p>${error.message}</p>
        `;
    } finally {
        processButton.disabled = false;
        processButton.textContent = "Proses Dokumen";
    }
});

templateForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const formData = new FormData(templateForm);

    templateMessage.classList.remove("hidden");
    templateMessage.textContent = "Menyimpan template...";

    try {
        const response = await fetch(
            "/api/templates",
            {
                method: "POST",
                body: formData,
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Template gagal disimpan."
            );
        }

        templateMessage.textContent =
            "Template berhasil disimpan.";

        templateForm.reset();
        await loadTemplates();
    } catch (error) {
        templateMessage.textContent = error.message;
    }
});

async function loadTemplates() {
    try {
        const response = await fetch("/api/templates");
        const data = await response.json();

        templateSelect.innerHTML = `
            <option value="">
                Tidak menggunakan template khusus
            </option>
        `;

        if (!data.templates.length) {
            templateList.innerHTML = `
                <div class="empty-state">
                    Belum ada template khusus.
                </div>
            `;
            return;
        }

        templateList.innerHTML = "";

        data.templates.forEach((template) => {
            const option = document.createElement("option");
            option.value = template.template_id;
            option.textContent =
                `${template.template_name}` +
                (
                    template.institution_name
                        ? ` — ${template.institution_name}`
                        : ""
                );

            templateSelect.appendChild(option);

            const item = document.createElement("div");
            item.className = "list-item";

            item.innerHTML = `
                <div>
                    <h4>${template.template_name}</h4>

                    <p>
                        ${template.institution_name || "Tanpa institusi"}
                        · ${template.document_type}
                        · ${template.file_name}
                    </p>
                </div>

                <div class="list-actions">
                    <button
                        class="danger-button"
                        type="button"
                        data-delete-template="${template.template_id}"
                    >
                        Hapus
                    </button>
                </div>
            `;

            templateList.appendChild(item);
        });

        document
            .querySelectorAll("[data-delete-template]")
            .forEach((button) => {
                button.addEventListener("click", async () => {
                    const confirmed = window.confirm(
                        "Hapus template ini?"
                    );

                    if (!confirmed) {
                        return;
                    }

                    await fetch(
                        `/api/templates/${button.dataset.deleteTemplate}`,
                        {
                            method: "DELETE",
                        }
                    );

                    loadTemplates();
                });
            });
    } catch (error) {
        templateList.innerHTML = `
            <div class="empty-state">
                ${error.message}
            </div>
        `;
    }
}

async function loadHistory() {
    try {
        const response = await fetch("/api/jobs?limit=50");
        const data = await response.json();

        if (!data.jobs.length) {
            historyList.innerHTML = `
                <div class="empty-state">
                    Belum ada dokumen yang diproses.
                </div>
            `;
            return;
        }

        historyList.innerHTML = "";

        data.jobs.forEach((job) => {
            const item = document.createElement("div");
            item.className = "list-item";

            const actions = job.status === "completed"
                ? `
                    <a
                        class="secondary-button"
                        href="${job.download_url}"
                    >
                        Dokumen
                    </a>

                    <a
                        class="secondary-button"
                        href="${job.report_url}"
                    >
                        Laporan
                    </a>
                `
                : "";

            item.innerHTML = `
                <div>
                    <h4>${job.original_name}</h4>

                    <p>
                        Mode: ${job.mode}
                        · Preset: ${job.preset}
                        · ${new Date(job.created_at).toLocaleString("id-ID")}
                    </p>

                    <span class="status">
                        ${job.status}
                    </span>

                    ${
                        job.error_message
                            ? `<p>${job.error_message}</p>`
                            : ""
                    }
                </div>

                <div class="list-actions">
                    ${actions}

                    <button
                        class="danger-button"
                        type="button"
                        data-delete-job="${job.job_id}"
                    >
                        Hapus
                    </button>
                </div>
            `;

            historyList.appendChild(item);
        });

        document
            .querySelectorAll("[data-delete-job]")
            .forEach((button) => {
                button.addEventListener("click", async () => {
                    const confirmed = window.confirm(
                        "Hapus riwayat dan file hasil ini?"
                    );

                    if (!confirmed) {
                        return;
                    }

                    await fetch(
                        `/api/jobs/${button.dataset.deleteJob}`,
                        {
                            method: "DELETE",
                        }
                    );

                    loadHistory();
                });
            });
    } catch (error) {
        historyList.innerHTML = `
            <div class="empty-state">
                ${error.message}
            </div>
        `;
    }
}

document
    .getElementById("refresh-templates")
    .addEventListener("click", loadTemplates);

document
    .getElementById("refresh-history")
    .addEventListener("click", loadHistory);

document
    .getElementById("clear-history")
    .addEventListener("click", async () => {
        const confirmed = window.confirm(
            "Hapus seluruh riwayat dan file hasil?"
        );

        if (!confirmed) {
            return;
        }

        await fetch(
            "/api/jobs",
            {
                method: "DELETE",
            }
        );

        loadHistory();
    });

loadTemplates();