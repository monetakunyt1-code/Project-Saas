const adminSecretInput = document.getElementById("adminSecret");
const saveSecretBtn = document.getElementById("saveSecretBtn");
const loadAllBtn = document.getElementById("loadAllBtn");
const refreshPendingBtn = document.getElementById("refreshPendingBtn");
const cleanupDryRunBtn = document.getElementById("cleanupDryRunBtn");

const authStatus = document.getElementById("authStatus");
const readinessBox = document.getElementById("readinessBox");
const overviewBox = document.getElementById("overviewBox");
const pendingBox = document.getElementById("pendingBox");
const cleanupBox = document.getElementById("cleanupBox");

adminSecretInput.value = localStorage.getItem("docurapi_admin_secret") || "";

function showStatus(element, message, isError = false) {
  element.textContent = message;
  element.classList.remove("hidden");
  element.classList.toggle("error", isError);
}

function getSecret() {
  return adminSecretInput.value.trim();
}

function rupiah(value) {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0
  }).format(value || 0);
}

async function fetchAdmin(url, options = {}) {
  const secret = getSecret();

  if (!secret) {
    throw new Error("Admin secret belum diisi.");
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      "X-Admin-Secret": secret
    }
  });

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail = typeof data === "object" ? data.detail : data;
    throw new Error(detail || "Request admin gagal.");
  }

  return data;
}

function renderReadiness(data) {
  const payment = data.checks.payment_config;
  const db = data.checks.database;

  readinessBox.innerHTML = `
    <strong>Ready:</strong> ${data.ready ? "Ya" : "Tidak"}<br>
    <strong>Version:</strong> ${data.version}<br>
    <strong>Database OK:</strong> ${db.ok ? "Ya" : "Tidak"}<br>
    <strong>Payment Mode:</strong> ${payment.payment_mode}<br>
    <strong>Admin WhatsApp:</strong> ${payment.admin_whatsapp_configured ? "Terisi" : "Belum"}<br>
    <strong>QRIS Image:</strong> ${payment.qris_static_image_exists ? "Ada" : "Belum ada"}<br>
    <strong>Warning:</strong> ${(payment.warnings || []).join("; ") || "-"}
  `;
}

function renderOverview(data) {
  overviewBox.innerHTML = `
    <strong>Total Jobs:</strong> ${data.jobs.total}<br>
    <strong>Completed:</strong> ${data.jobs.completed}<br>
    <strong>Failed:</strong> ${data.jobs.failed}<br><br>

    <strong>Unpaid:</strong> ${data.payments.unpaid}<br>
    <strong>Pending Verification:</strong> ${data.payments.pending_verification}<br>
    <strong>Paid:</strong> ${data.payments.paid}<br>
    <strong>Rejected:</strong> ${data.payments.rejected}<br>
    <strong>Expired:</strong> ${data.payments.expired}<br>
    <strong>Revenue Paid:</strong> ${rupiah(data.payments.revenue_paid)}
  `;
}

function renderPending(data) {
  if (!data.jobs || data.jobs.length === 0) {
    pendingBox.innerHTML = `<div class="status">Tidak ada pembayaran pending.</div>`;
    return;
  }

  pendingBox.innerHTML = data.jobs.map((job) => `
    <div class="meta" style="margin-top: 14px;">
      <strong>Job ID:</strong> ${job.job_id}<br>
      <strong>File:</strong> ${job.original_name || "-"}<br>
      <strong>Mode:</strong> ${job.mode || "-"} / ${job.preset || "-"}<br>
      <strong>Status:</strong> ${job.payment_status}<br>
      <strong>Total:</strong> ${rupiah(job.amount)}<br>
      <strong>Kode unik:</strong> ${rupiah(job.unique_code)}<br>
      <strong>Expired:</strong> ${job.invoice_expires_at || "-"}<br>

      <div class="actions">
        <a class="button" href="/api/admin/payments/${job.job_id}/proof" target="_blank" data-proof="${job.job_id}">
          Lihat Bukti
        </a>
        <button type="button" data-approve="${job.job_id}">Approve</button>
        <button type="button" data-reject="${job.job_id}">Reject</button>
      </div>
    </div>
  `).join("");

  pendingBox.querySelectorAll("[data-approve]").forEach((button) => {
    button.addEventListener("click", () => approvePayment(button.dataset.approve));
  });

  pendingBox.querySelectorAll("[data-reject]").forEach((button) => {
    button.addEventListener("click", () => rejectPayment(button.dataset.reject));
  });

  pendingBox.querySelectorAll("[data-proof]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      openProof(link.dataset.proof);
    });
  });
}

async function openProof(jobId) {
  try {
    const secret = encodeURIComponent(getSecret());
    window.open(`/api/admin/payments/${jobId}/proof?secret=${secret}`, "_blank");
  } catch (error) {
    showStatus(authStatus, error.message, true);
  }
}

async function approvePayment(jobId) {
  if (!confirm(`Approve pembayaran untuk job ${jobId}?`)) return;

  try {
    await fetchAdmin(`/api/admin/payments/${jobId}/approve`, { method: "POST" });
    showStatus(authStatus, "Pembayaran berhasil di-approve.");
    await loadPending();
    await loadOverview();
  } catch (error) {
    showStatus(authStatus, error.message, true);
  }
}

async function rejectPayment(jobId) {
  const reason = prompt("Alasan reject:", "Pembayaran tidak ditemukan atau tidak sesuai.");

  if (reason === null) return;

  const formData = new FormData();
  formData.append("reason", reason);

  try {
    await fetchAdmin(`/api/admin/payments/${jobId}/reject`, {
      method: "POST",
      body: formData
    });
    showStatus(authStatus, "Pembayaran berhasil ditolak.");
    await loadPending();
    await loadOverview();
  } catch (error) {
    showStatus(authStatus, error.message, true);
  }
}

async function loadReadiness() {
  const data = await fetchAdmin("/api/admin/system/readiness");
  renderReadiness(data);
}

async function loadOverview() {
  const data = await fetchAdmin("/api/admin/dashboard/overview");
  renderOverview(data);
}

async function loadPending() {
  const data = await fetchAdmin("/api/admin/payments/pending");
  renderPending(data);
}

async function runCleanupDryRun() {
  const data = await fetchAdmin("/api/admin/cleanup/run?dry_run=true", {
    method: "POST"
  });

  cleanupBox.innerHTML = `
    <strong>Dry Run:</strong> ${data.dry_run ? "Ya" : "Tidak"}<br>
    <strong>Candidate Jobs:</strong> ${data.summary.candidate_jobs}<br>
    <strong>Deleted Jobs:</strong> ${data.summary.deleted_jobs}<br>
    <strong>Files Matched:</strong> ${data.summary.files_matched}<br>
    <strong>Files Removed:</strong> ${data.summary.files_removed}<br>
    <strong>Audit Logs Matched:</strong> ${data.summary.audit_logs_matched}
  `;
}

async function loadAll() {
  try {
    showStatus(authStatus, "Memuat admin dashboard...");
    await loadReadiness();
    await loadOverview();
    await loadPending();
    showStatus(authStatus, "Admin dashboard berhasil dimuat.");
  } catch (error) {
    showStatus(authStatus, error.message, true);
  }
}

saveSecretBtn.addEventListener("click", () => {
  localStorage.setItem("docurapi_admin_secret", getSecret());
  showStatus(authStatus, "Admin secret disimpan di browser.");
});

loadAllBtn.addEventListener("click", loadAll);
refreshPendingBtn.addEventListener("click", loadPending);

cleanupDryRunBtn.addEventListener("click", async () => {
  try {
    await runCleanupDryRun();
    showStatus(authStatus, "Cleanup dry-run berhasil.");
  } catch (error) {
    showStatus(authStatus, error.message, true);
  }
});
