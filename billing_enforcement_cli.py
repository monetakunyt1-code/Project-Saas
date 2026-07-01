from __future__ import annotations

import argparse
import json

from services.billing_enforcement_service import (
    cleanup_expired_reservations,
    enforcement_health,
    list_all_reservations,
    run_enforcement_self_test,
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
            "DocuRapi Billing Enforcement CLI."
        )
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "health"
    )

    subparsers.add_parser(
        "self-test"
    )

    subparsers.add_parser(
        "cleanup"
    )

    reservations_parser = (
        subparsers.add_parser(
            "reservations"
        )
    )

    reservations_parser.add_argument(
        "--limit",
        type=int,
        default=100,
    )

    reservations_parser.add_argument(
        "--status",
        default=None,
    )

    arguments = parser.parse_args()

    if arguments.command == "health":
        print_json(
            enforcement_health()
        )

    elif arguments.command == "self-test":
        print_json(
            run_enforcement_self_test()
        )

    elif arguments.command == "cleanup":
        print_json(
            {
                "expired_cleaned": (
                    cleanup_expired_reservations()
                )
            }
        )

    elif arguments.command == "reservations":
        print_json(
            list_all_reservations(
                limit=arguments.limit,
                status=arguments.status,
            )
        )


if __name__ == "__main__":
    main()
