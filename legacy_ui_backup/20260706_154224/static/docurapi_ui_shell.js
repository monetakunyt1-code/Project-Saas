
(function () {
    "use strict";

    if (window.__docurapiUiShellInstalled) {
        return;
    }

    window.__docurapiUiShellInstalled = true;

    const knownLabels = [
        "notifikasi",
        "notification",
        "test center",
        "acceptance",
        "system health",
        "task center",
        "workspace",
        "security center",
        "billing",
        "bayar per proses",
        "infrastructure",
        "journal studio",
        "audit center"
    ];

    const knownPathFragments = [
        "/notifications",
        "/notification",
        "/acceptance",
        "/test-center",
        "/system-health",
        "/task-center",
        "/tasks",
        "/workspace",
        "/security",
        "/billing",
        "/infrastructure",
        "/journal-studio",
        "/academic-audit"
    ];

    let scanScheduled = false;


    function normalizeText(value) {
        return String(value || "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();
    }


    function createShell() {
        if (
            document.getElementById(
                "docurapi-tools-panel"
            )
        ) {
            return;
        }

        const overlay = document.createElement(
            "div"
        );

        overlay.id = "docurapi-tools-overlay";

        const panel = document.createElement(
            "aside"
        );

        panel.id = "docurapi-tools-panel";

        panel.setAttribute(
            "aria-hidden",
            "true"
        );

        panel.innerHTML = `
            <div class="docurapi-tools-header">
                <div class="docurapi-tools-title">
                    <strong>Menu DocuRapi</strong>
                    <span>Pusat fitur dan pengaturan</span>
                </div>

                <button
                    id="docurapi-tools-close"
                    type="button"
                    aria-label="Tutup menu"
                >
                    ×
                </button>
            </div>

            <div id="docurapi-tools-list"></div>

            <div class="docurapi-tools-footer">
                Semua fitur tambahan dikumpulkan di sini.
            </div>
        `;

        const toggle = document.createElement(
            "button"
        );

        toggle.id = "docurapi-tools-toggle";
        toggle.type = "button";

        toggle.setAttribute(
            "aria-expanded",
            "false"
        );

        toggle.innerHTML = `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                    d="M4 6h16v2H4V6zm0 5h16v2H4v-2zm0 5h16v2H4v-2z"
                ></path>
            </svg>

            <span>Menu</span>
        `;

        document.body.appendChild(
            overlay
        );

        document.body.appendChild(
            panel
        );

        document.body.appendChild(
            toggle
        );

        const closeButton = document.getElementById(
            "docurapi-tools-close"
        );

        toggle.addEventListener(
            "click",
            function () {
                const isOpen = panel.classList
                    .contains("is-open");

                setPanelOpen(!isOpen);
            }
        );

        closeButton.addEventListener(
            "click",
            function () {
                setPanelOpen(false);
            }
        );

        overlay.addEventListener(
            "click",
            function () {
                setPanelOpen(false);
            }
        );

        document.addEventListener(
            "keydown",
            function (event) {
                if (event.key === "Escape") {
                    setPanelOpen(false);
                }
            }
        );
    }


    function setPanelOpen(open) {
        const panel = document.getElementById(
            "docurapi-tools-panel"
        );

        const overlay = document.getElementById(
            "docurapi-tools-overlay"
        );

        const toggle = document.getElementById(
            "docurapi-tools-toggle"
        );

        if (!panel || !overlay || !toggle) {
            return;
        }

        panel.classList.toggle(
            "is-open",
            open
        );

        overlay.classList.toggle(
            "is-open",
            open
        );

        panel.setAttribute(
            "aria-hidden",
            open ? "false" : "true"
        );

        toggle.setAttribute(
            "aria-expanded",
            open ? "true" : "false"
        );
    }


    function hasFixedPosition(element) {
        const style = window.getComputedStyle(
            element
        );

        return (
            style.position === "fixed"
            || style.position === "sticky"
        );
    }


    function isKnownLauncher(element) {
        if (
            element.id === "docurapi-tools-toggle"
            || element.id === "docurapi-tools-close"
            || element.closest(
                "#docurapi-tools-panel"
            )
        ) {
            return false;
        }

        if (
            element.dataset
            .docurapiOriginalLauncher
            === "true"
        ) {
            return false;
        }

        const text = normalizeText(
            element.textContent
        );

        const href = normalizeText(
            element.getAttribute("href")
        );

        const className = normalizeText(
            typeof element.className === "string"
                ? element.className
                : ""
        );

        const labelMatched = knownLabels.some(
            function (label) {
                return (
                    text === label
                    || text.includes(label)
                    || className.includes(
                        label.replaceAll(" ", "-")
                    )
                );
            }
        );

        const pathMatched = knownPathFragments.some(
            function (fragment) {
                return href.includes(fragment);
            }
        );

        if (!labelMatched && !pathMatched) {
            return false;
        }

        return hasFixedPosition(element);
    }


    function launcherPriority(element) {
        const text = normalizeText(
            element.textContent
        );

        const order = [
            "billing",
            "bayar per proses",
            "task center",
            "notifikasi",
            "workspace",
            "journal studio",
            "test center",
            "system health",
            "security center",
            "infrastructure"
        ];

        const index = order.findIndex(
            function (label) {
                return text.includes(label);
            }
        );

        return index < 0
            ? 999
            : index;
    }


    function moveLaunchers() {
        createShell();

        const list = document.getElementById(
            "docurapi-tools-list"
        );

        if (!list) {
            return;
        }

        const candidates = Array.from(
            document.querySelectorAll(
                "body > a, body > button"
            )
        ).filter(
            isKnownLauncher
        );

        candidates.sort(
            function (first, second) {
                return (
                    launcherPriority(first)
                    - launcherPriority(second)
                );
            }
        );

        candidates.forEach(
            function (element) {
                element.dataset
                    .docurapiOriginalLauncher
                    = "true";

                element.classList.add(
                    "docurapi-docked-item"
                );

                element.removeAttribute("style");

                list.appendChild(element);
            }
        );

        document.body.classList.add(
            "docurapi-shell-ready"
        );
    }


    function scheduleScan() {
        if (scanScheduled) {
            return;
        }

        scanScheduled = true;

        window.requestAnimationFrame(
            function () {
                scanScheduled = false;
                moveLaunchers();
            }
        );
    }


    function start() {
        createShell();
        moveLaunchers();

        const observer = new MutationObserver(
            function () {
                scheduleScan();
            }
        );

        observer.observe(
            document.body,
            {
                childList: true,
                subtree: false
            }
        );

        window.setTimeout(
            moveLaunchers,
            500
        );

        window.setTimeout(
            moveLaunchers,
            1500
        );

        window.setTimeout(
            moveLaunchers,
            3000
        );
    }


    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            start,
            {
                once: true
            }
        );
    }
    else {
        start();
    }
})();
