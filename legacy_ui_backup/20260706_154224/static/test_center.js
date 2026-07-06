const toast = document.getElementById(
    "toast"
);

const loadingOverlay = document.getElementById(
    "loading-overlay"
);

const statusFilter = document.getElementById(
    "status-filter"
);

const searchInput = document.getElementById(
    "search-input"
);

let report = null;


function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function formatBytes(value) {
    let number = Number(value || 0);

    const units = [
        "B",
        "KB",
        "MB",
        "GB",
    ];

    let unit = 0;

    while (
        number >= 1024
        && unit < units.length - 1
    ) {
        number /= 1024;
        unit += 1;
    }

    return (
        `${number.toFixed(unit ? 1 : 0)} `
        + units[unit]
    );
}


function showToast(message) {
    toast.textContent = message;
    toast.classList.remove("hidden");

    setTimeout(() => {
        toast.classList.add("hidden");
    }, 4000);
}


function showLoading(visible) {
    loadingOverlay.classList.toggle(
        "hidden",
        !visible
    );
}


async function ensureAdmin() {
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
            <section class="card">
                <h1>Akses administrator diperlukan</h1>

                <p>
                    Test Center hanya dapat dijalankan oleh
                    administrator sistem.
                </p>
            </section>
        `;

        return false;
    }

    return true;
}


function renderSummary() {
    const summary = report.summary;

    document.getElementById(
        "summary-status"
    ).textContent = summary.readiness;

    document.getElementById(
        "summary-status"
    ).className = (
        "readiness "
        + summary.readiness
            .toLowerCase()
            .replaceAll(" ", "-")
    );

    document.getElementById(
        "summary-score"
    ).textContent = (
        `${summary.score}/100`
    );

    document.getElementById(
        "summary-pass"
    ).textContent = summary.pass;

    document.getElementById(
        "summary-fail"
    ).textContent = summary.fail;

    document.getElementById(
        "summary-warning"
    ).textContent = summary.warning;

    document.getElementById(
        "report-time"
    ).textContent = (
        "Laporan dibuat: "
        + new Date(
            report.generated_at
        ).toLocaleString("id-ID")
        + ` ? Mode ${report.mode}`
    );
}


function renderResults() {
    const container = document.getElementById(
        "result-table"
    );

    if (!report) {
        return;
    }

    const selectedStatus = statusFilter.value;

    const searchTerm = (
        searchInput.value
        .trim()
        .toLowerCase()
    );

    const results = report.results.filter(
        (item) => {
            const statusMatches = (
                !selectedStatus
                || item.status === selectedStatus
            );

            const searchText = (
                item.category
                + " "
                + item.name
                + " "
                + item.detail
            ).toLowerCase();

            const searchMatches = (
                !searchTerm
                || searchText.includes(
                    searchTerm
                )
            );

            return (
                statusMatches
                && searchMatches
            );
        }
    );

    if (!results.length) {
        container.innerHTML = `
            <div class="empty-state">
                Tidak ada hasil pada filter ini.
            </div>
        `;

        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Kategori</th>
                    <th>Pemeriksaan</th>
                    <th>Status</th>
                    <th>Keterangan</th>
                </tr>
            </thead>

            <tbody>
                ${results.map((item) => {
                    const evidence = (
                        item.evidence !== null
                        && item.evidence !== undefined
                    )
                        ? `
                            <details>
                                <summary>
                                    Lihat evidence
                                </summary>

                                <pre>${escapeHtml(
                                    JSON.stringify(
                                        item.evidence,
                                        null,
                                        2
                                    )
                                )}</pre>
                            </details>
                        `
                        : "";

                    return `
                        <tr>
                            <td>
                                ${escapeHtml(
                                    item.category
                                )}
                            </td>

                            <td>
                                <strong>
                                    ${escapeHtml(
                                        item.name
                                    )}
                                </strong>
                            </td>

                            <td>
                                <span class="status ${
                                    item.status.toLowerCase()
                                }">
                                    ${escapeHtml(
                                        item.status
                                    )}
                                </span>
                            </td>

                            <td>
                                ${escapeHtml(
                                    item.detail
                                )}

                                ${evidence}
                            </td>
                        </tr>
                    `;
                }).join("")}
            </tbody>
        </table>
    `;
}


async function loadLatestReport() {
    const response = await fetch(
        "/api/tests/latest"
    );

    if (response.status === 404) {
        return;
    }

    const data = await response.json();

    if (!response.ok) {
        showToast(
            data.detail
            || "Laporan gagal dimuat."
        );

        return;
    }

    report = data;

    renderSummary();
    renderResults();
}


async function loadFixtures() {
    const response = await fetch(
        "/api/tests/fixtures"
    );

    const data = await response.json();

    const container = document.getElementById(
        "fixture-list"
    );

    if (!response.ok) {
        container.innerHTML = `
            <div class="error-state">
                ${escapeHtml(
                    data.detail
                    || "Dokumen uji gagal dimuat."
                )}
            </div>
        `;

        return;
    }

    if (!data.fixtures.length) {
        container.innerHTML = `
            <div class="empty-state">
                Belum ada dokumen uji.
            </div>
        `;

        return;
    }

    container.innerHTML = data.fixtures
        .map((fixture) => {
            return `
                <article class="fixture-item">
                    <div>
                        <strong>
                            ${escapeHtml(
                                fixture.name
                            )}
                        </strong>

                        <span>
                            ${formatBytes(
                                fixture.size_bytes
                            )}
                        </span>
                    </div>

                    <a href="${
                        fixture.download_url
                    }">
                        Unduh
                    </a>
                </article>
            `;
        })
        .join("");
}


document
    .getElementById("run-tests")
    .addEventListener(
        "click",
        async () => {
            const mode = document.getElementById(
                "test-mode"
            ).value;

            const confirmed = window.confirm(
                (
                    mode === "full"
                    ? (
                        "Jalankan full acceptance test? "
                        + "Pemeriksaan akan menguji aplikasi, "
                        + "database, autentikasi, dan document engine."
                    )
                    : (
                        "Jalankan structural test?"
                    )
                )
            );

            if (!confirmed) {
                return;
            }

            showLoading(true);

            try {
                const response = await fetch(
                    `/api/tests/run?mode=${encodeURIComponent(
                        mode
                    )}`,
                    {
                        method: "POST",
                        body: new FormData(),
                    }
                );

                const data = await response.json();

                if (!response.ok) {
                    showToast(
                        data.detail
                        || "Acceptance test gagal dijalankan."
                    );

                    return;
                }

                report = data;

                renderSummary();
                renderResults();

                showToast(
                    (
                        "Acceptance test selesai. "
                        + `Status ${data.summary.readiness}, `
                        + `score ${data.summary.score}/100.`
                    )
                );
            }
            finally {
                showLoading(false);
            }
        }
    );


statusFilter.addEventListener(
    "change",
    renderResults
);

searchInput.addEventListener(
    "input",
    renderResults
);


async function initialize() {
    const allowed = await ensureAdmin();

    if (!allowed) {
        return;
    }

    await Promise.all([
        loadLatestReport(),
        loadFixtures(),
    ]);
}


initialize();
