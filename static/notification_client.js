async function refreshNotificationBadge() {
    const launcher = document.querySelector(
        ".notification-center-launch"
    );

    if (!launcher) {
        return;
    }

    try {
        const response = await fetch(
            "/api/notifications/unread-count"
        );

        if (!response.ok) {
            return;
        }

        const data = await response.json();

        let badge = launcher.querySelector(
            ".notification-badge"
        );

        if (!data.unread_count) {
            if (badge) {
                badge.remove();
            }

            return;
        }

        if (!badge) {
            badge = document.createElement(
                "span"
            );

            badge.className = (
                "notification-badge"
            );

            launcher.appendChild(
                badge
            );
        }

        badge.textContent = (
            data.unread_count > 99
            ? "99+"
            : String(data.unread_count)
        );
    }
    catch {
        return;
    }
}


refreshNotificationBadge();

setInterval(
    refreshNotificationBadge,
    30000
);
