
from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path

from services.midtrans_gateway_service import (
    gateway_health,
    run_midtrans_self_test,
)


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env.production"


def set_value(
    content: str,
    name: str,
    value: str,
) -> str:
    lines = content.splitlines()
    output = []
    replaced = False

    for line in lines:
        stripped = line.strip()

        if (
            stripped
            and not stripped.startswith("#")
            and "=" in stripped
        ):
            current = stripped.split(
                "=",
                1,
            )[0].strip()

            if current == name:
                output.append(
                    f"{name}={value}"
                )

                replaced = True
                continue

        output.append(line)

    if not replaced:
        output.append(
            f"{name}={value}"
        )

    return (
        "\n".join(output).strip()
        + "\n"
    )


def configure(
    environment: str,
) -> None:
    server_key = getpass.getpass(
        (
            "Midtrans Server Key "
            "(tidak ditampilkan): "
        )
    ).strip()

    client_key = getpass.getpass(
        (
            "Midtrans Client Key "
            "(tidak ditampilkan): "
        )
    ).strip()

    if not server_key or not client_key:
        raise SystemExit(
            (
                "Server Key dan Client Key "
                "wajib diisi."
            )
        )

    content = (
        ENV_PATH.read_text(
            encoding="utf-8",
            errors="replace",
        )
        if ENV_PATH.exists()
        else ""
    )

    values = {
        "DOCURAPI_PAYMENT_PROVIDER": (
            "midtrans"
        ),
        "DOCURAPI_PAYMENT_MODE": (
            "gateway"
        ),
        "DOCURAPI_MIDTRANS_ENV": (
            environment
        ),
        "DOCURAPI_MIDTRANS_SERVER_KEY": (
            server_key
        ),
        "DOCURAPI_MIDTRANS_CLIENT_KEY": (
            client_key
        ),
        "DOCURAPI_MIDTRANS_VERIFY_STATUS": (
            "1"
        ),
    }

    for name, value in values.items():
        content = set_value(
            content,
            name,
            value,
        )

    ENV_PATH.write_text(
        content,
        encoding="utf-8",
    )

    print("")
    print(
        "MIDTRANS_CONFIGURATION_SAVED"
    )
    print(
        "Environment :",
        environment,
    )
    print(
        "Keys        : SAVED, NOT DISPLAYED"
    )
    print(
        (
            "Restart server DocuRapi "
            "setelah konfigurasi."
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "DocuRapi Midtrans Gateway CLI"
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

    configure_parser = (
        subparsers.add_parser(
            "configure"
        )
    )

    configure_parser.add_argument(
        "--environment",
        choices=[
            "sandbox",
            "production",
        ],
        default="sandbox",
    )

    arguments = parser.parse_args()

    if arguments.command == "health":
        print(
            json.dumps(
                gateway_health(),
                ensure_ascii=False,
                indent=2,
            )
        )

    elif arguments.command == "self-test":
        print(
            json.dumps(
                run_midtrans_self_test(),
                ensure_ascii=False,
                indent=2,
            )
        )

    elif arguments.command == "configure":
        configure(
            arguments.environment
        )


if __name__ == "__main__":
    main()
