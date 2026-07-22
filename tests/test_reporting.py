"""Formatting and download-generation tests."""

import io
import zipfile

from src.formatting import basis_points, money, multiple, percent
from src.reporting import build_csv_bundle, build_excel, build_pdf, build_powerpoint


def test_financial_formatting():
    assert money(3.25e9, compact=True) == "$3.2B"
    assert percent(-.087) == "-8.7%"
    assert multiple(14.6) == "14.6x"
    assert basis_points(.0075) == "75 bps"


def test_excel_and_csv_exports(results):
    excel = build_excel(results)
    assert excel[:2] == b"PK"
    csv_zip = build_csv_bundle(results)
    with zipfile.ZipFile(io.BytesIO(csv_zip)) as archive:
        assert "valuation_summary.csv" in archive.namelist()
        assert len(archive.namelist()) == 18


def test_pdf_and_powerpoint_exports(results):
    pdf = build_pdf(results)
    assert pdf.startswith(b"%PDF") and len(pdf) > 10_000
    pptx = build_powerpoint(results)
    with zipfile.ZipFile(io.BytesIO(pptx)) as archive:
        assert "ppt/presentation.xml" in archive.namelist()
        assert len([x for x in archive.namelist() if x.startswith("ppt/slides/slide") and x.endswith(".xml")]) == 8

