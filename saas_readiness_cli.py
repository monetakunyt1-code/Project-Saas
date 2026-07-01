from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.saas_readiness_service import (
    LATEST_HTML,
    LATEST_JSON,
    LATEST_TEXT,
    run_readiness_audit,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "DocuRapi SaaS Readiness Gate"
        )
    )

    parser.add_argument(
        "command",
        choices=[
            "audit",
            "summary",
            "paths",
        ],
        nargs="?",
        default="audit",
    )

    arguments = parser.parse_args()

    if arguments.command == "audit":
        report = run_readiness_audit()

        print(
            json.dumps(
                report["summary"],
                ensure_ascii=False,
                indent=2,
            )
        )

        print("")
        print("BLOCKERS")

        blockers = [
            item
            for item in report["results"]
            if item["status"] == "BLOCKER"
        ]

        if blockers:
            for index, item in enumerate(
                blockers,
                start=1,
            ):
                print(
                    (
                        f"{index}. "
                        f"[{item['category']}] "
                        f"{item['name']}: "
                        f"{item['detail']}"
                    )
                )

                if item.get("action"):
                    print(
                        (
                            "   Tindakan: "
                            + item["action"]
                        )
                    )
        else:
            print("Tidak ada blocker.")

        print("")
        print("Report HTML :", LATEST_HTML)
        print("Report JSON :", LATEST_JSON)
        print("Report Text :", LATEST_TEXT)

    elif arguments.command == "summary":
        if not LATEST_JSON.exists():
            raise SystemExit(
                "Laporan belum tersedia. Jalankan audit."
            )

        report = json.loads(
            LATEST_JSON.read_text(
                encoding="utf-8"
            )
        )

        print(
            json.dumps(
                report["summary"],
                ensure_ascii=False,
                indent=2,
            )
        )

    elif arguments.command == "paths":
        print("HTML :", LATEST_HTML)
        print("JSON :", LATEST_JSON)
        print("TEXT :", LATEST_TEXT)


if __name__ == "__main__":
    main()
