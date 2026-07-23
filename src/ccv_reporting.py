"""CCV-only Excel, CSV and PDF exports."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

import pandas as pd


def _tables(result: dict) -> dict[str, pd.DataFrame]:
    project = result["project"]
    profile = pd.DataFrame([result["target"]])
    confidence = pd.DataFrame([result["confidence"]])
    assumptions = pd.DataFrame([
        {"Assumption": "Company Type", "Value": project.get("company_type")},
        {"Assumption": "Financial Period", "Value": project.get("manual_overrides", {}).get("period")},
        {"Assumption": "Outlier Method", "Value": project.get("outlier_settings", {}).get("method")},
        {"Assumption": "Outlier Threshold", "Value": project.get("outlier_settings", {}).get("threshold")},
    ])
    return {
        "Target Profile": profile,
        "Selected Peers": result["selected_peers"].reset_index(),
        "Rejected Candidates": result["rejected_candidates"].reset_index(),
        "Clean Multiples": result["clean_peers"].reset_index(),
        "Summary Statistics": result["summary_statistics"].reset_index(),
        "Outlier Analysis": result["outlier_audit"],
        "Outlier Boundaries": result["outlier_summary"].reset_index(),
        "Implied Valuation": result["implied_valuations"],
        "Confidence": confidence,
        "Assumptions": assumptions,
        "Sources": result["selected_peers"].reset_index()[["Ticker", "Data Source", "Source URL", "Financial Period", "Retrieved At"]]
        if not result["selected_peers"].empty else pd.DataFrame(),
    }


def build_ccv_excel(result: dict) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for name, frame in _tables(result).items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
    return output.getvalue()


def build_ccv_csv(result: dict) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, frame in _tables(result).items():
            archive.writestr(name.lower().replace(" ", "_") + ".csv", frame.to_csv(index=False))
    return output.getvalue()


def build_ccv_pdf(result: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=12 * mm, leftMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Comparable Company Valuation Report", styles["Title"]),
        Paragraph(str(result["target"].get("Company", "Target Company")), styles["Heading2"]),
        Paragraph(f"Generated at: {result['generated_at']} | Confidence: {result['confidence']['Level']}", styles["BodyText"]),
        Spacer(1, 8 * mm),
        Paragraph("Executive Summary", styles["Heading1"]),
        Paragraph(result["confidence"]["Explanation"], styles["BodyText"]),
    ]
    for title, frame in _tables(result).items():
        story += [PageBreak(), Paragraph(title, styles["Heading1"])]
        if frame.empty:
            story.append(Paragraph("No verified data available.", styles["BodyText"]))
            continue
        display = frame.copy().iloc[:25, :12].fillna("N/M")
        data = [list(map(str, display.columns))] + [[str(value)[:60] for value in row] for row in display.to_numpy()]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14324A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), .25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
    story += [PageBreak(), Paragraph("Limitations", styles["Heading1"]),
              Paragraph("This report uses verified provider data and user inputs. Missing values are not fabricated. "
                        "Comparable-company selection and accounting differences may materially affect the result. "
                        "This is not investment advice or a fairness opinion.", styles["BodyText"]),
              Paragraph(f"Report generated: {datetime.now(UTC).isoformat()}", styles["BodyText"])]
    doc.build(story)
    return output.getvalue()
