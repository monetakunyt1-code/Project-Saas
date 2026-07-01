const toast = document.getElementById(
    "toast"
);

const loadingOverlay = document.getElementById(
    "loading-overlay"
);

let products = [];


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
    }, 4000);
}


function setLoading(visible) {
    loadingOverlay.classList.toggle(
        "hidden",
        !visible
    );
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


async function ensureLogin() {
    const response = await fetch(
        "/api/auth/me"
    );

    if (!response.ok) {
        window.location.href = "/login";
        return false;
    }

    return true;
}


function productCard(product) {
    const creditButton = (
        product.product_type === "processing"
        && Number(product.credit_cost) > 0
    )
        ? `
            <button
                type="button"
                class="secondary-button"
                data-redeem="${escapeHtml(
                    product.product_code
                )}"
            >
                Gunakan ${product.credit_cost} Kredit
            </button>
        `
        : "";

    const purchaseLabel = (
        product.product_type === "credit_pack"
        ? "Beli Paket Kredit"
        : "Bayar Sekali"
    );

    const productMeta = (
        product.product_type === "credit_pack"
        ? `${product.credit_amount} kredit`
        : (
            `${product.credit_cost} kredit `
            + "bila memakai saldo"
        )
    );

    return `
        <article class="product-card">
            <div>
                <span class="product-type">
                    ${
                        product.product_type
                        === "credit_pack"
                        ? "PAKET KREDIT"
                        : "LAYANAN"
                    }
                </span>

                <h3>
                    ${escapeHtml(product.name)}
                </h3>

                <p>
                    ${escapeHtml(
                        product.description
                    )}
                </p>
            </div>

            <div class="product-footer">
                <div>
                    <strong>
                        ${escapeHtml(
                            product.formatted_price
                        )}
                    </strong>

                    <small>
                        ${escapeHtml(productMeta)}
                    </small>
                </div>

                <div class="product-actions">
                    <button
                        type="button"
                        data-buy="${escapeHtml(
                            product.product_code
                        )}"
                    >
                        ${purchaseLabel}
                    </button>

                    ${creditButton}
                </div>
            </div>
        </article>
    `;
}


function bindProductActions() {
    document
        .querySelectorAll("[data-buy]")
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    await purchaseProduct(
                        button.dataset.buy
                    );
                }
            );
        });

    document
        .querySelectorAll("[data-redeem]")
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    await redeemProduct(
                        button.dataset.redeem
                    );
                }
            );
        });
}


async function loadCatalog() {
    const response = await fetch(
        "/api/billing/catalog"
    );

    const data = await response.json();

    if (!response.ok) {
        showToast(
            data.detail
            || "Katalog gagal dimuat."
        );

        return;
    }

    products = data.products;

    const processingProducts = products.filter(
        (product) => (
            product.product_type
            === "processing"
        )
    );

    const creditProducts = products.filter(
        (product) => (
            product.product_type
            === "credit_pack"
        )
    );

    document.getElementById(
        "processing-products"
    ).innerHTML = processingProducts
        .map(productCard)
        .join("");

    document.getElementById(
        "credit-products"
    ).innerHTML = creditProducts
        .map(productCard)
        .join("");

    bindProductActions();
}


async function purchaseProduct(productCode) {
    const product = products.find(
        (item) => (
            item.product_code
            === productCode
        )
    );

    if (!product) {
        return;
    }

    const confirmed = window.confirm(
        (
            `Beli ${product.name} seharga `
            + `${product.formatted_price}?`
        )
    );

    if (!confirmed) {
        return;
    }

    setLoading(true);

    try {
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

        const orderResponse = await fetch(
            "/api/billing/orders",
            {
                method: "POST",
                body: formData,
            }
        );

        const orderData = await orderResponse.json();

        if (!orderResponse.ok) {
            showToast(
                orderData.detail
                || "Pesanan gagal dibuat."
            );

            return;
        }

        const orderId = (
            orderData.order.order_id
        );

        const paymentResponse = await fetch(
            (
                `/api/billing/orders/`
                + `${orderId}/simulate-pay`
            ),
            {
                method: "POST",
                body: new FormData(),
            }
        );

        const paymentData = (
            await paymentResponse.json()
        );

        if (!paymentResponse.ok) {
            showToast(
                paymentData.detail
                || "Pembayaran simulasi gagal."
            );

            return;
        }

        showToast(
            "Pembayaran berhasil. Hak penggunaan telah diberikan."
        );

        await refreshAll();
    }
    finally {
        setLoading(false);
    }
}


async function redeemProduct(productCode) {
    const product = products.find(
        (item) => (
            item.product_code
            === productCode
        )
    );

    if (!product) {
        return;
    }

    const confirmed = window.confirm(
        (
            `Gunakan ${product.credit_cost} kredit `
            + `untuk ${product.name}?`
        )
    );

    if (!confirmed) {
        return;
    }

    setLoading(true);

    try {
        const formData = new FormData();

        formData.append(
            "product_code",
            productCode
        );

        formData.append(
            "quantity",
            "1"
        );

        const response = await fetch(
            "/api/billing/credits/redeem",
            {
                method: "POST",
                body: formData,
            }
        );

        const data = await response.json();

        if (!response.ok) {
            showToast(
                data.detail
                || "Penukaran kredit gagal."
            );

            return;
        }

        showToast(
            "Kredit berhasil ditukar menjadi hak pemrosesan."
        );

        await refreshAll();
    }
    finally {
        setLoading(false);
    }
}


async function loadWallet() {
    const response = await fetch(
        "/api/billing/wallet"
    );

    if (!response.ok) {
        return;
    }

    const data = await response.json();

    document.getElementById(
        "credit-balance"
    ).textContent = data.credit_balance;
}


async function loadEntitlements() {
    const response = await fetch(
        "/api/billing/entitlements"
    );

    const data = await response.json();

    const container = document.getElementById(
        "entitlement-list"
    );

    if (!response.ok) {
        container.innerHTML = `
            <div class="error-state">
                ${escapeHtml(
                    data.detail
                    || "Hak pemrosesan gagal dimuat."
                )}
            </div>
        `;

        return;
    }

    if (!data.entitlements.length) {
        container.innerHTML = `
            <div class="empty-state">
                Belum ada hak pemrosesan.
            </div>
        `;

        return;
    }

    container.innerHTML = data.entitlements
        .slice(0, 20)
        .map((item) => {
            return `
                <article class="compact-item">
                    <div>
                        <strong>
                            ${escapeHtml(
                                item.service_code
                            )}
                        </strong>

                        <span>
                            Sumber:
                            ${escapeHtml(
                                item.source_type
                            )}
                        </span>
                    </div>

                    <span class="status ${
                        escapeHtml(item.status)
                    }">
                        ${escapeHtml(
                            item.status.toUpperCase()
                        )}
                    </span>
                </article>
            `;
        })
        .join("");
}


async function loadOrders() {
    const response = await fetch(
        "/api/billing/orders?limit=50"
    );

    const data = await response.json();

    const container = document.getElementById(
        "order-list"
    );

    if (!response.ok) {
        container.innerHTML = `
            <div class="error-state">
                ${escapeHtml(
                    data.detail
                    || "Transaksi gagal dimuat."
                )}
            </div>
        `;

        return;
    }

    if (!data.orders.length) {
        container.innerHTML = `
            <div class="empty-state">
                Belum ada transaksi.
            </div>
        `;

        return;
    }

    container.innerHTML = data.orders
        .map((order) => {
            return `
                <article class="compact-item">
                    <div>
                        <strong>
                            ${escapeHtml(
                                order.order_number
                            )}
                        </strong>

                        <span>
                            ${escapeHtml(
                                order.formatted_total
                            )}
                        </span>
                    </div>

                    <div class="compact-actions">
                        <span class="status ${
                            escapeHtml(order.status)
                        }">
                            ${escapeHtml(
                                order.status.toUpperCase()
                            )}
                        </span>

                        <a
                            href="/api/billing/orders/${
                                order.order_id
                            }/invoice"
                            target="_blank"
                        >
                            Invoice
                        </a>
                    </div>
                </article>
            `;
        })
        .join("");
}


async function refreshAll() {
    await Promise.all([
        loadWallet(),
        loadEntitlements(),
        loadOrders(),
    ]);
}


async function initialize() {
    const loggedIn = await ensureLogin();

    if (!loggedIn) {
        return;
    }

    await loadCatalog();
    await refreshAll();
}


initialize();
