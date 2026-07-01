from __future__ import annotations

import argparse
import json

from services.notification_service import (
    enqueue_and_deliver_email,
    notification_health,
    outbox_items,
    send_pending_emails,
)


def print_json(
    payload: object,
) -> None:
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Notification dan Email CLI DocuRapi."
        )
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "health"
    )

    outbox_parser = subparsers.add_parser(
        "outbox"
    )

    outbox_parser.add_argument(
        "--limit",
        type=int,
        default=100,
    )

    send_parser = subparsers.add_parser(
        "send-pending"
    )

    send_parser.add_argument(
        "--limit",
        type=int,
        default=50,
    )

    test_parser = subparsers.add_parser(
        "test-email"
    )

    test_parser.add_argument(
        "--recipient",
        required=True,
    )

    arguments = parser.parse_args()

    if arguments.command == "health":
        print_json(
            notification_health()
        )

    elif arguments.command == "outbox":
        print_json(
            outbox_items(
                limit=arguments.limit
            )
        )

    elif arguments.command == "send-pending":
        print_json(
            send_pending_emails(
                limit=arguments.limit
            )
        )

    elif arguments.command == "test-email":
        print_json(
            enqueue_and_deliver_email(
                recipient=arguments.recipient,
                subject=(
                    "Pengujian email DocuRapi"
                ),
                body_text=(
                    "Email Notification Center "
                    "berfungsi dengan baik."
                ),
                body_html=(
                    "<h2>DocuRapi</h2>"
                    "<p>Email Notification Center "
                    "berfungsi dengan baik.</p>"
                ),
                template_key="test_email",
            )
        )


if __name__ == "__main__":
    main()
