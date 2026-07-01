(function () {
    if (
        document.querySelector(
            ".billing-center-launch"
        )
    ) {
        return;
    }

    const launcher = document.createElement(
        "a"
    );

    launcher.className = (
        "billing-center-launch"
    );

    launcher.href = "/billing";

    launcher.textContent = "Bayar per Proses";

    document.body.appendChild(
        launcher
    );
})();
