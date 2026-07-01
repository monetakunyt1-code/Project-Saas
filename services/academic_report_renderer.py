from __future__ import annotations

from html import escape
from typing import Any


def safe(value: Any) -> str:
    if value is None:
        return "-"

    return escape(
        str(value)
    )


def metric(
    label: str,
    value: Any,
) -> str:
    return f"""
        <article class="metric">
            <span>{safe(label)}</span>
            <strong>{safe(value)}</strong>
        </article>
    """


def finding_rows(
    findings: list[dict[str, Any]],
) -> str:
    if not findings:
        return """
            <tr>
                <td colspan="5">
                    Tidak ditemukan masalah utama.
                </td>
            </tr>
        """

    rows: list[str] = []

    for finding in findings:
        severity = safe(
            finding.get(
                "severity",
                "info",
            )
        )

        rows.append(
            f"""
                <tr>
                    <td>
                        <span class="badge {severity}">
                            {severity}
                        </span>
                    </td>

                    <td>
                        {safe(finding.get("title"))}
                    </td>

                    <td>
                        {safe(finding.get("message"))}
                    </td>

                    <td>
                        {safe(finding.get("location"))}
                    </td>

                    <td>
                        {safe(finding.get("recommendation"))}
                    </td>
                </tr>
            """
        )

    return "".join(rows)


def checklist_rows(
    checklist: list[dict[str, Any]],
) -> str:
    if not checklist:
        return """
            <tr>
                <td colspan="3">
                    Checklist belum tersedia.
                </td>
            </tr>
        """

    rows: list[str] = []

    for item in checklist:
        status = safe(
            item.get(
                "status",
                "failed",
            )
        )

        rows.append(
            f"""
                <tr>
                    <td>
                        {safe(item.get("item"))}
                    </td>

                    <td>
                        <span class="badge {status}">
                            {status}
                        </span>
                    </td>

                    <td>
                        {safe(item.get("message"))}
                    </td>
                </tr>
            """
        )

    return "".join(rows)


def structure_rows(
    items: list[dict[str, Any]],
    number_key: str,
) -> str:
    if not items:
        return """
            <tr>
                <td colspan="3">
                    Struktur belum terdeteksi.
                </td>
            </tr>
        """

    rows: list[str] = []

    for item in items:
        rows.append(
            f"""
                <tr>
                    <td>
                        {safe(item.get(number_key))}
                    </td>

                    <td>
                        {safe(item.get("text"))}
                    </td>

                    <td>
                        {safe(item.get("style"))}
                    </td>
                </tr>
            """
        )

    return "".join(rows)


def render_academic_report(
    report: dict[str, Any],
) -> str:
    file_data = report.get(
        "file",
        {}
    )

    score = report.get(
        "score",
        {}
    )

    summary = report.get(
        "summary",
        {}
    )

    structure = report.get(
        "structure",
        {}
    )

    citations = report.get(
        "citations",
        {}
    )

    findings = report.get(
        "findings",
        []
    )

    checklist = report.get(
        "checklist",
        []
    )

    metrics = "".join(
        [
            metric(
                "Skor",
                score.get(
                    "score",
                    0,
                ),
            ),
            metric(
                "BAB",
                summary.get(
                    "chapters_total",
                    0,
                ),
            ),
            metric(
                "Subbab",
                summary.get(
                    "subheadings_total",
                    0,
                ),
            ),
            metric(
                "Tabel",
                summary.get(
                    "tables_total",
                    0,
                ),
            ),
            metric(
                "Gambar",
                summary.get(
                    "inline_images_total",
                    0,
                ),
            ),
            metric(
                "Sitasi",
                citations.get(
                    "citations_total",
                    0,
                ),
            ),
            metric(
                "Referensi",
                citations.get(
                    "references_total",
                    0,
                ),
            ),
            metric(
                "Temuan",
                summary.get(
                    "findings_total",
                    0,
                ),
            ),
        ]
    )

    limitations = "".join(
        f"<li>{safe(item)}</li>"
        for item in report.get(
            "limitations",
            []
        )
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Laporan Audit Akademik DocuRapi</title>

    <style>
        :root {{
            --primary: #0f6b5d;
            --primary-dark: #084d43;
            --primary-soft: #e5f3ef;
            --background: #f2f7f6;
            --card: #ffffff;
            --text: #172326;
            --muted: #66777b;
            --border: #dce7e4;
            --danger: #b83232;
            --warning: #9c6719;
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
            width: min(1260px, calc(100% - 32px));
            margin: 36px auto 80px;
        }}

        .header,
        .section {{
            margin-bottom: 22px;
            padding: 30px;
            border: 1px solid var(--border);
            border-radius: 22px;
            background: var(--card);
        }}

        .header {{
            background:
                linear-gradient(
                    135deg,
                    var(--primary),
                    var(--primary-dark)
                );
            color: white;
        }}

        h1,
        h2 {{
            margin-top: 0;
        }}

        .header p {{
            margin-bottom: 0;
            line-height: 1.7;
            opacity: 0.9;
        }}

        .score-box {{
            display: flex;
            align-items: center;
            gap: 24px;
            margin-top: 24px;
        }}

        .score-number {{
            min-width: 110px;
            height: 110px;
            display: grid;
            place-items: center;
            border-radius: 50%;
            background: white;
            color: var(--primary);
            font-size: 42px;
            font-weight: 900;
        }}

        .metric-grid {{
            display: grid;
            grid-template-columns:
                repeat(4, minmax(0, 1fr));
            gap: 14px;
        }}

        .metric {{
            padding: 18px;
            border-radius: 15px;
            background: var(--primary-soft);
        }}

        .metric span,
        .metric strong {{
            display: block;
        }}

        .metric span {{
            margin-bottom: 7px;
            color: var(--muted);
            font-size: 13px;
        }}

        .metric strong {{
            color: var(--primary);
            font-size: 28px;
        }}

        .table-wrap {{
            overflow-x: auto;
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
            color: var(--primary-dark);
            font-size: 12px;
            font-weight: 800;
        }}

        .badge.error,
        .badge.failed {{
            background: #ffeded;
            color: var(--danger);
        }}

        .badge.warning {{
            background: #fff4d9;
            color: var(--warning);
        }}

        .badge.passed {{
            background: var(--primary-soft);
            color: var(--primary-dark);
        }}

        .note {{
            padding: 18px;
            border-left: 5px solid var(--primary);
            border-radius: 12px;
            background: var(--primary-soft);
            line-height: 1.7;
        }}

        li {{
            margin-bottom: 8px;
            line-height: 1.6;
        }}

        @media (max-width: 850px) {{
            .metric-grid {{
                grid-template-columns:
                    repeat(2, minmax(0, 1fr));
            }}

            .score-box {{
                align-items: flex-start;
                flex-direction: column;
            }}
        }}
    </style>
</head>

<body>
    <main class="container">
        <header class="header">
            <h1>Audit Akademik DocuRapi</h1>

            <p>
                Dokumen:
                <strong>{safe(file_data.get("name"))}</strong>

                <br>

                Jenis:
                <strong>{safe(report.get("document_type"))}</strong>

                <br>

                Waktu audit:
                <strong>{safe(report.get("audited_at"))}</strong>
            </p>

            <div class="score-box">
                <div class="score-number">
                    {safe(score.get("score", 0))}
                </div>

                <div>
                    <h2>
                        {safe(score.get("grade", "-"))}
                    </h2>

                    <p>
                        Error:
                        <strong>{safe(score.get("errors", 0))}</strong>
                        · Warning:
                        <strong>{safe(score.get("warnings", 0))}</strong>
                        · Informasi:
                        <strong>{safe(score.get("information", 0))}</strong>
                    </p>
                </div>
            </div>
        </header>

        <section class="section">
            <h2>Ringkasan</h2>

            <div class="metric-grid">
                {metrics}
            </div>
        </section>

        <section class="section">
            <h2>Checklist Kelengkapan</h2>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Komponen</th>
                            <th>Status</th>
                            <th>Keterangan</th>
                        </tr>
                    </thead>

                    <tbody>
                        {checklist_rows(checklist)}
                    </tbody>
                </table>
            </div>
        </section>

        <section class="section">
            <h2>Temuan Audit</h2>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Tingkat</th>
                            <th>Temuan</th>
                            <th>Keterangan</th>
                            <th>Lokasi</th>
                            <th>Rekomendasi</th>
                        </tr>
                    </thead>

                    <tbody>
                        {finding_rows(findings)}
                    </tbody>
                </table>
            </div>
        </section>

        <section class="section">
            <h2>Struktur BAB</h2>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Nomor</th>
                            <th>Teks</th>
                            <th>Style</th>
                        </tr>
                    </thead>

                    <tbody>
                        {
                            structure_rows(
                                structure.get(
                                    "chapters",
                                    [],
                                ),
                                "number",
                            )
                        }
                    </tbody>
                </table>
            </div>
        </section>

        <section class="section">
            <h2>Struktur Subbab</h2>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Nomor</th>
                            <th>Teks</th>
                            <th>Style</th>
                        </tr>
                    </thead>

                    <tbody>
                        {
                            structure_rows(
                                structure.get(
                                    "subheadings",
                                    [],
                                ),
                                "numbering",
                            )
                        }
                    </tbody>
                </table>
            </div>
        </section>

        <section class="section">
            <h2>Catatan Interpretasi</h2>

            <div class="note">
                Pencocokan sitasi dengan daftar pustaka dilakukan
                menggunakan nama penulis dan tahun yang dapat
                dikenali secara otomatis. Hasilnya perlu ditinjau
                kembali untuk sumber dengan nama lembaga, tanpa
                tahun, atau gaya sitasi yang tidak umum.
            </div>
        </section>

        <section class="section">
            <h2>Batasan Audit</h2>

            <ul>
                {limitations}
            </ul>
        </section>
    </main>
</body>
</html>
"""