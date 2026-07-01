const views = document.querySelectorAll(".view");
const adminLink = document.getElementById("admin-link");
const toast = document.getElementById("toast");

let currentUser = null;
let currentUsage = null;
let plans = [];


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


function formatMoney(value) {
    const number = Number(value || 0);

    if (number === 0) {
        return "Gratis";
    }

    return new Intl.NumberFormat(
        "id-ID",
        {
            style: "currency",
            currency: "IDR",
            maximumFractionDigits: 0,
        }
    ).format(number);
}


function currentView() {
    const path = window.location.pathname;

    if (path === "/register") return "register";
    if (path === "/pricing") return "pricing";
    if (path === "/account") return "account";
    if (path === "/admin") return "admin";

    return "login";
}


function showView(name) {
    views.forEach((view) => {
        view.classList.toggle(
            "active",
            view.id === `${name}-view`
        );
    });
}


async function loadMe() {
    const response = await fetch("/api/auth/me");

    if (!response.ok) {
        currentUser = null;
        currentUsage = null;
        adminLink.classList.add("hidden");
        return;
    }

    const data = await response.json();

    currentUser = data.user;
    currentUsage = data.usage;

    adminLink.classList.toggle(
        "hidden",
        currentUser.role !== "admin"
    );
}


async function loadPlans() {
    const response = await fetch("/api/plans");
    const data = await response.json();

    plans = data.plans || [];
    renderPlans();
}


function renderPlans() {
    const grid = document.getElementById("pricing-grid");

    grid.innerHTML = plans.map((plan) => {
        const active =
            currentUsage?.plan_code === plan.plan_code;

        const features = plan.features.map((item) => {
            return `<li>${escapeHtml(item)}</li>`;
        }).join("");

        return `
            <article class="plan-card ${active ? "active" : ""}">
                <h2>${escapeHtml(plan.name)}</h2>

                <p>
                    ${escapeHtml(plan.monthly_quota)}
                    operasi per bulan
                </p>

                <div class="price">
                    ${formatMoney(plan.price_idr)}
                </div>

                <ul>${features}</ul>

                <button
                    type="button"
                    data-plan="${plan.plan_code}"
                    ${active ? "disabled" : ""}
                >
                    ${active ? "Paket Aktif" : "Pilih Paket"}
                </button>
            </article>
        `;
    }).join("");

    document
        .querySelectorAll("[data-plan]")
        .forEach((button) => {
            button.addEventListener("click", async () => {
                if (!currentUser) {
                    window.location.href = "/login";
                    return;
                }

                const formData = new FormData();

                formData.append(
                    "plan_code",
                    button.dataset.plan
                );

                const response = await fetch(
                    "/api/billing/checkout",
                    {
                        method: "POST",
                        body: formData,
                    }
                );

                const data = await response.json();

                if (!response.ok) {
                    showToast(
                        data.detail || "Upgrade gagal."
                    );
                    return;
                }

                currentUsage = data.usage;
                renderPlans();
                renderAccount();

                showToast(
                    "Paket berhasil diperbarui."
                );
            });
        });
}


function renderAccount() {
    const grid = document.getElementById("account-grid");

    if (!currentUser || !currentUsage) {
        grid.innerHTML = `
            <article class="dashboard-card">
                <span>Status</span>
                <strong>Belum login</strong>
            </article>
        `;
        return;
    }

    const used = Number(currentUsage.used_count);
    const quota = Math.max(
        Number(currentUsage.monthly_quota),
        1
    );

    const percentage = Math.min(
        100,
        Math.round((used / quota) * 100)
    );

    grid.innerHTML = `
        <article class="dashboard-card">
            <span>Pengguna</span>
            <strong>
                ${escapeHtml(currentUser.display_name)}
            </strong>
            <p>${escapeHtml(currentUser.email)}</p>
        </article>

        <article class="dashboard-card">
            <span>Paket aktif</span>
            <strong>
                ${escapeHtml(currentUsage.plan_name)}
            </strong>
            <p>${formatMoney(currentUsage.price_idr)}</p>
        </article>

        <article class="dashboard-card">
            <span>Sisa kuota</span>
            <strong>
                ${escapeHtml(currentUsage.remaining)}
            </strong>
            <p>
                ${used} dari ${quota} digunakan
            </p>

            <div class="usage-bar">
                <div style="width:${percentage}%"></div>
            </div>
        </article>
    `;
}


async function submitAuth(
    form,
    endpoint,
    messageElement
) {
    messageElement.className = "message";
    messageElement.textContent = "Memproses...";

    const response = await fetch(
        endpoint,
        {
            method: "POST",
            body: new FormData(form),
        }
    );

    const data = await response.json();

    if (!response.ok) {
        messageElement.className = "message error";
        messageElement.textContent =
            data.detail || "Permintaan gagal.";
        return;
    }

    window.location.href = "/account";
}


document
    .getElementById("login-form")
    .addEventListener("submit", async (event) => {
        event.preventDefault();

        await submitAuth(
            event.currentTarget,
            "/api/auth/login",
            document.getElementById("login-message")
        );
    });


document
    .getElementById("register-form")
    .addEventListener("submit", async (event) => {
        event.preventDefault();

        await submitAuth(
            event.currentTarget,
            "/api/auth/register",
            document.getElementById("register-message")
        );
    });


document
    .getElementById("logout-button")
    .addEventListener("click", async () => {
        await fetch(
            "/api/auth/logout",
            {
                method: "POST",
            }
        );

        window.location.href = "/login";
    });


async function loadAdmin() {
    const usersContainer =
        document.getElementById("admin-users");

    const paymentsContainer =
        document.getElementById("admin-payments");

    const usersResponse =
        await fetch("/api/admin/users");

    if (!usersResponse.ok) {
        usersContainer.innerHTML =
            "<p>Akses administrator diperlukan.</p>";
        paymentsContainer.innerHTML = "";
        return;
    }

    const paymentsResponse =
        await fetch("/api/admin/payments");

    const usersData = await usersResponse.json();
    const paymentsData = await paymentsResponse.json();

    const options = plans.map((plan) => {
        return `
            <option value="${plan.plan_code}">
                ${escapeHtml(plan.name)}
            </option>
        `;
    }).join("");

    usersContainer.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Pengguna</th>
                    <th>Peran</th>
                    <th>Paket</th>
                    <th>Kuota</th>
                    <th>Status</th>
                    <th>Tindakan</th>
                </tr>
            </thead>

            <tbody>
                ${usersData.users.map((user) => {
                    return `
                        <tr>
                            <td>
                                <strong>
                                    ${escapeHtml(user.display_name)}
                                </strong>
                                <br>
                                ${escapeHtml(user.email)}
                            </td>

                            <td>${escapeHtml(user.role)}</td>
                            <td>${escapeHtml(user.plan_name)}</td>

                            <td>
                                ${escapeHtml(user.used_count)}
                                /
                                ${escapeHtml(user.monthly_quota)}
                            </td>

                            <td>
                                <span class="status ${
                                    user.is_active
                                        ? ""
                                        : "inactive"
                                }">
                                    ${
                                        user.is_active
                                            ? "Aktif"
                                            : "Nonaktif"
                                    }
                                </span>
                            </td>

                            <td>
                                <div class="table-actions">
                                    <select
                                        data-plan-select="${user.user_id}"
                                    >
                                        ${options}
                                    </select>

                                    <button
                                        class="small-button"
                                        type="button"
                                        data-save-plan="${user.user_id}"
                                    >
                                        Simpan
                                    </button>

                                    <button
                                        class="small-button"
                                        type="button"
                                        data-toggle="${user.user_id}"
                                        data-active="${
                                            user.is_active
                                                ? "false"
                                                : "true"
                                        }"
                                    >
                                        ${
                                            user.is_active
                                                ? "Nonaktifkan"
                                                : "Aktifkan"
                                        }
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join("")}
            </tbody>
        </table>
    `;

    usersData.users.forEach((user) => {
        const select = document.querySelector(
            `[data-plan-select="${user.user_id}"]`
        );

        if (select) {
            select.value = user.plan_code;
        }
    });

    document
        .querySelectorAll("[data-save-plan]")
        .forEach((button) => {
            button.addEventListener("click", async () => {
                const userId =
                    button.dataset.savePlan;

                const select = document.querySelector(
                    `[data-plan-select="${userId}"]`
                );

                const formData = new FormData();

                formData.append(
                    "plan_code",
                    select.value
                );

                await fetch(
                    `/api/admin/users/${userId}/plan`,
                    {
                        method: "POST",
                        body: formData,
                    }
                );

                showToast("Paket pengguna diperbarui.");
                loadAdmin();
            });
        });

    document
        .querySelectorAll("[data-toggle]")
        .forEach((button) => {
            button.addEventListener("click", async () => {
                const formData = new FormData();

                formData.append(
                    "active",
                    button.dataset.active
                );

                const response = await fetch(
                    `/api/admin/users/${
                        button.dataset.toggle
                    }/toggle`,
                    {
                        method: "POST",
                        body: formData,
                    }
                );

                const data = await response.json();

                if (!response.ok) {
                    showToast(
                        data.detail ||
                        "Status gagal diperbarui."
                    );
                    return;
                }

                showToast("Status pengguna diperbarui.");
                loadAdmin();
            });
        });

    paymentsContainer.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Email</th>
                    <th>Paket</th>
                    <th>Jumlah</th>
                    <th>Status</th>
                    <th>Waktu</th>
                </tr>
            </thead>

            <tbody>
                ${
                    paymentsData.payments.length
                        ? paymentsData.payments.map((payment) => {
                            return `
                                <tr>
                                    <td>
                                        ${escapeHtml(payment.email)}
                                    </td>

                                    <td>
                                        ${escapeHtml(payment.plan_name)}
                                    </td>

                                    <td>
                                        ${formatMoney(
                                            payment.amount_idr
                                        )}
                                    </td>

                                    <td>
                                        ${escapeHtml(payment.status)}
                                    </td>

                                    <td>
                                        ${new Date(
                                            payment.created_at
                                        ).toLocaleString("id-ID")}
                                    </td>
                                </tr>
                            `;
                        }).join("")
                        : `
                            <tr>
                                <td colspan="5">
                                    Belum ada pembayaran.
                                </td>
                            </tr>
                        `
                }
            </tbody>
        </table>
    `;
}


document
    .getElementById("refresh-admin")
    .addEventListener("click", loadAdmin);


async function initialize() {
    const view = currentView();

    showView(view);

    await loadMe();
    await loadPlans();

    if (
        view === "account"
        && !currentUser
    ) {
        window.location.href = "/login";
        return;
    }

    renderAccount();

    if (view === "admin") {
        await loadAdmin();
    }
}


initialize();