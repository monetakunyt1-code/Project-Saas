const params = new URLSearchParams(window.location.search);
const jobId = params.get("job_id");
const token = params.get("token");

const statusBox = document.getElementById("statusBox");
const statusDetail = document.getElementById("statusDetail");
const statusActions = document.getElementById("statusActions");

function rupiah(value) {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0
  }).format(value || 0);
}

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
}

function renderActions(paymentStatus) {
  statusActions.innerHTML = "";

  const invoiceLink = document.createElement("a");
  invoiceLink.className = "button";
  invoiceLink.href = `/api/payments/${jobId}/invoice?token=${token}`;
  invoiceLink.target = "_blank";
  invoiceLink.textContent = "Lihat Invoice";
  statusActions.appendChild(invoiceLink);

  const refreshButton = document.createElement("button");
  refreshButton.type = "button";
  refreshButton.textContent = "Refresh Status";
  refreshButton.addEventListener("click", loadStatus);
  statusActions.appendChild(refreshButton);

  if (paymentStatus === "paid") {
    const downloadLink = document.createElement("a");
    downloadLink.className = "button";
    downloadLink.href = `/api/jobs/${jobId}/download?token=${token}`;
    downloadLink.textContent = "Download Dokumen";
    statusActions.appendChild(downloadLink);

    const receiptLink = document.createElement("a");
    receiptLink.className = "button";
    receiptLink.href = `/api/payments/${jobId}/receipt?token=${token}`;
    receiptLink.target = "_blank";
    receiptLink.textContent = "Lihat Receipt";
    statusActions.appendChild(receiptLink);
  }

  if (paymentStatus === "expired") {
    const refreshInvoiceButton = document.createElement("button");
    refreshInvoiceButton.type = "button";
    refreshInvoiceButton.textContent = "Refresh Invoice";
    refreshInvoiceButton.addEventListener("click", refreshInvoice);
    statusActions.appendChild(refreshInvoiceButton);
  }
}

async function refreshInvoice() {
  try {
    setStatus("Memperbarui invoice...");

    const response = await fetch(`/api/payments/${jobId}/refresh-invoice?token=${token}`, {
      method: "POST"
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.detail || data.message || "Gagal refresh invoice.");
    }

    setStatus("Invoice berhasil diperbarui. Gunakan nominal terbaru.");
    await loadStatus();
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function loadStatus() {
  if (!jobId || !token) {
    setStatus("Parameter job_id atau token tidak ditemukan.", true);
    return;
  }

  try {
    const response = await fetch(`/api/payments/${jobId}/status?token=${token}`);
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.detail || data.message || "Gagal mengambil status.");
    }

    const paymentStatus = data.job_payment_status;

    let message = `Status pembayaran: ${paymentStatus}`;

    if (paymentStatus === "paid") {
      message = "Pembayaran sudah disetujui. Dokumen bisa di-download.";
    } else if (paymentStatus === "pending_verification") {
      message = "Pembayaran sedang menunggu verifikasi admin.";
    } else if (paymentStatus === "expired") {
      message = "Invoice sudah kedaluwarsa. Refresh invoice untuk mendapat nominal baru.";
    } else if (paymentStatus === "rejected") {
      message = "Pembayaran ditolak. Hubungi admin atau refresh invoice.";
    }

    setStatus(message);

    statusDetail.innerHTML = `
      <strong>Job ID:</strong> ${data.job_id}<br>
      <strong>Status:</strong> ${paymentStatus}<br>
      <strong>Harga dasar:</strong> ${rupiah(data.base_amount)}<br>
      <strong>Kode unik:</strong> ${rupiah(data.unique_code)}<br>
      <strong>Total bayar:</strong> ${rupiah(data.amount)}<br>
      <strong>Expired:</strong> ${data.invoice_expires_at || "-"}<br>
      <strong>Invoice expired:</strong> ${data.invoice_expired ? "Ya" : "Tidak"}
    `;

    renderActions(paymentStatus);
  } catch (error) {
    setStatus(error.message, true);
  }
}

loadStatus();
setInterval(loadStatus, 15000);
