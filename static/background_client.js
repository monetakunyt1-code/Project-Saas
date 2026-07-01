(function () {
    "use strict";

    const previousFetch = window.fetch.bind(
        window
    );

    const backgroundRoutes = {
        "/api/process": "process",
        "/api/batch/process": "batch",
        "/api/audit/document": "audit",
        "/api/journal/build": "journal",
    };

    const activeCards = new Map();


    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }


    function ensureContainer() {
        let container = document.getElementById(
            "docurapi-background-panel"
        );

        if (container) {
            return container;
        }

        container = document.createElement(
            "div"
        );

        container.id =
            "docurapi-background-panel";

        container.innerHTML = `
            <div class="dr-background-header">
                <strong>
                    Pemrosesan DocuRapi
                </strong>

                <a href="/task-center">
                    Task Center
                </a>
            </div>

            <div
                id="docurapi-background-list"
                class="dr-background-list"
            ></div>
        `;

        document.body.appendChild(
            container
        );

        return container;
    }


    function injectStyles() {
        if (
            document.getElementById(
                "docurapi-background-style"
            )
        ) {
            return;
        }

        const style = document.createElement(
            "style"
        );

        style.id =
            "docurapi-background-style";

        style.textContent = `
            #docurapi-background-panel {
                position: fixed;
                right: 20px;
                bottom: 20px;
                z-index: 99999;
                width: min(390px, calc(100vw - 32px));
                overflow: hidden;
                border: 1px solid #dce7e4;
                border-radius: 16px;
                background: #ffffff;
                color: #172326;
                font-family: "Segoe UI", Arial, sans-serif;
                box-shadow:
                    0 22px 54px rgba(20, 74, 64, 0.18);
            }

            #docurapi-background-panel:has(
                .dr-background-list:empty
            ) {
                display: none;
            }

            .dr-background-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                padding: 13px 15px;
                background: #0f6b5d;
                color: #ffffff;
            }

            .dr-background-header a {
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
            }

            .dr-background-list {
                display: grid;
                gap: 1px;
                max-height: 420px;
                overflow-y: auto;
                background: #dce7e4;
            }

            .dr-background-card {
                padding: 15px;
                background: #ffffff;
            }

            .dr-background-title {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 8px;
            }

            .dr-background-title strong {
                text-transform: capitalize;
            }

            .dr-background-percent {
                color: #0f6b5d;
                font-weight: 900;
            }

            .dr-background-message {
                margin: 0 0 10px;
                color: #68787c;
                font-size: 13px;
                line-height: 1.45;
            }

            .dr-background-track {
                height: 8px;
                overflow: hidden;
                border-radius: 999px;
                background: #e5efec;
            }

            .dr-background-bar {
                height: 100%;
                width: 0;
                border-radius: inherit;
                background: #0f6b5d;
                transition: width 0.35s ease;
            }

            .dr-background-actions {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                margin-top: 10px;
            }

            .dr-background-status {
                padding: 4px 8px;
                border-radius: 999px;
                background: #e5f3ef;
                color: #084d43;
                font-size: 11px;
                font-weight: 800;
            }

            .dr-background-status.failed,
            .dr-background-status.canceled {
                background: #fff0f0;
                color: #b63b3b;
            }

            .dr-background-cancel {
                padding: 6px 9px;
                border: 0;
                border-radius: 8px;
                background: #fff0f0;
                color: #b63b3b;
                cursor: pointer;
                font-size: 12px;
                font-weight: 800;
            }
        `;

        document.head.appendChild(
            style
        );
    }


    function operationLabel(operation) {
        const labels = {
            process: "Format Dokumen",
            batch: "Batch Processing",
            audit: "Audit Akademik",
            journal: "Journal Studio",
        };

        return (
            labels[operation]
            || operation
        );
    }


    function createProgressCard(
        jobId,
        operation
    ) {
        injectStyles();

        const container = ensureContainer();

        const list = container.querySelector(
            "#docurapi-background-list"
        );

        const card = document.createElement(
            "article"
        );

        card.className =
            "dr-background-card";

        card.dataset.jobId = jobId;

        card.innerHTML = `
            <div class="dr-background-title">
                <strong>
                    ${escapeHtml(
                        operationLabel(operation)
                    )}
                </strong>

                <span
                    class="dr-background-percent"
                >
                    0%
                </span>
            </div>

            <p class="dr-background-message">
                Memasukkan pekerjaan ke antrean...
            </p>

            <div class="dr-background-track">
                <div
                    class="dr-background-bar"
                ></div>
            </div>

            <div class="dr-background-actions">
                <span
                    class="dr-background-status"
                >
                    queued
                </span>

                <button
                    class="dr-background-cancel"
                    type="button"
                >
                    Batalkan
                </button>
            </div>
        `;

        list.prepend(card);

        const cancelButton = card.querySelector(
            ".dr-background-cancel"
        );

        cancelButton.addEventListener(
            "click",
            async () => {
                cancelButton.disabled = true;
                cancelButton.textContent =
                    "Membatalkan...";

                const formData = new FormData();

                try {
                    await previousFetch(
                        `/api/background/jobs/${jobId}/cancel`,
                        {
                            method: "POST",
                            body: formData,
                        }
                    );
                }
                catch {
                    cancelButton.disabled = false;
                    cancelButton.textContent =
                        "Batalkan";
                }
            }
        );

        activeCards.set(
            jobId,
            card
        );

        return card;
    }


    function updateProgressCard(
        job
    ) {
        const card = activeCards.get(
            job.job_id
        );

        if (!card) {
            return;
        }

        card.querySelector(
            ".dr-background-percent"
        ).textContent = (
            `${Number(job.progress || 0)}%`
        );

        card.querySelector(
            ".dr-background-message"
        ).textContent = (
            job.message
            || "Sedang memproses..."
        );

        card.querySelector(
            ".dr-background-bar"
        ).style.width = (
            `${Number(job.progress || 0)}%`
        );

        const status = card.querySelector(
            ".dr-background-status"
        );

        status.textContent = job.status;
        status.className = (
            "dr-background-status "
            + job.status
        );

        const cancelButton = card.querySelector(
            ".dr-background-cancel"
        );

        if (
            [
                "completed",
                "failed",
                "canceled",
            ].includes(job.status)
        ) {
            cancelButton.remove();

            setTimeout(() => {
                card.remove();

                activeCards.delete(
                    job.job_id
                );
            }, 8000);
        }
    }


    async function pollJob(jobId) {
        while (true) {
            const response = await previousFetch(
                `/api/background/jobs/${jobId}`
            );

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.detail
                    || "Status pekerjaan gagal dimuat."
                );
            }

            updateProgressCard(
                data.job
            );

            if (
                [
                    "completed",
                    "failed",
                    "canceled",
                ].includes(
                    data.job.status
                )
            ) {
                return data.job;
            }

            await new Promise(
                (resolve) => {
                    setTimeout(resolve, 900);
                }
            );
        }
    }


    function waitForJob(jobId) {
        return new Promise(
            (resolve, reject) => {
                let completed = false;

                const source = new EventSource(
                    `/api/background/jobs/${jobId}/events`
                );

                source.onmessage = (event) => {
                    try {
                        const payload = JSON.parse(
                            event.data
                        );

                        const job = payload.job;

                        updateProgressCard(job);

                        if (
                            [
                                "completed",
                                "failed",
                                "canceled",
                            ].includes(job.status)
                        ) {
                            completed = true;
                            source.close();
                            resolve(job);
                        }
                    }
                    catch (error) {
                        source.close();
                        reject(error);
                    }
                };

                source.onerror = async () => {
                    source.close();

                    if (completed) {
                        return;
                    }

                    try {
                        resolve(
                            await pollJob(jobId)
                        );
                    }
                    catch (error) {
                        reject(error);
                    }
                };
            }
        );
    }


    function responseFromJob(job) {
        if (
            job.status === "canceled"
        ) {
            return new Response(
                JSON.stringify(
                    {
                        detail: (
                            "Pekerjaan dibatalkan."
                        )
                    }
                ),
                {
                    status: 499,
                    headers: {
                        "content-type":
                            "application/json",
                    },
                }
            );
        }

        const result = job.result;

        if (!result) {
            return new Response(
                JSON.stringify(
                    {
                        detail: (
                            job.error_message
                            || "Pekerjaan gagal."
                        )
                    }
                ),
                {
                    status: 500,
                    headers: {
                        "content-type":
                            "application/json",
                    },
                }
            );
        }

        const statusCode = Number(
            result.status_code
            || (
                job.status === "completed"
                    ? 200
                    : 500
            )
        );

        const contentType = (
            result.content_type
            || "application/json"
        );

        if (
            result.body_type
            === "json"
        ) {
            return new Response(
                JSON.stringify(
                    result.body
                ),
                {
                    status: statusCode,
                    headers: {
                        "content-type":
                            "application/json",
                    },
                }
            );
        }

        if (
            result.body_type
            === "text"
        ) {
            return new Response(
                String(
                    result.body
                    || ""
                ),
                {
                    status: statusCode,
                    headers: {
                        "content-type":
                            contentType,
                    },
                }
            );
        }

        return new Response(
            JSON.stringify(
                result.body
                || {
                    detail: (
                        "Hasil tersedia sebagai file."
                    )
                }
            ),
            {
                status: statusCode,
                headers: {
                    "content-type":
                        "application/json",
                },
            }
        );
    }


    window.fetch = async function (
        input,
        init = {}
    ) {
        const url = new URL(
            input instanceof Request
                ? input.url
                : input,
            window.location.href
        );

        const method = String(
            init.method
            || (
                input instanceof Request
                    ? input.method
                    : "GET"
            )
        ).toUpperCase();

        const operation = (
            method === "POST"
            ? backgroundRoutes[
                url.pathname
            ]
            : null
        );

        if (!operation) {
            return previousFetch(
                input,
                init
            );
        }

        const submitResponse = await previousFetch(
            `/api/background/submit/${operation}`,
            {
                ...init,
                method: "POST",
            }
        );

        let submitData;

        try {
            submitData = await submitResponse
                .clone()
                .json();
        }
        catch {
            return submitResponse;
        }

        if (!submitResponse.ok) {
            return submitResponse;
        }

        const jobId = submitData.job_id;

        createProgressCard(
            jobId,
            operation
        );

        try {
            const job = await waitForJob(
                jobId
            );

            return responseFromJob(job);
        }
        catch (error) {
            return new Response(
                JSON.stringify(
                    {
                        detail: (
                            error.message
                            || "Pekerjaan latar belakang gagal."
                        )
                    }
                ),
                {
                    status: 500,
                    headers: {
                        "content-type":
                            "application/json",
                    },
                }
            );
        }
    };


    window.DocuRapiBackground = {
        waitForJob,
        pollJob,
    };
})();