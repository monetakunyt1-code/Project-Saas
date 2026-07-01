from __future__ import annotations

import argparse
import json

from services.acceptance_factory import (
    create_acceptance_fixtures,
)
from services.acceptance_runner import (
    load_latest_report,
    run_acceptance_suite,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "DocuRapi Acceptance Test "
            "dan Release Readiness."
        )
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    run_parser = subparsers.add_parser(
        "run"
    )

    run_parser.add_argument(
        "--mode",
        choices=[
            "structural",
            "full",
        ],
        default="full",
    )

    run_parser.add_argument(
        "--json",
        action="store_true",
    )

    subparsers.add_parser(
        "latest"
    )

    subparsers.add_parser(
        "fixtures"
    )

    arguments = parser.parse_args()

    if arguments.command == "run":
        report = run_acceptance_suite(
            mode=arguments.mode
        )

        if arguments.json:
            print(
                json.dumps(
                    report,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
        else:
            summary = report["summary"]

            print("")
            print(
                "DOCURAPI ACCEPTANCE RESULT"
            )
            print(
                "--------------------------------"
            )
            print(
                "Mode      :",
                report["mode"],
            )
            print(
                "Status    :",
                summary["readiness"],
            )
            print(
                "Score     :",
                f"{summary['score']}/100",
            )
            print(
                "PASS      :",
                summary["pass"],
            )
            print(
                "FAIL      :",
                summary["fail"],
            )
            print(
                "WARNING   :",
                summary["warning"],
            )
            print(
                "SKIPPED   :",
                summary["skipped"],
            )
            print("")
            print(
                "JSON      :",
                report[
                    "report_files"
                ]["json"],
            )
            print(
                "HTML      :",
                report[
                    "report_files"
                ]["html"],
            )
            print(
                "Markdown  :",
                report[
                    "report_files"
                ]["markdown"],
            )

    elif arguments.command == "latest":
        report = load_latest_report()

        print(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

    elif arguments.command == "fixtures":
        print(
            json.dumps(
                create_acceptance_fixtures(),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
