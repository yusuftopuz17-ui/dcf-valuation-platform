"""Generate the bundled live-data sample reports for verification."""

from pathlib import Path

from src.reporting import build_csv_bundle, build_excel, build_pdf, build_powerpoint
from valuation_platform.config import ComparableConfig, ForecastAssumptions, TerminalAssumptions, ValuationConfig, WACCAssumptions
from valuation_platform.pipeline import run_valuation


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs" / "reports"
TABLES = ROOT / "outputs" / "tables"
REPORTS.mkdir(parents=True, exist_ok=True)
TABLES.mkdir(parents=True, exist_ok=True)

config = ValuationConfig()
results = run_valuation(
    config,
    ForecastAssumptions([.12, .11, .10, .08, .05], [.47, .48, .49, .49, .50]),
    WACCAssumptions(),
    TerminalAssumptions(),
    ComparableConfig(),
)

(REPORTS / "MSFT_valuation_model.xlsx").write_bytes(build_excel(results))
(REPORTS / "MSFT_valuation_report.pdf").write_bytes(build_pdf(results))
(REPORTS / "MSFT_valuation_summary.pptx").write_bytes(build_powerpoint(results))
(TABLES / "MSFT_valuation_tables.zip").write_bytes(build_csv_bundle(results))
print(f"Raporlar üretildi: {REPORTS}")
