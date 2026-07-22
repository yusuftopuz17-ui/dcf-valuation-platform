"""Validated valuation configuration objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


def clean_ticker(value: str) -> str:
    """Validate and normalize an exchange ticker."""
    ticker = str(value).strip().upper()
    if not ticker or len(ticker) > 15 or not all(ch.isalnum() or ch in ".-" for ch in ticker):
        raise ValueError(f"Geçersiz sembol: {value!r}")
    return ticker


def validate_rate(name: str, value: float, low: float = -0.5, high: float = 1.0) -> None:
    if not low <= float(value) <= high:
        raise ValueError(f"{name}, {low:.1%} ile {high:.1%} arasında olmalıdır.")


@dataclass
class ValuationConfig:
    target_ticker: str = "MSFT"
    peer_tickers: list[str] = field(default_factory=lambda: ["AAPL", "GOOGL", "ORCL", "CRM", "ADBE"])
    historical_years: int = 5
    forecast_years: int = 5
    valuation_date: str | None = None
    base_currency: str = "USD"
    mid_year_discounting: bool = True
    stale_market_days: int = 10
    terminal_value_warning_threshold: float = 0.80

    def __post_init__(self) -> None:
        self.target_ticker = clean_ticker(self.target_ticker)
        self.peer_tickers = list(dict.fromkeys(clean_ticker(x) for x in self.peer_tickers))
        if self.target_ticker in self.peer_tickers:
            raise ValueError("Hedef şirket benzer şirket listesinde yer alamaz.")
        if not 3 <= self.historical_years <= 15 or not 3 <= self.forecast_years <= 10:
            raise ValueError("Geçmiş dönem 3-15, tahmin dönemi 3-10 yıl olmalıdır.")
        if self.valuation_date:
            date.fromisoformat(self.valuation_date)
        if len(self.base_currency) != 3:
            raise ValueError("Para birimi üç harfli olmalıdır.")
        self.base_currency = self.base_currency.upper()


@dataclass
class ForecastAssumptions:
    revenue_growth: list[float]
    ebitda_margin: list[float]
    tax_rate: float = 0.21
    depreciation_as_percent_revenue: float = 0.04
    capex_as_percent_revenue: float = 0.05
    nwc_as_percent_revenue: float = 0.03

    def validate(self, years: int) -> None:
        if len(self.revenue_growth) != years or len(self.ebitda_margin) != years:
            raise ValueError("Büyüme ve marj varsayım sayısı tahmin dönemiyle eşleşmelidir.")
        for value in self.revenue_growth:
            validate_rate("Hasılat büyümesi", value, -0.50, 1.0)
        for value in self.ebitda_margin:
            validate_rate("EBITDA marjı", value, -0.50, 1.0)
        for label, value in (("Vergi", self.tax_rate), ("D&A", self.depreciation_as_percent_revenue),
                             ("Capex", self.capex_as_percent_revenue), ("NWC", self.nwc_as_percent_revenue)):
            validate_rate(label, value, 0, 0.75)


@dataclass
class WACCAssumptions:
    risk_free_rate: float = 0.04
    equity_risk_premium: float = 0.055
    beta: float | None = None
    pre_tax_cost_of_debt: float = 0.045
    country_risk_premium: float = 0.0
    target_debt_weight: float | None = None

    def __post_init__(self) -> None:
        for label, value in (("Risksiz faiz", self.risk_free_rate), ("Hisse risk primi", self.equity_risk_premium),
                             ("Borç maliyeti", self.pre_tax_cost_of_debt), ("Ülke risk primi", self.country_risk_premium)):
            validate_rate(label, value, -0.05, 0.50)
        if self.beta is not None and not 0 < self.beta <= 5:
            raise ValueError("Beta 0 ile 5 arasında olmalıdır.")
        if self.target_debt_weight is not None:
            validate_rate("Hedef borç ağırlığı", self.target_debt_weight, 0, 0.95)


@dataclass
class TerminalAssumptions:
    terminal_growth_rate: float = 0.025
    exit_ebitda_multiple: float = 18.0

    def __post_init__(self) -> None:
        validate_rate("Terminal büyüme", self.terminal_growth_rate, -0.02, 0.06)
        if not 0 < self.exit_ebitda_multiple <= 100:
            raise ValueError("Çıkış çarpanı pozitif ve makul olmalıdır.")


@dataclass
class ComparableConfig:
    selected_multiples: list[str] = field(default_factory=lambda: ["EV/Revenue", "EV/EBITDA", "EV/EBIT", "P/E"])
    outlier_method: str = "iqr"
    outlier_threshold: float = 1.5
    use_ttm: bool = True
    manual_exclusions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        allowed = {"EV/Revenue", "EV/EBITDA", "EV/EBIT", "P/E", "P/B", "Price/Sales"}
        if not self.selected_multiples or not set(self.selected_multiples).issubset(allowed):
            raise ValueError("Geçersiz çarpan seçimi.")
        if self.outlier_method not in {"iqr", "zscore", "mad", "none"}:
            raise ValueError("Aykırı değer yöntemi iqr, zscore, mad veya none olmalıdır.")
        if self.outlier_threshold <= 0:
            raise ValueError("Aykırı değer eşiği pozitif olmalıdır.")
        self.manual_exclusions = [clean_ticker(x) for x in self.manual_exclusions]
