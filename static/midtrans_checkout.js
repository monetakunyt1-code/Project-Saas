
(function () {
    "use strict";

    if (
        window.__docurapiMidtransCheckoutInstalled
    ) {
        return;
    }

    window.__docurapiMidtransCheckoutInstalled = true;

    let configPromise = null;
    let busy = false;


    function toast(message) {
        if (
            typeof window.showToast === "function"
        ) {
            window.showToast(message);
            return;
        }

        const element = document.getElementById(
            "toast"
        );

        if (element) {
            element.textContent = message;
            element.classList.remove(
                "hidden"
            );

            window.setTimeout(
                function () {
                    element.classList.add(
                        "hidden"
                    );
                },
                4000
            );

            return;
        }

        window.alert(message);
    }


    function loading(visible) {
        const overlay = document.getElementById(
            "loading-overlay"
        );

        if (overlay) {
            overlay.classList.toggle(
                "hidden",
                !visible
            );
        }
    }


    function idempotencyKey() {
        if (
            window.crypto
            && window.crypto.randomUUID
        ) {
            return window.crypto.randomUUID();
        }

        return (
            Date.now().toString()
            + "-"
            + Math.random()
                .toString(16)
                .slice(2)
        );
    }


    async function getConfig() {
        if (!configPromise) {
            configPromise = fetch(
                "/api/payments/midtrans/config"
            ).then(
                async function (response) {
                    const payload = (
                        await response.json()
                    );

                    if (!response.ok) {
                        throw new Error(
                            payload.detail
                            || (
                                "Konfigurasi Midtrans "
                                + "gagal dimuat."
                            )
                        );
                    }

                    return payload;
                }
            );
        }

        return configPromise;
    }


    function gatewayEnabled(config) {
        return (
            config.configured
            && [
                "gateway",
                "midtrans",
                "sandbox",
                "production",
            ].includes(
                String(
                    config.payment_mode
                    || ""
                ).toLowerCase()
            )
        );
    }


    function loadSnap(config) {
        if (
            window.snap
            && typeof window.snap.pay
            === "function"
        ) {
            return Promise.resolve();
        }

        return new Promise(
            function (resolve, reject) {
                const existing = (
                    document.getElementById(
                        "docurapi-midtrans-snap-js"
                    )
                );

                if (existing) {
                    existing.addEventListener(
                        "load",
                        resolve,
                        {
                            once: true
                        }
                    );

                    existing.addEventListener(
                        "error",
                        function () {
                            reject(
                                new Error(
                                    "Snap.js gagal dimuat."
                                )
                            );
                        },
                        {
                            once: true
                        }
                    );

                    return;
                }

                const script = (
                    document.createElement(
                        "script"
                    )
                );

                script.id = (
                    "docurapi-midtrans-snap-js"
                );

                script.src = config.snap_js_url;

                script.setAttribute(
                    "data-client-key",
                    config.client_key
                );

                script.async = true;
                script.onload = resolve;

                script.onerror = function () {
                    reject(
                        new Error(
                            "Snap.js gagal dimuat."
                        )
                    );
                };

                document.head.appendChild(
                    script
                );
            }
        );
    }


    async function createOrder(
        productCode
    ) {
        const formData = new FormData();

        formData.append(
            "product_code",
            productCode
        );

        formData.append(
            "quantity",
            "1"
        );

        formData.append(
            "idempotency_key",
            idempotencyKey()
        );

        const response = await fetch(
            "/api/billing/orders",
            {
                method: "POST",
                body: formData,
            }
        );

        const payload = (
            await response.json()
        );

        if (!response.ok) {
            throw new Error(
                payload.detail
                || "Pesanan gagal dibuat."
            );
        }

        return payload.order;
    }


    async function createCheckout(
        orderId
    ) {
        const response = await fetch(
            (
                "/api/payments/midtrans/checkout/"
                + encodeURIComponent(
                    orderId
                )
            ),
            {
                method: "POST",
                body: new FormData(),
            }
        );

        const payload = (
            await response.json()
        );

        if (!response.ok) {
            throw new Error(
                payload.detail
                || (
                    "Checkout Midtrans "
                    + "gagal dibuat."
                )
            );
        }

        return payload;
    }


    async function syncOrder(
        orderId
    ) {
        const response = await fetch(
            (
                "/api/payments/midtrans/sync/"
                + encodeURIComponent(
                    orderId
                )
            ),
            {
                method: "POST",
                body: new FormData(),
            }
        );

        const payload = (
            await response.json()
        );

        if (!response.ok) {
            throw new Error(
                payload.detail
                || (
                    "Status pembayaran "
                    + "gagal diverifikasi."
                )
            );
        }

        return payload;
    }


    async function launchPayment(
        productCode
    ) {
        if (busy) {
            return;
        }

        busy = true;
        loading(true);

        try {
            const config = await getConfig();

            await loadSnap(
                config
            );

            const order = await createOrder(
                productCode
            );

            const checkout = (
                await createCheckout(
                    order.order_id
                )
            );

            loading(false);

            window.snap.pay(
                checkout.snap_token,
                {
                    onSuccess: async function () {
                        loading(true);

                        try {
                            const result = (
                                await syncOrder(
                                    order.order_id
                                )
                            );

                            toast(
                                result.state === "paid"
                                    ? (
                                        "Pembayaran berhasil "
                                        + "dan hak pemrosesan "
                                        + "sudah diberikan."
                                    )
                                    : (
                                        "Status pembayaran: "
                                        + result.state
                                    )
                            );

                            window.setTimeout(
                                function () {
                                    window.location.reload();
                                },
                                1200
                            );
                        }
                        catch (error) {
                            toast(
                                error.message
                            );
                        }
                        finally {
                            loading(false);
                        }
                    },

                    onPending: async function () {
                        try {
                            const result = (
                                await syncOrder(
                                    order.order_id
                                )
                            );

                            toast(
                                (
                                    "Pembayaran masih "
                                    + result.state
                                    + "."
                                )
                            );
                        }
                        catch (error) {
                            toast(
                                error.message
                            );
                        }
                    },

                    onError: function () {
                        toast(
                            (
                                "Pembayaran gagal. "
                                + "Pesanan tidak dikonsumsi."
                            )
                        );
                    },

                    onClose: function () {
                        toast(
                            (
                                "Jendela pembayaran ditutup. "
                                + "Pesanan tetap pending."
                            )
                        );
                    },
                }
            );
        }
        catch (error) {
            toast(
                error.message
                || "Checkout Midtrans gagal."
            );
        }
        finally {
            loading(false);
            busy = false;
        }
    }


    async function handleClick(event) {
        const button = event.target.closest(
            "[data-buy]"
        );

        if (!button) {
            return;
        }

        let config;

        try {
            config = await getConfig();
        }
        catch {
            return;
        }

        if (!gatewayEnabled(config)) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        const productCode = (
            button.dataset.buy
        );

        if (productCode) {
            await launchPayment(
                productCode
            );
        }
    }


    document.addEventListener(
        "click",
        handleClick,
        true
    );
})();
