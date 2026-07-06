from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from docurapi.main import app  # noqa: E402


def main() -> None:
    output_path = PROJECT_ROOT / "docs" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    schema = app.openapi()

    output_path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"OpenAPI schema exported to {output_path}")


if __name__ == "__main__":
    main()
