from __future__ import annotations

import argparse
import json

from services.billing_service import (
    billing_health,
    get_catalog,
    list_all_orders,
    run_billing_self_test,
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
            "DocuRapi Pay-per-Use Billing CLI."
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
        "catalog"
    )

    subparsers.add_parser(
        "self-test"
    )

    orders_parser = subparsers.add_parser(
        "orders"
    )

    orders_parser.add_argument(
        "--limit",
        type=int,
        default=100,
    )

    arguments = parser.parse_args()

    if arguments.command == "health":
        print_json(
            billing_health()
        )

    elif arguments.command == "catalog":
        print_json(
            get_catalog(
                include_inactive=True
            )
        )

    elif arguments.command == "self-test":
        print_json(
            run_billing_self_test()
        )

    elif arguments.command == "orders":
        print_json(
            list_all_orders(
                limit=arguments.limit
            )
        )


if __name__ == "__main__":
    main()
