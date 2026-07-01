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
    }, 4000);
}


async function ensureAdministrator() {
    const response = await fetch(
        "/api/auth/me"
    );

    if (!response.ok) {
        window.location.href = "/login";
        return false;
    }

    const data = await response.json();

    const role = (
        data.user?.role
        || data.role
        || ""
    );

    if (
        role
        && role !== "admin"
    ) {
        document.querySelector(
            "main"
        ).innerHTML = `
            <section class="section-card">
                <h1>Akses administrator diperlukan</h1>
            </section>
        `;

        return false;
    }

    return true;
}


async function loadProducts() {
    const response = await fetch(
        "/api/billing/admin/catalog"
    );

    const data = await response.json();

    const container = document.getElementById(
        "admin-product-list"
    );

    if (!response.ok) {
        container.innerHTML = `
            <div class="error-state">
                ${escapeHtml(
                    data.detail
                    || "Katalog gagal dimuat."
                )}
            </div>
        `;

        return;
    }

    container.innerHTML = data.products
        .map((product) => {
            return `
                <form
                    class="admin-product-form"
                    data-product="${
                        product.product_code
                    }"
                >
                    <div>
                        <strong>
                            ${escapeHtml(
                                product.product_code
                            )}
                        </strong>

                        <span>
                            ${escapeHtml(
                                product.product_type
                            )}
                        </span>
                    </div>

                    <label>
                        <span>Nama</span>

                        <input
                            name="name"
                            value="${escapeHtml(
                                product.name
                            )}"
                            required
                        >
                    </label>

                    <label>
                        <span>Deskripsi</span>

                        <textarea
                            name="description"
                            required
                        >${escapeHtml(
                            product.description
                        )}</textarea>
                    </label>

                    <label>
                        <span>Harga IDR</span>

                        <input
                            name="price_idr"
                            type="number"
                            min="0"
                            value="${
                                product.price_idr
                            }"
                            required
                        >
                    </label>

                    <label>
                        <span>Biaya kredit</span>

                        <input
                            name="credit_cost"
                            type="number"
                            min="0"
                            value="${
                                product.credit_cost
                            }"
                            required
                        >
                    </label>

                    <label class="checkbox-label">
                        <input
                            name="active"
                            type="checkbox"
                            ${
                                product.active
                                ? "checked"
                                : ""
                            }
                        >

                        Produk aktif
                    </label>

                    <button type="submit">
                        Simpan
                    </button>
                </form>
            `;
        })
        .join("");

    document
        .querySelectorAll(
            ".admin-product-form"
        )
        .forEach((form) => {
            form.addEventListener(
                "submit",
                async (event) => {
                    event.preventDefault();

                    const formData = new FormData(
                        form
                    );

                    formData.set(
                        "active",
                        form.elements.active.checked
                            ? "true"
                            : "false"
                    );

                    const response = await fetch(
                        (
                            "/api/billing/admin/catalog/"
                            + form.dataset.product
                        ),
                        {
                            method: "POST",
                            body: formData,
                        }
                    );

                    const data = (
                        await response.json()
                    );

                    showToast(
                        data.detail
                        || "Produk berhasil diperbarui."
                    );

                    if (response.ok) {
                        await loadProducts();
                    }
                }
            );
        });
}


async function loadOrders() {
    const response = await fetch(
        "/api/billing/admin/orders?limit=200"
    );

    const data = await response.json();

    const container = document.getElementById(
        "admin-order-list"
    );

    if (!response.ok) {
        container.innerHTML = `
            <div class="error-state">
                ${escapeHtml(
                    data.detail
                    || "Pesanan gagal dimuat."
                )}
            </div>
        `;

        return;
    }

    if (!data.orders.length) {
        container.innerHTML = `
            <div class="empty-state">
                Belum ada pesanan.
            </div>
        `;

        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Pesanan</th>
                    <th>Pengguna</th>
                    <th>Total</th>
                    <th>Status</th>
                    <th>Tindakan</th>
                </tr>
            </thead>

            <tbody>
                ${data.orders.map((order) => {
                    const refundButton = (
                        order.status === "paid"
                        ? `
                            <button
                                type="button"
                                class="danger-button"
                                data-refund="${
                                    order.order_id
                                }"
                            >
                                Refund
                            </button>
                        `
                        : "-";

                    return `
                        <tr>
                            <td>
                                ${escapeHtml(
                                    order.order_number
                                )}
                            </td>

                            <td>
                                ${escapeHtml(
                                    order.user_email
                                    || order.user_id
                                )}
                            </td>

                            <td>
                                ${escapeHtml(
                                    order.formatted_total
                                )}
                            </td>

                            <td>
                                <span class="status ${
                                    escapeHtml(
                                        order.status
                                    )
                                }">
                                    ${escapeHtml(
                                        order.status.toUpperCase()
                                    )}
                                </span>
                            </td>

                            <td>
                                ${refundButton}
                            </td>
                        </tr>
                    `;
                }).join("")}
            </tbody>
        </table>
    `;

    document
        .querySelectorAll("[data-refund]")
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const confirmed = (
                        window.confirm(
                            "Refund pesanan ini?"
                        )
                    );

                    if (!confirmed) {
                        return;
                    }

                    const response = await fetch(
                        (
                            "/api/billing/admin/orders/"
                            + button.dataset.refund
                            + "/refund"
                        ),
                        {
                            method: "POST",
                            body: new FormData(),
                        }
                    );

                    const data = (
                        await response.json()
                    );

                    showToast(
                        data.detail
                        || "Refund berhasil."
                    );

                    if (response.ok) {
                        await loadOrders();
                    }
                }
            );
        });
}


async function initialize() {
    const allowed = await ensureAdministrator();

    if (!allowed) {
        return;
    }

    await Promise.all([
        loadProducts(),
        loadOrders(),
    ]);
}


initialize();
