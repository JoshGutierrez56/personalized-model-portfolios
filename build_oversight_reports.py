"""Create aggregate-only investment oversight workbook, memo and interview guide."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, Preformatted, KeepTogether)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from docx import Document
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs/oversight"
NAVY = "142D42"
TEAL = "006B65"
GRAY = "EEF2F5"
INK = "182D3E"


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def flat(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def tab(wb, name, rows, title, subtitle):
    ws = wb.create_sheet(name)
    ws.append([title]); ws.append([subtitle]); ws.append([])
    rows = list(rows)
    if not rows:
        ws.append(["No rows"])
    else:
        keys = list(rows[0])
        ws.append(keys)
        for row in rows:
            ws.append([flat(row.get(k)) for k in keys])
        ws.auto_filter.ref = f"A4:{get_column_letter(len(keys))}{ws.max_row}"
    ws.freeze_panes = "B5"
    for cell in ws[1]:
        cell.font = Font(name="Calibri", size=18, bold=True, color=NAVY)
    for cell in ws[2]:
        cell.font = Font(name="Calibri", size=10, italic=True, color="526574")
    for cell in ws[4]:
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.font = Font(name="Calibri", bold=True, color="FFFFFF")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for row in ws.iter_rows(min_row=5):
        for cell in row:
            cell.font = Font(name="Calibri", size=11, color=INK)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if cell.row % 2 == 1:
                cell.fill = PatternFill("solid", fgColor="F3F6F8")
            if isinstance(cell.value, float):
                cell.number_format = "0.0000"
    for j in range(1, ws.max_column + 1):
        lengths = [len(str(ws.cell(i, j).value or "")) for i in range(4, min(ws.max_row, 100) + 1)]
        ws.column_dimensions[get_column_letter(j)].width = min(55, max(16, max(lengths, default=18) + 2))
        if ws.cell(4, j).value in {"max_abs_error", "tolerance", "active_linking_residual"}:
            for row_number in range(5, ws.max_row + 1):
                ws.cell(row_number, j).number_format = "0.00E+00"
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[4].height = 32
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0
    ws.print_title_rows = "1:4"
    ws.oddFooter.center.text = "Portfolio Oversight | Aggregate research / not live orders"
    return ws


def workbook():
    baseline, incidents, receipt = read("validation_summary.json"), read("incident_summary.json"), read("run_receipt.json")
    scenarios = pd.read_csv(ROOT / "outputs/wrds/scenario_summary.csv")
    wb = Workbook(); wb.remove(wb.active)
    wb.properties.creator = "Josh Gutierrez"
    wb.properties.title = "Portfolio Validation & Investment Oversight"
    wb.properties.subject = "Independent aggregate research validation and deliberate fault-injection evidence"
    overview = [{"item": "Evidence release decision", "value": receipt["status"], "interpretation": "Technical validation only; not investment or live-trade approval."},
        {"item": "Baseline", "value": baseline["status"], "interpretation": "Separately implemented challenger using the saved licensed research."},
        {"item": "Injected faults detected", "value": f'{receipt["detected_cases"]}/{receipt["injected_cases"]}', "interpretation": "Controlled tests, not real operational incidents."},
        {"item": "Corrected original-input retest", "value": receipt["corrected_retest_status"], "interpretation": "Original source hashes remain unchanged."},
        {"item": "Investment conclusion", "value": "Do not spend tracking-risk budget solely to save tiny ETF costs", "interpretation": "For No gold, 1.10bp/year modeled savings accompanies about 27bp more realized TE."},
        {"item": "Reproducibility", "value": receipt["run_id"], "interpretation": "See RunEvidence; full empirical rerun requires own licensed inputs."}]
    tab(wb, "Decision", overview, "Portfolio oversight | decision brief", "Actual WRDS-backed aggregate research. Hypothetical accounts. Already-exposed 2014–2025 history.")
    tab(wb, "Controls", baseline.get("checks", []), "Independent control results", "PASS is technical consistency. A passing control is not proof the investment decision is optimal.")
    cases = [{"id": c["id"], "case": c["title"], "classification": c["classification"], "observed": c["observed_status"],
        "retest": c["corrected_retest"], "closure": c["closure"], "root_cause": c["root_cause"],
        "corrective_action": c["corrective_action"], "suggested_owner": c["suggested_operational_owner"],
        "acceptance_criterion": c["acceptance_criterion"]} for c in incidents["cases"]]
    tab(wb, "Exceptions", cases, "Exception register | controlled experiments", "Suggested functional owners are workflow examples, not a claim of a managed production team.")
    cols = ["client", "method", "gross_te_pct", "annual_one_way_turnover_pct", "annual_incurred_cost_bps", "net_cagr_pct", "terminal_nav"]
    ws = tab(wb, "RiskCost", scenarios[cols].to_dict("records"), "Risk and implementation economics", "TE/turnover/CAGR in %. Cost in annualized basis points of account value. Terminal NAV in USD.")
    summary = scenarios[scenarios.client.eq("No gold")].set_index("method")
    a, b = summary.loc["Minimum risk"], summary.loc["Lower turnover"]
    difference = float(a.annual_incurred_cost_bps - b.annual_incurred_cost_bps)
    tab(wb, "NoGoldDecision", [
        {"metric": "Annual one-way turnover (%)", "minimum_risk": a.annual_one_way_turnover_pct, "lower_turnover": b.annual_one_way_turnover_pct},
        {"metric": "Realized gross TE (%)", "minimum_risk": a.gross_te_pct, "lower_turnover": b.gross_te_pct},
        {"metric": "Annualized cost (bp NAV)", "minimum_risk": a.annual_incurred_cost_bps, "lower_turnover": b.annual_incurred_cost_bps},
        {"metric": "Annual cost per constant $1m (USD)", "minimum_risk": a.annual_incurred_cost_bps * 100, "lower_turnover": b.annual_incurred_cost_bps * 100}],
        "Would I authorize the lower-turnover choice?", "Conditional choice, not automatic approval: inspect mandate, cost assumptions and the price of tracking risk.")
    tab(wb, "Stress", read("historical_stress.json"), "Historical episode replay", "Preselected familiar periods within already-exposed history. Returns exclude start-close date, include end-close date.")
    agg = baseline.get("aggregate", {})
    tab(wb, "Reconciliation", [{"metric": k, "value": flat(v)} for k, v in agg.items() if k not in {"attribution_totals", "path_metrics"}],
        "Reconciliation | aggregate residuals", "Detailed security-day ledgers are intentionally excluded from this public workbook.")
    attr = agg.get("attribution_totals", [])
    if agg.get("path_metrics"):
        tab(wb, "PathMetrics", agg["path_metrics"], "Reconstructed path metrics", "One aggregate row per account/method, not security-day data. Tracking error is an annual decimal; 0.01 = 1%.")
    if isinstance(attr, list) and attr and isinstance(attr[0], dict):
        totals = [{k: v for k, v in row.items() if not isinstance(v, dict)} for row in attr]
        tab(wb, "LinkedTotals", totals, "Cumulative contribution reconciliation", "Initial-capital-scaled dollar P&L, in decimals. 0.01 = 1 percentage point of cumulative return.")
        detail = [{"client": row["client"], "method": row["method"], "asset": ticker,
                   "asset_pnl_over_initial_capital": value,
                   "benchmark_pnl_over_initial_capital": row["linked_benchmark_pnl"][ticker],
                   "active_asset_pnl_over_initial_capital": row["linked_active_asset_pnl"][ticker]}
                  for row in attr for ticker, value in row["linked_asset_pnl"].items()]
        tab(wb, "Contributions", detail, "Linked asset contributions | full-history aggregates", "Not Brinson/factor attribution or a sum of daily active returns. Add linked cost to summed active contributions to reconcile terminal wealth difference / initial capital.")
    tab(wb, "RunEvidence", [{"key": k, "value": flat(v)} for k, v in receipt.items()],
        "Run provenance and evidence", "Relative paths/hashes identify local research inputs without distributing those inputs.")
    fx = wb.create_sheet("WorkedExample")
    fx.append(["Hand-worked trade accounting | artificial teaching fixture"])
    fx.append(["These numbers are fabricated for checking formulas, NOT empirical research or an actual account."])
    fixture = [("Initial A", 600), ("Initial B", 400), ("A return", .10), ("B return", -.05),
               ("Cost rate", .001), ("Beginning NAV", "=B4+B5"), ("Pretrade A", "=B4*(1+B6)"),
               ("Pretrade B", "=B5*(1+B7)"), ("Pretrade NAV", "=B10+B11"),
               ("Fee (one sell, one buy; 50/50 target)", "=B8*(B10-B11)"),
               ("Posttrade NAV", "=B12-B13"), ("Posttrade A", "=B14/2"), ("Posttrade B", "=B14/2"),
               ("Trade A", "=B15-B10"), ("Trade B", "=B16-B11"),
               ("Funding residual", "=B17+B18+B13"), ("Gross return", "=B12/B9-1"),
               ("Net return", "=B14/B9-1"), ("Cost contribution", "=-B13/B9"),
               ("Return residual", "=B20+B22-B21")]
    fx.append([])
    for row in fixture: fx.append(row)
    fx.column_dimensions["A"].width = 65; fx.column_dimensions["B"].width = 24
    for row in fx.iter_rows(min_row=4):
        row[0].font = Font(name="Calibri", size=11, color=INK)
        row[1].number_format = "0.000000"
        row[1].fill = PatternFill("solid", fgColor="E9F4F2" if isinstance(row[1].value, str) else "EEF2F5")
    fx.freeze_panes = "B4"; fx.sheet_view.showGridLines = False
    from openpyxl.workbook.properties import CalcProperties
    wb.calculation = CalcProperties(calcId=191029, fullCalcOnLoad=True)
    path = OUT / "Portfolio_Oversight.xlsx"
    wb.save(path)
    check = load_workbook(path, read_only=False, data_only=False)
    assert len(check.worksheets) >= 9 and check["WorkedExample"]["B23"].value == "=B20+B22-B21"
    return {"path": path.name, "sheets": check.sheetnames, "formula_note": "Open in Excel/LibreOffice to recalculate teaching formulas; research figures are materialized values."}


def styles():
    fontdir = Path("C:/Windows/Fonts")
    if (fontdir / "arial.ttf").exists():
        for name, file in [("BodyFont", "arial.ttf"), ("BodyFont-Bold", "arialbd.ttf"), ("BodyFont-Italic", "ariali.ttf")]:
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(fontdir / file)))
        pdfmetrics.registerFontFamily("BodyFont", normal="BodyFont", bold="BodyFont-Bold", italic="BodyFont-Italic", boldItalic="BodyFont-Bold")
        face, bold = "BodyFont", "BodyFont-Bold"
    else:
        face, bold = "Helvetica", "Helvetica-Bold"
    if (fontdir / "consola.ttf").exists():
        if "CodeFont" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("CodeFont", str(fontdir / "consola.ttf")))
        mono = "CodeFont"
    else:
        mono = "Courier"
    s = getSampleStyleSheet()
    for name in ["Normal", "BodyText"]:
        s[name].fontName = face; s[name].fontSize = 10; s[name].leading = 14
        s[name].spaceAfter = 7
    for name, size in [("Title", 27), ("Heading1", 20), ("Heading2", 15), ("Heading3", 12)]:
        s[name].fontName = bold; s[name].fontSize = size; s[name].leading = size * 1.25
        s[name].textColor = colors.HexColor("#" + NAVY); s[name].spaceBefore = 12; s[name].spaceAfter = 8
    s.add(ParagraphStyle("SmallNote", parent=s["BodyText"], fontSize=8, leading=11, textColor=colors.HexColor("#526574")))
    s.add(ParagraphStyle("CodeBlock", parent=s["BodyText"], fontName=mono, fontSize=7.5, leading=10,
                         backColor=colors.HexColor("#F1F4F6"), borderPadding=6))
    return s


def inline(s):
    s = html.escape(s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: m[1] + (f' (<link href="{m[2]}">{m[2]}</link>)' if m[2].startswith("https://") else ""), s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', s)
    return s


def footer(canvas, doc):
    canvas.saveState(); w, h = doc.pagesize
    canvas.setStrokeColor(colors.HexColor("#D9E2E9")); canvas.line(45, 38, w - 45, 38)
    canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.HexColor("#526574"))
    canvas.drawString(45, 26, "Josh Gutierrez | Portfolio Validation & Investment Oversight")
    canvas.drawRightString(w - 45, 26, str(doc.page)); canvas.restoreState()


class GuideDocTemplate(SimpleDocTemplate):
    """Expose section navigation in PDF readers without a second source of text."""
    def afterFlowable(self, flowable):
        if hasattr(flowable, "_outline_level"):
            self._bookmark_number = getattr(self, "_bookmark_number", 0) + 1
            key = f"section-{self._bookmark_number}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(), key,
                                      level=flowable._outline_level, closed=False)


def render_markdown(source: Path, stem: str):
    text = source.read_text(encoding="utf-8")
    if re.search(r"\bTODO\b|\bTBD\b|\[INSERT", text):
        raise ValueError(f"Unresolved drafting placeholder in {source.name}")
    st = styles(); flow = []; docx = Document()
    sec = docx.sections[0]; sec.top_margin = Inches(.7); sec.bottom_margin = Inches(.65)
    sec.left_margin = Inches(.7); sec.right_margin = Inches(.7)
    normal = docx.styles["Normal"]; normal.font.name = "Calibri"; normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(6)
    docx.core_properties.author = "Josh Gutierrez"
    docx.core_properties.title = stem.replace("_", " ")
    docx.core_properties.comments = ""
    code = []; in_code = False; table = []
    def flush_table():
        nonlocal table
        if not table: return
        data = [[Paragraph(inline(x.strip()), st["SmallNote"]) for x in row] for row in table]
        n = max(map(len, data)); data = [r + [Paragraph("", st["SmallNote"])] * (n - len(r)) for r in data]
        widths = [(7.05 * inch) / n] * n
        if n == 3 and any("Location" in cell for cell in table[0]):
            widths = [7.05 * inch * fraction for fraction in (.24, .49, .27)]
        t = Table(data, repeatRows=1, colWidths=widths)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EFF3")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#D5DEE5")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]))
        flow.extend([t, Spacer(1, 8)])
        dt = docx.add_table(rows=0, cols=n); dt.style = "Light Shading Accent 1"
        for row in table:
            cells = dt.add_row().cells
            for i, val in enumerate(row): cells[i].text = val.strip().replace("**", "").replace("`", "")
        table = []
    for line in text.splitlines():
        if line.startswith("```"):
            flush_table()
            if in_code:
                raw = "\n".join(code)
                # Avoid off-page monospace: wrap only visually, preserve source separately.
                import textwrap
                wrapped = "\n".join(part for ln in code for part in (textwrap.wrap(ln, width=98, replace_whitespace=False) or [""]))
                flow.extend([Preformatted(wrapped, st["CodeBlock"]), Spacer(1, 8)])
                p = docx.add_paragraph(raw); p.style = "No Spacing"
                for run in p.runs: run.font.name = "Consolas"; run.font.size = Pt(8)
                code = []
            in_code = not in_code; continue
        if in_code: code.append(line); continue
        if line.startswith("|"):
            if not re.match(r"^\|[\s:|\-]+\|$", line): table.append(line.strip("|").split("|"))
            continue
        flush_table()
        if not line.strip(): continue
        if line.strip() == "---": flow.append(Spacer(1, 8)); continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level, title = min(len(m[1]), 3), m[2]
            style = "Title" if len(m[1]) == 1 else f"Heading{level - 1}"
            heading = Paragraph(inline(title), st[style])
            heading._outline_level = max(0, min(len(m[1]) - 2, 1))
            flow.append(heading); docx.add_heading(title, level=0 if len(m[1]) == 1 else level - 1)
        else:
            bullet = re.match(r"^(?:[-*]|\d+\.)\s+(.*)", line)
            content = bullet[1] if bullet else line.removeprefix("> ")
            flow.append(Paragraph(inline(content), st["BodyText"], bulletText="•" if bullet else None))
            docx.add_paragraph(content.replace("**", "").replace("`", ""), style="List Bullet" if bullet else "Normal")
    flush_table()
    pdf = OUT / f"{stem}.pdf"
    GuideDocTemplate(str(pdf), pagesize=(612, 792), rightMargin=45, leftMargin=45,
        topMargin=43, bottomMargin=50, title=stem.replace("_", " "), author="Josh Gutierrez").build(flow, onFirstPage=footer, onLaterPages=footer)
    docx.save(OUT / f"{stem}.docx")
    return {"pdf": pdf.name, "docx": f"{stem}.docx", "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}


def memo():
    b, i, r = read("validation_summary.json"), read("incident_summary.json"), read("run_receipt.json")
    st = styles()
    f = [Paragraph("Portfolio oversight", st["Title"]), Paragraph("Decision memo | independent validation and implementation economics", st["Heading2"]),
        Paragraph(f"Research evidence run: {r['run_id']} · {r['completed_utc'][:10]}", st["SmallNote"]),
        Paragraph("Recommendation", st["Heading2"]),
        Paragraph(f"Release the research evidence for review: baseline {b['status']}; {r['detected_cases']} of {r['injected_cases']} deliberate faults blocked; corrected inputs {r['corrected_retest_status']}. Do not interpret technical release as approval to trade a real account.", st["BodyText"]),
        Paragraph("The investment decision", st["Heading2"]),
        Paragraph("For the No gold account, lower-turnover allocation cut annual one-way turnover from 18.23% to 7.25%, but raised realized gross tracking error from 1.37% to 1.64%. At the assumed 5bp per dollar bought or sold, the annual cost-rate saving is 1.10bp of NAV: about $110 per constant $1m. That is a modest cost benefit for about 27bp more tracking risk. Prefer the minimum-risk implementation if tracking fidelity is the client's primary objective; accept lower turnover only when the mandate places a defensible value on avoiding trades. Taxes are not modeled.", st["BodyText"]),
        Paragraph("What was independently challenged", st["Heading2"]),
        Paragraph("A separate contract and challenger reconstruct total-return sleeve holdings, return contributions, self-financing costs and benchmark wealth from source returns and recorded trades. SQL checks data grain and trade/cost identities. The checker does not call the production optimizer's validation or accounting functions. Shared economic assumptions and shared source inputs remain a limitation of independence.", st["BodyText"]),
        Paragraph("Decision clock", st["Heading2"]),
        Paragraph("Estimate risk and propose weights at the previous close. Old holdings earn the execution day's return. Rebalance at that day's close and deduct costs from the account. Enforce weight bounds after execution; monitor, rather than prohibit, drift between rebalances. Realized TE is an outcome, not the same object as the ex-ante risk budget.", st["BodyText"]),
        Paragraph("Data and evidence", st["Heading2"]),
        Paragraph("Actual WRDS/CRSP CIZ data: eight ETFs and 32,192 source observations across 2010–2025; 2014–2025 evaluation, 30 account/method paths and 4,320 decisions. Current-vintage and retrospectively selected universe; the history has already been examined. All displayed accounts and trading-cost assumptions are hypothetical.", st["BodyText"]),
        PageBreak(), Paragraph("Failure investigation and release conditions", st["Heading1"])]
    for c in i["cases"]:
        f.append(Paragraph(f"{c['id']} | {html.escape(c['title'])} — {c['observed_status']}", st["Heading3"]))
        f.append(Paragraph(inline(c["injection"] + " " + c["corrective_action"] + " Corrected-input retest: " + c["corrected_retest"] + "."), st["BodyText"]))
    f.extend([Paragraph("What the evidence does not establish", st["Heading2"]),
        Paragraph("Faults are deliberately injected copies, not historical production incidents. The wrong-return case holds recorded trades fixed; its replay is diagnostic inconsistency, not a self-consistent alternative strategy. The experiment does not establish live execution readiness, tax-lot handling, stock-level factor attribution, market-impact calibration, multi-currency accounting or future alpha. Contribution reconciliation explains the accounting of this model, not a causal factor model. Passing these checks does not certify all possible errors.", st["BodyText"]),
        Paragraph("Next release conditions", st["Heading2"]),
        Paragraph("For production use: reconcile to an independent custodian/order source; implement corporate-action and tax-lot policies, market-impact and execution controls, operational ownership, monitoring and deployment review. For research discussion: retain run hashes, tolerance definitions, exception acceptance criteria and the corrected retest receipt. Detailed licensed security-day data remain private.", st["BodyText"]),
        Paragraph("Evidence: validation_summary.json, incident_summary.json, run_receipt.json, historical_stress.json and Portfolio_Oversight.xlsx. Created with AI coding and drafting assistance; interpretation and technical explanations require the presenter's own understanding.", st["SmallNote"])])
    path = OUT / "Portfolio_Oversight_Memo.pdf"
    SimpleDocTemplate(str(path), pagesize=(612, 792), leftMargin=45, rightMargin=45, topMargin=38, bottomMargin=48,
                      title="Portfolio Oversight Decision Memo", author="Josh Gutierrez").build(f, onFirstPage=footer, onLaterPages=footer)
    return path.name


def main():
    if read("run_receipt.json")["status"] != "PASS": raise RuntimeError("Do not render a release package from a failed research gate.")
    evidence = {"created_utc": datetime.now(timezone.utc).isoformat(), "workbook": workbook(), "memo": memo()}
    for path, stem in [(ROOT / "docs/INTERVIEW_GUIDE.md", "Interview_Guide"), (ROOT / "docs/OVERSIGHT_METHODOLOGY.md", "Oversight_Methodology")]:
        if path.exists(): evidence[stem] = render_markdown(path, stem)
    evidence["files"] = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted(OUT.iterdir()) if p.is_file() and p.suffix in {".pdf", ".docx", ".xlsx"}}
    (OUT / "report_manifest.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
