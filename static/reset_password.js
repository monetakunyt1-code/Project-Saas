const form = document.getElementById(
    "reset-password-form"
);

const message = document.getElementById(
    "reset-message"
);

const parameters = new URLSearchParams(
    window.location.search
);

document.getElementById(
    "reset-token"
).value = parameters.get("token") || "";


form.addEventListener(
    "submit",
    async (event) => {
        event.preventDefault();

        const formData = new FormData(form);

        const password = formData.get(
            "new_password"
        );

        const confirmation = formData.get(
            "confirmation"
        );

        if (password !== confirmation) {
            message.className = (
                "message error"
            );

            message.textContent = (
                "Konfirmasi password tidak sama."
            );

            return;
        }

        formData.delete(
            "confirmation"
        );

        const response = await fetch(
            "/api/email/password-reset/confirm",
            {
                method: "POST",
                body: formData,
            }
        );

        const data = await response.json();

        if (!response.ok) {
            message.className = (
                "message error"
            );

            message.textContent = (
                data.detail
                || "Reset password gagal."
            );

            return;
        }

        message.className = (
            "message success"
        );

        message.textContent = (
            data.message
        );

        setTimeout(() => {
            window.location.href = "/login";
        }, 1800);
    }
);
