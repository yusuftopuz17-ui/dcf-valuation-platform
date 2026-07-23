"""Deterministic comparable-company valuation models and calculations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd


SECTOR_TAXONOMY: dict[str, list[str]] = {
    "Industrials": ["Infrastructure", "Architecture & Engineering Services", "Environmental, Energy & Field Services",
                    "Building Materials", "Security Systems & Fire Protection", "Precision Manufacturing & Metal Fabrication",
                    "Specialty Manufacturing", "Industrial Equipment Manufacturing", "Industrial Distribution", "Other"],
    "Construction & Commercial Trades": ["HVAC, Plumbing & Electrical Services", "Roofing & Exterior Services",
                                           "Lawn, Landscape & Outdoor Services", "Building Materials", "Other"],
    "Manufacturing": ["Precision Manufacturing & Metal Fabrication", "Industrial Equipment Manufacturing",
                      "Specialty Manufacturing", "Other"],
    "Consumer": ["Consumer Products", "Food & Beverage", "Automotive", "Other"],
    "Healthcare": ["Healthcare Clinics & Practices", "Behavioral Health Services", "Home Health Services",
                   "Medical Equipment & Devices", "Other"],
    "Technology": ["Software", "Managed IT Services", "IT Solutions", "Other"],
    "Business Services": ["Professional & Business Support Services", "Financial Services & Insurance",
                          "Education, Training & Workforce Services", "Digital Marketing & Advertising",
                          "Media & Print Services", "Security Systems & Fire Protection", "Other"],
    "Transportation & Logistics": ["Transportation, Logistics & Freight", "Automotive", "Industrial Distribution", "Other"],
    "Residential Trades": ["Home Improvement", "Lawn, Landscape & Outdoor Services",
                            "HVAC, Plumbing & Electrical Services", "Roofing & Exterior Services", "Other"],
    "Energy & Environment": ["Environmental, Energy & Field Services", "Infrastructure",
                             "Architecture & Engineering Services", "Other"],
    "Other": ["Other"],
}

DEFAULT_WEIGHTS = {
    "Sector": .15, "Subsector": .20, "Business Model": .15, "Customer Structure": .10,
    "Geography": .10, "Company Size": .10, "Growth": .075, "Profitability": .075, "Revenue Model": .05,
}
MULTIPLES = ["EV/Revenue", "EV/EBITDA", "EV/EBIT", "P/E"]
BOUNDARY_FIELDS = [
    "Revenue", "EBITDA", "Market Cap", "Enterprise Value", "Revenue Growth", "EBITDA Margin", "Employees",
]
UNIT_FACTORS = {"actual": 1.0, "thousands": 1_000.0, "millions": 1_000_000.0, "billions": 1_000_000_000.0}


@dataclass
class ValuationProject:
    """Typed, session-serializable valuation project."""

    project_id: str = field(default_factory=lambda: str(uuid4()))
    project_name: str = "Yeni Değerleme"
    selected_method: str | None = None
    company_type: str | None = None
    active_ccv_page: str = "Kurulum"
    target_identity: dict[str, Any] = field(default_factory=dict)
    private_profile: dict[str, Any] = field(default_factory=dict)
    public_identifier: dict[str, Any] = field(default_factory=dict)
    financial_inputs: dict[str, Any] = field(default_factory=dict)
    boundaries: dict[str, Any] = field(default_factory=dict)
    similarity_weights: dict[str, float] = field(default_factory=lambda: DEFAULT_WEIGHTS.copy())
    candidate_tickers: list[str] = field(default_factory=list)
    included_peers: list[str] = field(default_factory=list)
    excluded_peers: list[str] = field(default_factory=list)
    locked_peers: list[str] = field(default_factory=list)
    outlier_settings: dict[str, Any] = field(default_factory=lambda: {"method": "IQR", "threshold": 1.5})
    manual_overrides: dict[str, Any] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        self.updated_at = datetime.now(UTC).isoformat()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ValuationProject":
        if not payload:
            return cls()
        accepted = {name for name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in payload.items() if key in accepted})


def normalize_value(value: float | int | None, unit: str = "actual") -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    if unit not in UNIT_FACTORS:
        raise ValueError(f"Geçersiz birim: {unit}")
    return float(value) * UNIT_FACTORS[unit]


def validate_weights(weights: dict[str, float]) -> None:
    missing = set(DEFAULT_WEIGHTS) - set(weights)
    if missing:
        raise ValueError(f"Eksik benzerlik ağırlıkları: {', '.join(sorted(missing))}")
    if any(not np.isfinite(value) or value < 0 for value in weights.values()):
        raise ValueError("Benzerlik ağırlıkları negatif veya geçersiz olamaz.")
    if not np.isclose(sum(weights.values()), 1.0, atol=1e-6):
        raise ValueError("Benzerlik ağırlıklarının toplamı %100 olmalıdır.")


def validate_boundaries(boundaries: dict[str, Any]) -> None:
    for field in BOUNDARY_FIELDS:
        minimum, maximum = boundaries.get(f"min_{field}"), boundaries.get(f"max_{field}")
        if minimum is not None and maximum is not None and np.isfinite(minimum) and np.isfinite(maximum) and minimum > maximum:
            raise ValueError(f"{field}: minimum değer maksimum değerden büyük olamaz.")


def enterprise_value(market_cap: float, debt: float = 0, preferred: float = 0, nci: float = 0, cash: float = 0) -> float:
    values = [market_cap, debt, preferred, nci, cash]
    if not all(np.isfinite(value) for value in values):
        return np.nan
    return float(market_cap + debt + preferred + nci - cash)


def calculate_multiples(companies: pd.DataFrame) -> pd.DataFrame:
    """Calculate period-consistent multiples; non-meaningful values remain NaN/N/M."""
    out = companies.copy()
    numeric = ["Market Cap", "Enterprise Value", "Revenue", "EBITDA", "EBIT", "Net Income"]
    for column in numeric:
        out[column] = pd.to_numeric(out.get(column), errors="coerce")
    out["EV/Revenue"] = np.where(out["Revenue"] > 0, out["Enterprise Value"] / out["Revenue"], np.nan)
    out["EV/EBITDA"] = np.where(out["EBITDA"] > 0, out["Enterprise Value"] / out["EBITDA"], np.nan)
    out["EV/EBIT"] = np.where(out["EBIT"] > 0, out["Enterprise Value"] / out["EBIT"], np.nan)
    out["P/E"] = np.where(out["Net Income"] > 0, out["Market Cap"] / out["Net Income"], np.nan)
    return out


def _tokens(value: Any) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        values = value
    elif value is None or (isinstance(value, float) and np.isnan(value)):
        values = []
    else:
        values = str(value).replace(";", ",").split(",")
    return {str(item).strip().casefold() for item in values if str(item).strip()}


def _overlap(target: Any, candidate: Any) -> float:
    left, right = _tokens(target), _tokens(candidate)
    if not left or not right:
        return .5
    return len(left & right) / len(left | right)


def _categorical(target: Any, candidate: Any) -> float:
    left, right = str(target or "").strip().casefold(), str(candidate or "").strip().casefold()
    if not left or not right or left in {"bilinmiyor", "unknown"} or right in {"bilinmiyor", "unknown"}:
        return .5
    return 1.0 if left == right else (0.6 if left in right or right in left else 0.0)


def _numeric_similarity(target: Any, candidate: Any, floor: float = 1e-9) -> float:
    try:
        left, right = float(target), float(candidate)
    except (TypeError, ValueError):
        return .5
    if not np.isfinite(left) or not np.isfinite(right):
        return .5
    scale = max(abs(left), abs(right), floor)
    return float(np.clip(1 - abs(left - right) / scale, 0, 1))


def similarity_scores(target: dict[str, Any], candidates: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.DataFrame:
    """Return transparent, reproducible peer scores with component detail."""
    weights = weights or DEFAULT_WEIGHTS
    validate_weights(weights)
    rows = []
    for ticker, candidate in candidates.iterrows():
        components = {
            "Sector": _categorical(target.get("Sector"), candidate.get("Sector")),
            "Subsector": _categorical(target.get("Subsector"), candidate.get("Subsector")),
            "Business Model": _overlap(target.get("Business Model"), candidate.get("Business Model")),
            "Customer Structure": _overlap(target.get("Customer Structure"), candidate.get("Customer Structure")),
            "Geography": _overlap(target.get("Geography"), [candidate.get("Country")]),
            "Company Size": _numeric_similarity(target.get("Revenue"), candidate.get("Revenue")),
            "Growth": _numeric_similarity(target.get("Revenue Growth"), candidate.get("Revenue Growth")),
            "Profitability": _numeric_similarity(target.get("EBITDA Margin"), candidate.get("EBITDA Margin")),
            "Revenue Model": _overlap(target.get("Revenue Model"), candidate.get("Revenue Model")),
        }
        score = sum(weights[name] * value for name, value in components.items())
        strongest = sorted(components, key=components.get, reverse=True)[:3]
        rows.append({"Ticker": ticker, "Similarity Score": score,
                     "Selection Reason": "En güçlü eşleşmeler: " + ", ".join(strongest),
                     **{f"Score · {key}": value for key, value in components.items()}})
    return pd.DataFrame(rows).set_index("Ticker").sort_values("Similarity Score", ascending=False)


def apply_boundaries(candidates: pd.DataFrame, boundaries: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    validate_boundaries(boundaries)
    accepted = pd.Series(True, index=candidates.index)
    reasons: dict[str, list[str]] = {str(index): [] for index in candidates.index}
    for field in BOUNDARY_FIELDS:
        if field not in candidates:
            continue
        values = pd.to_numeric(candidates[field], errors="coerce")
        minimum, maximum = boundaries.get(f"min_{field}"), boundaries.get(f"max_{field}")
        boundary_currency = boundaries.get(f"currency_{field}")
        if field in {"Revenue", "EBITDA", "Market Cap", "Enterprise Value"} and boundary_currency and (minimum is not None or maximum is not None):
            currency_mismatch = candidates.get("Currency", pd.Series(index=candidates.index, dtype=object)).astype(str).ne(boundary_currency)
            accepted &= ~currency_mismatch
            for index in candidates.index[currency_mismatch]:
                reasons[str(index)].append(f"{field} sınırı {boundary_currency}; aday para birimi farklı ve FX dönüşümü uygulanmadı")
        if minimum is not None and np.isfinite(minimum):
            failed = values.isna() | (values < minimum)
            accepted &= ~failed
            for index in candidates.index[failed]:
                reasons[str(index)].append(f"{field} minimum sınırının altında veya veri yok")
        if maximum is not None and np.isfinite(maximum):
            failed = values.isna() | (values > maximum)
            accepted &= ~failed
            for index in candidates.index[failed]:
                reasons[str(index)].append(f"{field} maksimum sınırının üzerinde veya veri yok")
    rejected = candidates.loc[~accepted].copy()
    if not rejected.empty:
        rejected["Rejection Reason"] = ["; ".join(reasons[str(index)]) for index in rejected.index]
    return candidates.loc[accepted].copy(), rejected


def rank_peers(target: dict[str, Any], candidates: pd.DataFrame, boundaries: dict[str, Any],
               weights: dict[str, float], target_count: int, minimum_score: float,
               include: list[str] | None = None, exclude: list[str] | None = None,
               locked: list[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    filtered, rejected = apply_boundaries(candidates, boundaries)
    scored = filtered.join(similarity_scores(target, filtered, weights))
    include_set = {x.upper() for x in (include or [])}; exclude_set = {x.upper() for x in (exclude or [])}
    locked_set = {x.upper() for x in (locked or [])}
    scored["Manual Status"] = np.where(scored.index.isin(locked_set), "Locked",
                               np.where(scored.index.isin(include_set), "Included", "Automatic"))
    low_score = (scored["Similarity Score"] < minimum_score) & ~scored.index.isin(include_set | locked_set)
    low = scored.loc[low_score].copy()
    if not low.empty:
        low["Rejection Reason"] = f"Benzerlik puanı %{minimum_score * 100:.0f} eşiğinin altında"
        rejected = pd.concat([rejected, low], axis=0)
    scored = scored.loc[~low_score & ~scored.index.isin(exclude_set)]
    excluded_rows = filtered.loc[filtered.index.intersection(exclude_set)].copy()
    if not excluded_rows.empty:
        excluded_rows["Rejection Reason"] = "Kullanıcı tarafından hariç tutuldu"
        rejected = pd.concat([rejected, excluded_rows], axis=0)
    forced = scored.loc[scored.index.isin(include_set | locked_set)]
    automatic = scored.loc[~scored.index.isin(include_set | locked_set)].head(max(target_count - len(forced), 0))
    selected = pd.concat([forced, automatic]).loc[lambda x: ~x.index.duplicated()]
    return selected.sort_values(["Manual Status", "Similarity Score"], ascending=[True, False]), rejected.loc[lambda x: ~x.index.duplicated()]


def clean_outliers(peers: pd.DataFrame, method: str = "IQR", threshold: float = 1.5) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Apply selected method independently to every multiple."""
    clean, audit, summaries = peers.copy(), [], []
    for multiple in MULTIPLES:
        series = pd.to_numeric(peers.get(multiple), errors="coerce")
        valid = series.dropna()
        q1, median, q3 = valid.quantile(.25), valid.median(), valid.quantile(.75)
        iqr = q3 - q1
        lower, upper = -np.inf, np.inf
        excluded = pd.Series(False, index=series.index)
        method_key = method.casefold()
        if method_key == "iqr" and len(valid) >= 4:
            lower, upper = q1 - threshold * iqr, q3 + threshold * iqr
            excluded = (series < lower) | (series > upper)
        elif method_key in {"z-score", "zscore"} and len(valid) >= 3 and valid.std(ddof=0) > 0:
            excluded = ((series - valid.mean()) / valid.std(ddof=0)).abs() > threshold
        elif method_key == "winsorization" and len(valid) >= 4:
            lower, upper = valid.quantile(.05), valid.quantile(.95)
            clean[multiple] = series.clip(lower, upper)
        for ticker in series.index[excluded.fillna(False)]:
            audit.append({"Ticker": ticker, "Multiple": multiple, "Original": series.loc[ticker],
                          "Cleaned": np.nan, "Reason": f"{method} eşiği dışında"})
            clean.loc[ticker, multiple] = np.nan
        summaries.append({"Multiple": multiple, "Original Observations": len(valid), "Q1": q1, "Median": median,
                          "Q3": q3, "IQR": iqr, "Lower Bound": lower, "Upper Bound": upper,
                          "Excluded": int(excluded.sum()), "Cleaned Observations": int(clean[multiple].notna().sum())})
    return clean, pd.DataFrame(audit), pd.DataFrame(summaries).set_index("Multiple")


def summary_statistics(clean_peers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for multiple in MULTIPLES:
        values = pd.to_numeric(clean_peers.get(multiple), errors="coerce").dropna()
        rows.append({"Multiple": multiple, "Minimum": values.min(), "25th Percentile": values.quantile(.25),
                     "Mean": values.mean(), "Median": values.median(), "75th Percentile": values.quantile(.75),
                     "Maximum": values.max(), "Valid Observations": len(values),
                     "Confidence": "High" if len(values) >= 6 else ("Medium" if len(values) >= 4 else "Low")})
    return pd.DataFrame(rows).set_index("Multiple")


def implied_valuations(summary: pd.DataFrame, target: dict[str, Any], bridge: dict[str, Any]) -> pd.DataFrame:
    metric_map = {"EV/Revenue": "Revenue", "EV/EBITDA": "EBITDA", "EV/EBIT": "EBIT", "P/E": "Net Income"}
    rows = []
    cash, debt = bridge.get("Cash"), bridge.get("Debt")
    preferred, nci = bridge.get("Preferred Equity", 0), bridge.get("Non-Controlling Interest", 0)
    nonop, debt_like = bridge.get("Other Non-operating Assets", 0), bridge.get("Debt-like Liabilities", 0)
    can_bridge = all(value is not None and np.isfinite(value) for value in [cash, debt, preferred, nci, nonop, debt_like])
    shares = target.get("Diluted Shares")
    for multiple, metric in metric_map.items():
        target_metric = target.get(metric)
        if target_metric is None or not np.isfinite(target_metric) or target_metric <= 0:
            continue
        for statistic in ["25th Percentile", "Median", "75th Percentile"]:
            selected = summary.loc[multiple, statistic]
            if not np.isfinite(selected):
                continue
            if multiple == "P/E":
                equity, ev = selected * target_metric, np.nan
            else:
                ev = selected * target_metric
                equity = ev + cash - debt - preferred - nci + nonop - debt_like if can_bridge else np.nan
            per_share = equity / shares if np.isfinite(equity) and shares is not None and np.isfinite(shares) and shares > 0 else np.nan
            rows.append({"Multiple": multiple, "Statistic": statistic, "Selected Multiple": selected,
                         "Target Metric": target_metric, "Implied Enterprise Value": ev,
                         "Implied Equity Value": equity, "Implied Value Per Share": per_share,
                         "Bridge Available": can_bridge or multiple == "P/E"})
    return pd.DataFrame(rows)


def confidence_assessment(peers: pd.DataFrame, summary: pd.DataFrame, target: dict[str, Any],
                          relaxed_filters: int = 0) -> dict[str, Any]:
    count = len(peers)
    similarity = pd.to_numeric(peers.get("Similarity Score"), errors="coerce").mean()
    completeness = np.mean([target.get(key) is not None and np.isfinite(target.get(key))
                            for key in ["Revenue", "EBITDA", "EBIT", "Net Income"]])
    valid_multiples = int((summary["Valid Observations"] >= 3).sum())
    score = min(count / 8, 1) * .30 + (similarity if np.isfinite(similarity) else .3) * .25 + completeness * .20 + min(valid_multiples / 4, 1) * .20 + max(0, 1 - relaxed_filters / 3) * .05
    level = "High" if score >= .75 else ("Medium" if score >= .50 else "Low")
    return {"Level": level, "Score": float(score), "Peer Count": count,
            "Average Similarity": float(similarity) if np.isfinite(similarity) else np.nan,
            "Target Completeness": float(completeness), "Valid Multiples": valid_multiples,
            "Relaxed Filters": relaxed_filters,
            "Explanation": f"{count} benzer şirket, %{similarity*100:.0f} ortalama benzerlik ve {valid_multiples} kullanılabilir çarpan." if np.isfinite(similarity) else f"{count} benzer şirket; benzerlik verisi sınırlı."}


def run_ccv(target: dict[str, Any], candidates: pd.DataFrame, project: ValuationProject,
            bridge: dict[str, Any]) -> dict[str, Any]:
    """Run the complete deterministic CCV analysis."""
    multiples = calculate_multiples(candidates)
    selected, rejected = rank_peers(target, multiples, project.boundaries, project.similarity_weights,
                                    int(project.manual_overrides.get("target_peer_count", 8)),
                                    float(project.manual_overrides.get("minimum_similarity", .35)),
                                    project.included_peers, project.excluded_peers, project.locked_peers)
    clean, outlier_audit, outlier_summary = clean_outliers(
        selected, project.outlier_settings.get("method", "IQR"),
        float(project.outlier_settings.get("threshold", 1.5)),
    )
    stats = summary_statistics(clean)
    implied = implied_valuations(stats, target, bridge)
    confidence = confidence_assessment(selected, stats, target)
    if len(selected) < 3:
        confidence["Warning"] = "Benzer şirket örneklemi üçten az; istatistikler düşük güven düzeyindedir. Sınırları genişletmek için kullanıcı onayı gerekir."
    return {"target": target, "candidates": multiples, "selected_peers": selected, "rejected_candidates": rejected,
            "clean_peers": clean, "outlier_audit": outlier_audit, "outlier_summary": outlier_summary,
            "summary_statistics": stats, "implied_valuations": implied, "confidence": confidence,
            "bridge": bridge, "project": project.to_dict(), "generated_at": datetime.now(UTC).isoformat()}
