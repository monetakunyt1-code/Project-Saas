let currentJobId = null;
let currentToken = null;

const uploadForm = document.getElementById("uploadForm");
const confirmForm = document.getElementById("confirmForm");
const statusBox = document.getElementById("status");
const resultCard = document.getElementById("resultCard");
const paymentCard = document.getElementById("paymentCard");
const resultBox = document.getElementById("result");
const confirmResult = document.getElementById("confirmResult");

function showStatus(element, message, isError = false) {
  element.textContent = message;
  element.classList.remove("hidden");
  element.classList.toggle("error", isError);
}

function tokenFromUrl(url) {
  const marker = "token=";
  const index = url.indexOf(marker);

  if (index === -1) {
    return "";
  }

  return url.slice(index + marker.length);
}

function rupiah(value) {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0
  }).format(value || 0);
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  statusBox.classList.add("hidden");
  resultCard.classList.add("hidden");
  paymentCard.classList.add("hidden");
  showStatus(statusBox, "Memproses dokumen...");

  const formData = new FormData(uploadForm);

  try {
    const response = await fetch("/api/process", {
      method: "POST",
      body: formData
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.detail || data.message || "Gagal memproses dokumen.");
    }

    currentJobId = data.job_id;
    currentToken = tokenFromUrl(data.payment_url);

    resultBox.innerHTML = `
      <div class="meta">
        <strong>Job ID:</strong> ${data.job_id}<br>
        <strong>Status pembayaran:</strong> ${data.payment_status}<br>
        <strong>Harga dasar:</strong> ${rupiah(data.base_amount)}<br>
        <strong>Kode unik:</strong> ${rupiah(data.unique_code)}<br>
        <strong>Total bayar:</strong> ${rupiah(data.amount)}<br>
        <strong>Expired:</strong> ${data.invoice_expires_at || "-"}
      </div>

      <div class="actions">
        <a class="button" href="${data.preview_url}" target="_blank">Lihat Preview</a>
        <a class="button" href="${data.report_url}" target="_blank">Lihat Report</a>
        <a class="button" href="/api/payments/${data.job_id}/invoice?token=${currentToken}" target="_blank">Lihat Invoice</a>
        <a class="button" href="/static/app/status.html?job_id=${data.job_id}&token=${currentToken}" target="_blank">Cek Status</a>
        <a class="button" href="${data.payment_url}" target="_blank">Checkout JSON</a>
      </div>
    `;

    resultCard.classList.remove("hidden");
    paymentCard.classList.remove("hidden");
    saveLastJob(data, currentToken);
    showStatus(statusBox, "Dokumen berhasil diproses. Silakan cek invoice dan lakukan pembayaran.");

  } catch (error) {
    showStatus(statusBox, error.message, true);
  }
});

confirmForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!currentJobId || !currentToken) {
    showStatus(confirmResult, "Job belum tersedia. Upload dokumen dulu.", true);
    return;
  }

  showStatus(confirmResult, "Mengirim konfirmasi pembayaran...");

  const formData = new FormData(confirmForm);

  try {
    const response = await fetch(`/api/payments/${currentJobId}/confirm-manual?token=${currentToken}`, {
      method: "POST",
      body: formData
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.detail || data.message || "Gagal mengirim konfirmasi pembayaran.");
    }

    let message = "Konfirmasi pembayaran berhasil dikirim. Tunggu admin memverifikasi pembayaran.";

    if (data.admin_whatsapp_url) {
      message += " Link WhatsApp admin tersedia di bawah.";
      confirmResult.innerHTML = `
        <p>${message}</p>
        <div class="actions">
          <a class="button" href="${data.admin_whatsapp_url}" target="_blank">Buka WhatsApp Admin</a>
          <a class="button" href="/static/app/status.html?job_id=${currentJobId}&token=${currentToken}" target="_blank">Cek Status Pembayaran</a>
        </div>
      `;
      confirmResult.classList.remove("hidden");
      confirmResult.classList.remove("error");
      return;
    }

    showStatus(confirmResult, message);

  } catch (error) {
    showStatus(confirmResult, error.message, true);
  }
});


function saveLastJob(data, token) {
  const lastJob = {
    job_id: data.job_id,
    token: token,
    payment_status: data.payment_status,
    amount: data.amount,
    base_amount: data.base_amount,
    unique_code: data.unique_code,
    invoice_expires_at: data.invoice_expires_at,
    saved_at: new Date().toISOString()
  };

  localStorage.setItem("docurapi_last_job", JSON.stringify(lastJob));
  renderLastJob();
}

function getLastJob() {
  try {
    return JSON.parse(localStorage.getItem("docurapi_last_job") || "null");
  } catch {
    return null;
  }
}

function clearLastJob() {
  localStorage.removeItem("docurapi_last_job");
  renderLastJob();
}

function renderLastJob() {
  const lastJob = getLastJob();
  let card = document.getElementById("lastJobCard");

  if (!card) {
    card = document.createElement("section");
    card.id = "lastJobCard";
    card.className = "card";
    const firstCard = document.querySelector(".card");
    if (firstCard && firstCard.parentNode) {
      firstCard.parentNode.insertBefore(card, firstCard.nextSibling);
    } else {
      document.querySelector(".page").appendChild(card);
    }
  }

  if (!lastJob) {
    card.classList.add("hidden");
    card.innerHTML = "";
    return;
  }

  card.classList.remove("hidden");
  card.innerHTML = `
    <h2>Dokumen Terakhir</h2>
    <div class="meta">
      <strong>Job ID:</strong> ${lastJob.job_id}<br>
      <strong>Status terakhir:</strong> ${lastJob.payment_status || "-"}<br>
      <strong>Total bayar:</strong> ${rupiah(lastJob.amount)}<br>
      <strong>Kode unik:</strong> ${rupiah(lastJob.unique_code)}<br>
      <strong>Expired:</strong> ${lastJob.invoice_expires_at || "-"}<br>
      <strong>Disimpan:</strong> ${lastJob.saved_at || "-"}
    </div>
    <div class="actions">
      <a class="button" href="/static/app/status.html?job_id=${lastJob.job_id}&token=${lastJob.token}" target="_blank">Cek Status</a>
      <a class="button" href="/api/payments/${lastJob.job_id}/invoice?token=${lastJob.token}" target="_blank">Lihat Invoice</a>
      <button type="button" id="clearLastJobBtn">Hapus Riwayat Lokal</button>
    </div>
  `;

  const clearButton = document.getElementById("clearLastJobBtn");
  if (clearButton) {
    clearButton.addEventListener("click", clearLastJob);
  }
}

renderLastJob();
