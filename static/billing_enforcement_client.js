(function () {
    if (
        window.__docurapiBillingEnforcement
    ) {
        return;
    }

    window.__docurapiBillingEnforcement = true;

    const originalFetch = (
        window.fetch.bind(window)
    );

    let paymentModalVisible = false;


    function createPaymentModal(payload) {
        if (paymentModalVisible) {
            return;
        }

        paymentModalVisible = true;

        const overlay = document.createElement(
            "div"
        );

        overlay.id = (
            "docurapi-payment-required-overlay"
        );

        overlay.style.position = "fixed";
        overlay.style.inset = "0";
        overlay.style.zIndex = "999999";
        overlay.style.display = "grid";
        overlay.style.placeItems = "center";
        overlay.style.padding = "20px";
        overlay.style.background = (
            "rgba(10, 22, 24, 0.72)"
        );

        const card = document.createElement(
            "div"
        );

        card.style.width = (
            "min(460px, 100%)"
        );

        card.style.padding = "28px";
        card.style.borderRadius = "18px";
        card.style.background = "#ffffff";
        card.style.boxShadow = (
            "0 20px 55px rgba(0,0,0,0.25)"
        );

        const title = document.createElement(
            "h2"
        );

        title.textContent = (
            "Pembayaran Diperlukan"
        );

        title.style.marginTop = "0";

        const description = (
            document.createElement("p")
        );

        description.textContent = (
            payload.message
            || (
                "Silakan membeli layanan "
                + "sebelum memproses dokumen."
            )
        );

        description.style.color = "#68787c";
        description.style.lineHeight = "1.6";

        const service = document.createElement(
            "p"
        );

        service.textContent = (
            "Layanan: "
            + (
                payload.service_code
                || "-"
            )
        );

        service.style.fontWeight = "700";

        const actions = document.createElement(
            "div"
        );

        actions.style.display = "flex";
        actions.style.flexWrap = "wrap";
        actions.style.gap = "9px";
        actions.style.marginTop = "20px";

        const checkoutLink = (
            document.createElement("a")
        );

        checkoutLink.href = (
            payload.checkout_url
            || "/billing"
        );

        checkoutLink.textContent = (
            "Buka Billing"
        );

        checkoutLink.style.padding = (
            "11px 15px"
        );

        checkoutLink.style.borderRadius = (
            "9px"
        );

        checkoutLink.style.background = (
            "#0f6b5d"
        );

        checkoutLink.style.color = "#ffffff";
        checkoutLink.style.textDecoration = "none";
        checkoutLink.style.fontWeight = "800";

        const closeButton = (
            document.createElement("button")
        );

        closeButton.type = "button";
        closeButton.textContent = "Tutup";
        closeButton.style.padding = "11px 15px";
        closeButton.style.border = "0";
        closeButton.style.borderRadius = "9px";
        closeButton.style.background = "#e5f3ef";
        closeButton.style.color = "#084d43";
        closeButton.style.fontWeight = "800";
        closeButton.style.cursor = "pointer";

        closeButton.addEventListener(
            "click",
            function () {
                overlay.remove();
                paymentModalVisible = false;
            }
        );

        actions.appendChild(
            checkoutLink
        );

        actions.appendChild(
            closeButton
        );

        card.appendChild(title);
        card.appendChild(description);
        card.appendChild(service);
        card.appendChild(actions);

        overlay.appendChild(card);

        document.body.appendChild(
            overlay
        );
    }


    window.fetch = async function (
        ...argumentsList
    ) {
        const response = await originalFetch(
            ...argumentsList
        );

        if (response.status === 402) {
            try {
                const payload = await response
                    .clone()
                    .json();

                createPaymentModal(
                    payload.detail
                    && typeof payload.detail
                    === "object"
                        ? payload.detail
                        : payload
                );
            }
            catch {
                createPaymentModal(
                    {
                        message: (
                            "Hak pemrosesan tidak "
                            + "tersedia."
                        ),
                        checkout_url: "/billing",
                    }
                );
            }
        }

        return response;
    };
})();
