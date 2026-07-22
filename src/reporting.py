"""Dynamic Excel, CSV, PDF, and Open XML PowerPoint report generation."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime
from html import escape
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .formatting import money, percent


def _frames(results: dict[str, Any]) -> dict[str, pd.DataFrame]:
    profile = pd.DataFrame(list(results["market"].items()), columns=["Field", "Value"])
    assumptions = pd.DataFrame({"Year": results["forecast"].index,
                                "Revenue Growth": results["forecast_assumptions"].revenue_growth,
                                "EBITDA Margin": results["forecast_assumptions"].ebitda_margin})
    dcf_summary = pd.DataFrame([
        {**{k: v for k, v in results["dcf_pg"].items() if np.isscalar(v)}, "Method": "Sürekli Büyüme"},
        {**{k: v for k, v in results["dcf_exit"].items() if np.isscalar(v)}, "Method": "Çıkış Çarpanı"},
    ])
    peer_stats = results["peer_multiples"][[x for x in results["comparable_config"].selected_multiples if x in results["peer_multiples"]]].describe().T
    summary = pd.DataFrame([{"Method": "DCF - Perpetuity Growth", "Implied Price": results["dcf_pg"]["Implied Price"], "Upside": results["dcf_pg"]["Upside"]},
                            {"Method": "DCF - Exit Multiple", "Implied Price": results["dcf_exit"]["Implied Price"], "Upside": results["dcf_exit"]["Upside"]},
                            {"Method": "Comparable Companies", "Implied Price": results["peer_median_price"], "Upside": results["peer_median_price"] / results["market"]["Current Price"] - 1},
                            {"Method": "Blended", "Implied Price": results["blended_value"], "Upside": results["upside"]}])
    return {"Configuration": pd.DataFrame([{"Section": "Valuation", **asdict(results["config"])},
                                             {"Section": "WACC", **asdict(results["wacc_assumptions"])},
                                             {"Section": "Terminal", **asdict(results["terminal_assumptions"])}]),
            "Company Profile": profile, "Historical Financials": results["financials"],
            "Historical Metrics": results["historical_metrics"], "Forecast Assumptions": assumptions,
            "Forecast Model": results["forecast"], "UFCF": results["forecast"][["EBIT", "Tax Rate", "NOPAT", "D&A", "Capex", "Change in NWC", "UFCF"]],
            "WACC": results["wacc_bridge"], "DCF": dcf_summary,
            "DCF Sensitivity": results["sensitivities"]["WACC / Terminal Growth"],
            "Comparable Companies": results["peer_multiples"], "Peer Statistics": peer_stats,
            "Peer Exclusions": results["exclusions"], "Implied Valuations": results["implied_values"],
            "Scenario Analysis": results["scenarios"], "Football Field": results["football"],
            "Valuation Summary": summary, "Data Sources": results["sources"]}


def build_excel(results: dict[str, Any]) -> bytes:
    """Create a professional, formatted valuation workbook in memory."""
    output = io.BytesIO(); frames = _frames(results)
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        book = writer.book
        title = book.add_format({"bold": True, "font_size": 16, "font_color": "#F4F6F8", "bg_color": "#111419"})
        header = book.add_format({"bold": True, "font_color": "#F4F6F8", "bg_color": "#252B33", "align": "center"})
        input_fmt = book.add_format({"font_color": "#0000FF", "bg_color": "#FFF2CC"})
        currency_fmt = book.add_format({"num_format": '$#,##0;[Red]($#,##0);-'})
        percent_fmt = book.add_format({"num_format": '0.0%;[Red](0.0%);-'})
        multiple_fmt = book.add_format({"num_format": '0.0x;[Red](0.0x);-'})
        for sheet_name, frame in frames.items():
            frame.to_excel(writer, sheet_name=sheet_name, startrow=3, index=True)
            ws = writer.sheets[sheet_name]; ws.hide_gridlines(2); ws.freeze_panes(4, 1); ws.set_zoom(90)
            last_col = max(1, len(frame.columns))
            ws.merge_range(0, 0, 0, last_col, f"Institutional Valuation Platform - {sheet_name}", title)
            ws.write(1, 0, f"Generated: {results['generated_at'][:19]} | Currency: {results['market']['Currency']}")
            for col, name in enumerate([frame.index.name or "Index", *frame.columns]): ws.write(3, col, str(name), header)
            ws.set_column(0, 0, 24)
            for col, name in enumerate(frame.columns, 1):
                lower = str(name).lower(); fmt = None
                if any(key in lower for key in ("margin", "growth", "rate", "upside", "%", "yield", "wacc")): fmt = percent_fmt
                elif any(key in lower for key in ("multiple", "ev/", "p/e", "p/b")): fmt = multiple_fmt
                elif any(key in lower for key in ("value", "revenue", "ebit", "income", "cash", "debt", "price", "capex", "nwc", "ufcf")): fmt = currency_fmt
                ws.set_column(col, col, 19, fmt)
            if sheet_name in {"Configuration", "Forecast Assumptions"}: ws.set_column(1, last_col, 20, input_fmt)
            if sheet_name == "DCF Sensitivity": ws.conditional_format(4, 1, 3 + len(frame), last_col, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})
    return output.getvalue()


def build_csv_bundle(results: dict[str, Any]) -> bytes:
    """Create a ZIP containing every material model table as CSV."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, frame in _frames(results).items():
            archive.writestr(name.lower().replace(" ", "_") + ".csv", frame.to_csv(index=True))
    return output.getvalue()


def _chart_bytes(results: dict[str, Any], kind: str) -> io.BytesIO:
    plt.style.use("dark_background"); fig, ax = plt.subplots(figsize=(9.5, 4.8), facecolor="#111419"); ax.set_facecolor("#111419")
    if kind == "football":
        frame = results["football"]
        y = np.arange(len(frame)); ax.hlines(y, frame["Low"], frame["High"], color="#5F8FE8", linewidth=9)
        ax.scatter(frame["Median"], y, color="#F4F6F8", zorder=3); ax.axvline(results["market"]["Current Price"], color="#EF6268", linestyle="--")
        ax.set_yticks(y, frame["Method"]); ax.set_title("Football-Field Değerleme Aralığı", loc="left", fontweight="bold"); ax.set_xlabel("İma edilen hisse değeri")
    elif kind == "revenue":
        f, model = results["financials"], results["forecast"]
        years = list(f.index.year.astype(str)) + list(model.index.astype(str)); values = np.r_[f["Revenue"], model["Revenue"]] / 1e9
        ax.plot(years, values, marker="o", color="#28C7B7", linewidth=2.8); ax.axvline(len(f)-.5, color="#E5AA4F", linestyle="--")
        ax.set_title("Tarihsel ve Tahmini Hasılat", loc="left", fontweight="bold"); ax.set_ylabel("Milyar para birimi")
    else:
        s = results["scenarios"]; ax.bar(s["Scenario"], s["Implied Price"], color=["#EF6268", "#5F8FE8", "#36C98F"])
        ax.axhline(results["market"]["Current Price"], color="#E5AA4F", linestyle="--"); ax.set_title("Senaryo Değerlemesi", loc="left", fontweight="bold")
    ax.grid(alpha=.15); fig.tight_layout(); buffer = io.BytesIO(); fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor()); plt.close(fig); buffer.seek(0); return buffer


def build_pdf(results: dict[str, Any]) -> bytes:
    """Generate a multi-page executive PDF report with charts and disclaimer."""
    pdfmetrics.registerFont(TTFont("ValuationUnicode", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"))
    pdfmetrics.registerFont(TTFont("ValuationUnicode-Bold", "/System/Library/Fonts/Supplemental/Arial.ttf"))
    output = io.BytesIO(); doc = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=14*mm, leftMargin=14*mm, topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet(); styles.add(ParagraphStyle(name="TitleDark", parent=styles["Title"], fontName="ValuationUnicode-Bold", fontSize=24, leading=28, textColor=colors.HexColor("#111419"), alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="Sub", parent=styles["BodyText"], fontName="ValuationUnicode", textColor=colors.HexColor("#4B5563"), fontSize=10, leading=14))
    story = [Paragraph("DCF ve Benzer Şirket Değerlemesi", styles["TitleDark"]), Spacer(1, 5*mm),
             Paragraph(f"{escape(results['market']['Company'])} ({escape(results['market']['Ticker'])}) | Oluşturulma {results['generated_at'][:19]}", styles["Sub"]), Spacer(1, 8*mm)]
    data = [["Güncel Fiyat", "DCF (Sürekli Büyüme)", "DCF (Çıkış)", "Benzer Medyan", "Harmanlanmış", "WACC"],
            [money(results["market"]["Current Price"]), money(results["dcf_pg"]["Implied Price"]), money(results["dcf_exit"]["Implied Price"]),
             money(results["peer_median_price"]), money(results["blended_value"]), percent(results["wacc"])]]
    table = Table(data, colWidths=[43*mm]*6, rowHeights=[10*mm, 14*mm]); table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#111419")), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "ValuationUnicode-Bold"), ("FONTNAME", (0,1), (-1,1), "ValuationUnicode-Bold"), ("FONTSIZE", (0,1), (-1,1), 14),
        ("ALIGN", (0,0), (-1,-1), "CENTER"), ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#CBD5E1"))]))
    story += [table, Spacer(1, 8*mm), Image(_chart_bytes(results, "football"), width=250*mm, height=112*mm), PageBreak(),
              Paragraph("Tarihsel Performans ve Tahmin", styles["TitleDark"]), Spacer(1, 5*mm), Image(_chart_bytes(results, "revenue"), width=250*mm, height=112*mm),
              Spacer(1, 5*mm), Paragraph("Tahminler; hasılat büyümesi, EBITDA marjı, yeniden yatırım, vergi ve iskonto oranı varsayımlarına dayanır.", styles["Sub"]), PageBreak(),
              Paragraph("DCF, Senaryolar ve Temel Bulgular", styles["TitleDark"]), Spacer(1, 4*mm), Image(_chart_bytes(results, "scenario"), width=140*mm, height=62*mm)]
    for line in results["commentary"]: story += [Paragraph("- " + escape(line), styles["Sub"]), Spacer(1, 2*mm)]
    disclaimer = ParagraphStyle(name="Disclaimer", parent=styles["Heading2"], fontName="ValuationUnicode-Bold")
    story += [Spacer(1, 7*mm), Paragraph("Sorumluluk Reddi", disclaimer), Paragraph("Sonuçlar; tarihsel veriler, piyasa bilgileri, seçilen benzer şirketler ve kullanıcı varsayımlarından türetilen model tahminleridir. Tahmin garantisi, adillik görüşü veya yatırım tavsiyesi değildir.", styles["Sub"])]
    doc.build(story); return output.getvalue()


def _shape(shape_id: int, name: str, text: str, x: int, y: int, cx: int, cy: int, size: int, color: str, bold: bool = False) -> str:
    return f'''<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{escape(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" anchor="t" lIns="0" rIns="0" tIns="0" bIns="0"/><a:lstStyle/><a:p><a:pPr algn="l"/><a:r><a:rPr lang="tr-TR" sz="{size}" b="{1 if bold else 0}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:rPr><a:t>{escape(text)}</a:t></a:r><a:endParaRPr lang="tr-TR" sz="{size}"/></a:p></p:txBody></p:sp>'''


def build_powerpoint(results: dict[str, Any]) -> bytes:
    """Create an editable text-and-chart PPTX directly with Office Open XML."""
    slides = [
        ("DCF ve Benzer Şirket Değerlemesi", f"{results['market']['Company']} ({results['market']['Ticker']})\nOluşturulma: {results['generated_at'][:19]}", None),
        ("Değerleme yöntemleri modellenen aralığı gösteriyor", f"Güncel fiyat: {money(results['market']['Current Price'])}\nDCF - sürekli büyüme: {money(results['dcf_pg']['Implied Price'])}\nDCF - çıkış çarpanı: {money(results['dcf_exit']['Implied Price'])}\nBenzer şirket medyanı: {money(results['peer_median_price'])}\nHarmanlanmış değer: {money(results['blended_value'])}", "football"),
        ("Tahmini nakit üretimi varsayımlara dayanıyor", f"İlk yıl büyüme: {percent(results['forecast']['Revenue Growth'].iloc[0])}\nSon EBITDA marjı: {percent(results['forecast']['EBITDA Margin'].iloc[-1])}\nSon UFCF: {money(results['forecast']['UFCF'].iloc[-1], compact=True)}", "revenue"),
        ("Terminal varsayımlar DCF değerini etkiliyor", f"WACC: {percent(results['wacc'])}\nTerminal büyüme: {percent(results['terminal_assumptions'].terminal_growth_rate)}\nÇıkış EV/EBITDA: {results['terminal_assumptions'].exit_ebitda_multiple:.1f}x\nTerminal değer / EV: {percent(results['dcf_pg']['Terminal Value % EV'])}", None),
        ("Benzer şirketler harici piyasa kontrolü sağlıyor", f"Benzer medyan ima edilen fiyat: {money(results['peer_median_price'])}\nHedef EV/EBITDA primi/(iskontosu): {percent(results['premium_discount'])}\nBenzerler: {', '.join(results['peer_multiples'].index)}", None),
        ("Senaryo dağılımı belirsizliği gösteriyor", "\n".join(f"{'Ayı' if row['Scenario'] == 'Bear' else 'Baz' if row['Scenario'] == 'Base' else 'Boğa'}: {money(row['Implied Price'])}" for _, row in results['scenarios'].iterrows()), "scenario"),
        ("Temel bulgular", "\n".join("• " + item for item in results["commentary"]), None),
        ("Model sınırlamaları", "Tarihsel veriler gelecekteki sonuçları öngörmeyebilir. Tahminler kullanıcı varsayımlarına dayanır. Benzer şirket seçimi özneldir. Muhasebe ve para birimi farkları karşılaştırılabilirliği etkiler. Terminal değer varsayımlara son derece duyarlıdır. Piyasa verileri gecikmeli olabilir. Bu rapor yatırım tavsiyesi veya adillik görüşü değildir.", None),
    ]
    image_bytes = {kind: _chart_bytes(results, kind).getvalue() for kind in {slide[2] for slide in slides if slide[2]}}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        overrides = ''.join(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' for i in range(1, len(slides)+1))
        z.writestr("[Content_Types].xml", f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/><Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/><Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>{overrides}<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>''')
        z.writestr("_rels/.rels", '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>''')
        z.writestr("docProps/core.xml", f'''<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>Valuation Summary</dc:title><dc:creator>Institutional Valuation Platform</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">{datetime.now(UTC).isoformat()}</dcterms:created></cp:coreProperties>''')
        z.writestr("docProps/app.xml", f'''<?xml version="1.0" encoding="UTF-8"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Institutional Valuation Platform</Application><Slides>{len(slides)}</Slides></Properties>''')
        sld_ids = ''.join(f'<p:sldId id="{255+i}" r:id="rId{i+1}"/>' for i in range(1, len(slides)+1))
        z.writestr("ppt/presentation.xml", f'''<?xml version="1.0" encoding="UTF-8"?><p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>{sld_ids}</p:sldIdLst><p:sldSz cx="12192000" cy="6858000" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>''')
        pres_rels = '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>' + ''.join(f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>' for i in range(1, len(slides)+1))
        z.writestr("ppt/_rels/presentation.xml.rels", f'''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{pres_rels}</Relationships>''')
        master_tree = '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        z.writestr("ppt/slideMasters/slideMaster1.xml", f'''<?xml version="1.0" encoding="UTF-8"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree>{master_tree}</p:spTree></p:cSld><p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/><p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>''')
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>''')
        z.writestr("ppt/slideLayouts/slideLayout1.xml", f'''<?xml version="1.0" encoding="UTF-8"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank"><p:cSld name="Blank"><p:spTree>{master_tree}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>''')
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>''')
        z.writestr("ppt/theme/theme1.xml", '''<?xml version="1.0" encoding="UTF-8"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Institutional"><a:themeElements><a:clrScheme name="Institutional"><a:dk1><a:srgbClr val="050607"/></a:dk1><a:lt1><a:srgbClr val="F4F6F8"/></a:lt1><a:dk2><a:srgbClr val="111419"/></a:dk2><a:lt2><a:srgbClr val="A7B0BC"/></a:lt2><a:accent1><a:srgbClr val="28C7B7"/></a:accent1><a:accent2><a:srgbClr val="5F8FE8"/></a:accent2><a:accent3><a:srgbClr val="8979E6"/></a:accent3><a:accent4><a:srgbClr val="36C98F"/></a:accent4><a:accent5><a:srgbClr val="E5AA4F"/></a:accent5><a:accent6><a:srgbClr val="EF6268"/></a:accent6><a:hlink><a:srgbClr val="5F8FE8"/></a:hlink><a:folHlink><a:srgbClr val="8979E6"/></a:folHlink></a:clrScheme><a:fontScheme name="Inter"><a:majorFont><a:latin typeface="Arial"/></a:majorFont><a:minorFont><a:latin typeface="Arial"/></a:minorFont></a:fontScheme><a:fmtScheme name="Institutional"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme></a:themeElements></a:theme>''')
        image_counter = 0
        for index, (title, body, image_kind) in enumerate(slides, 1):
            shapes = master_tree + _shape(2, "Title", title, 650000, 420000, 10800000, 800000, 2800 if index > 1 else 3600, "F4F6F8", True)
            body_width = 5000000 if image_kind else 10800000
            shapes += _shape(3, "Body", body, 700000, 1500000, body_width, 4200000, 1700, "A7B0BC")
            rels = '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            if image_kind:
                image_counter += 1; media_name = f"image{image_counter}.png"; z.writestr(f"ppt/media/{media_name}", image_bytes[image_kind])
                rels += f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{media_name}"/>'
                shapes += f'''<p:pic><p:nvPicPr><p:cNvPr id="4" name="Chart"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="5900000" y="1500000"/><a:ext cx="5600000" cy="3600000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'''
            z.writestr(f"ppt/slides/slide{index}.xml", f'''<?xml version="1.0" encoding="UTF-8"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="050607"/></a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree>{shapes}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>''')
            z.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", f'''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>''')
    return output.getvalue()
