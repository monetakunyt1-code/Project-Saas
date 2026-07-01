from __future__ import annotations

from html import escape
from typing import Any


def safe_text(
    value: Any,
) -> str:
    if value is None:
        return "-"

    return escape(str(value))


def metric_card(
    title: str,
    value: Any,
) -> str:
    return f"""
        <article class="metric">
            <span>{safe_text(title)}</span>
            <strong>{safe_text(value)}</strong>
        </article>
    """


def issue_rows(
    issues: list[dict[str, Any]],
) -> str:
    if not issues:
        return """
            <tr>
                <td colspan="3">
                    Tidak ditemukan masalah utama.
                </td>
            </tr>
        """

    rows: list[str] = []

    for issue in issues:
        severity = safe_text(
            issue.get("severity", "info")
        )

        code = safe_text(
            issue.get("code", "-")
        )

        message = safe_text(
            issue.get("message", "-")
        )

        rows.append(
            f"""
                <tr>
                    <td>
                        <span class="badge {severity}">
                            {severity}
                        </span>
                    </td>
                    <td>{code}</td>
                    <td>{message}</td>
                </tr>
            """
        )

    return "".join(rows)


def structure_rows(
    items: list[dict[str, Any]],
) -> str:
    if not items:
        return """
            <tr>
                <td colspan="3">
                    Data belum terdeteksi.
                </td>
            </tr>
        """

    rows: list[str] = []

    for item in items:
        rows.append(
            f"""
                <tr>
                    <td>
                        {safe_text(item.get("number", "-"))}
                    </td>
                    <td>
                        {safe_text(item.get("text", "-"))}
                    </td>
                    <td>
                        {safe_text(item.get("style", "-"))}
                    </td>
                </tr>
            """
        )

    return "".join(rows)


def render_report_html(
    payload: dict[str, Any],
) -> str:
    before = payload.get(
        "analysis_before",
        {}
    )

    after = payload.get(
        "analysis_after",
        {}
    )

    before_summary = before.get(
        "summary",
        {}
    )

    after_summary = after.get(
        "summary",
        {}
    )

    after_structure = after.get(
        "structure",
        {}
    )

    issues = after.get(
        "issues",
        []
    )

    chapters = after_structure.get(
        "chapters",
        []
    )

    subheadings = after_structure.get(
        "subheadings",
        []
    )

    document_name = payload.get(
        "original_name",
        "Dokumen"
    )

    mode = payload.get(
        "mode",
        "-"
    )

    preset = payload.get(
        "preset",
        "-"
    )

    metrics = "".join(
        [
            metric_card(
                "Paragraf",
                after_summary.get(
                    "paragraphs_total",
                    0,
                ),
            ),
            metric_card(
                "BAB",
                after_summary.get(
                    "chapters_total",
                    0,
                ),
            ),
            metric_card(
                "Subbab",
                after_summary.get(
                    "subheadings_total",
                    0,
                ),
            ),
            metric_card(
                "Tabel",
                after_summary.get(
                    "tables_total",
                    0,
                ),
            ),
            metric_card(
                "Caption tabel",
                after_summary.get(
                    "table_captions_total",
                    0,
                ),
            ),
            metric_card(
                "Caption gambar",
                after_summary.get(
                    "figure_captions_total",
                    0,
                ),
            ),
            metric_card(
                "Lampiran",
                after_summary.get(
                    "appendices_total",
                    0,
                ),
            ),
            metric_card(
                "Temuan",
                after_summary.get(
                    "issues_total",
                    0,
                ),
            ),
        ]
    )

    before_issues = before_summary.get(
        "issues_total",
        0,
    )

    after_issues = after_summary.get(
        "issues_total",
        0,
    )

    difference = before_issues - after_issues

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
    <title>Laporan DocuRapi</title>

    <style>
        :root {{
            --primary: #0f6b5d;
            --primary-soft: #e5f3ef;
            --text: #172326;
            --muted: #64767a;
            --border: #dce7e4;
            --background: #f2f7f6;
            --warning: #b7791f;
            --danger: #b83232;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: var(--background);
            color: var(--text);
            font-family:
                Inter,
                "Segoe UI",
                Arial,
                sans-serif;
        }}

        .container {{
            width: min(1180px, calc(100% - 32px));
            margin: 40px auto 80px;
        }}

        .header,
        .section {{
            padding: 30px;
            margin-bottom: 22px;
            background: white;
            border: 1px solid var(--border);
            border-radius: 22px;
        }}

        .header {{
            background:
                linear-gradient(
                    135deg,
                    var(--primary),
                    #164f47
                );
            color: white;
        }}

        h1,
        h2 {{
            margin-top: 0;
        }}

        .subtitle {{
            opacity: 0.85;
            line-height: 1.7;
        }}

        .metrics {{
            display: grid;
            grid-template-columns:
                repeat(4, minmax(0, 1fr));
            gap: 14px;
        }}

        .metric {{
            padding: 18px;
            border-radius: 16px;
            background: var(--primary-soft);
        }}

        .metric span,
        .metric strong {{
            display: block;
        }}

        .metric span {{
            margin-bottom: 8px;
            color: var(--muted);
            font-size: 13px;
        }}

        .metric strong {{
            color: var(--primary);
            font-size: 28px;
        }}

        .comparison {{
            padding: 18px;
            border-left: 5px solid var(--primary);
            background: var(--primary-soft);
            border-radius: 12px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th,
        td {{
            padding: 13px;
            border-bottom: 1px solid var(--border);
            text-align: left;
            vertical-align: top;
        }}

        th {{
            background: #f7faf9;
        }}

        .badge {{
            display: inline-flex;
            padding: 5px 9px;
            border-radius: 999px;
            background: var(--primary-soft);
            color: var(--primary);
            font-size: 12px;
            font-weight: 700;
        }}

        .badge.warning {{
            background: #fff4da;
            color: var(--warning);
        }}

        .badge.error {{
            background: #ffeded;
            color: var(--danger);
        }}

        @media (max-width: 800px) {{
            .metrics {{
                grid-template-columns:
                    repeat(2, minmax(0, 1fr));
            }}

            .section {{
                overflow-x: auto;
            }}
        }}
    </style>
</head>

<body>
    <main class="container">
        <header class="header">
            <h1>Laporan Analisis DocuRapi</h1>

            <p class="subtitle">
                Dokumen:
                <strong>{safe_text(document_name)}</strong>
                <br>
                Mode:
                <strong>{safe_text(mode)}</strong>
                · Preset:
                <strong>{safe_text(preset)}</strong>
            </p>
        </header>

        <section class="section">
            <h2>Ringkasan Dokumen</h2>

            <div class="metrics">
                {metrics}
            </div>
        </section>

        <section class="section">
            <h2>Perbandingan Temuan</h2>

            <div class="comparison">
                Temuan sebelum diproses:
                <strong>{safe_text(before_issues)}</strong>

                <br>

                Temuan setelah diproses:
                <strong>{safe_text(after_issues)}</strong>

                <br>

                Perubahan:
                <strong>{safe_text(difference)}</strong>
            </div>
        </section>

        <section class="section">
            <h2>Temuan dan Peringatan</h2>

            <table>
                <thead>
                    <tr>
                        <th>Tingkat</th>
                        <th>Kode</th>
                        <th>Keterangan</th>
                    </tr>
                </thead>

                <tbody>
                    {issue_rows(issues)}
                </tbody>
            </table>
        </section>

        <section class="section">
            <h2>Struktur BAB</h2>

            <table>
                <thead>
                    <tr>
                        <th>Nomor</th>
                        <th>Teks</th>
                        <th>Style Word</th>
                    </tr>
                </thead>

                <tbody>
                    {structure_rows(chapters)}
                </tbody>
            </table>
        </section>

        <section class="section">
            <h2>Struktur Subbab</h2>

            <table>
                <thead>
                    <tr>
                        <th>Nomor</th>
                        <th>Teks</th>
                        <th>Style Word</th>
                    </tr>
                </thead>

                <tbody>
                    {structure_rows(subheadings)}
                </tbody>
            </table>
        </section>
    </main>
</body>
</html>
"""