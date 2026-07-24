"""Reusable professional-analysis utilities for the public valuation tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd


SIMILARITY_CRITERIA = (
    "Sector",
    "Sub-sector / Business Model",
    "Geography",
    "Customer Base",
    "Revenue Model",
    "Growth Profile",
    "Profitability / Margin Profile",
    "Company Size",
)

DEFAULT_SIMILARITY_WEIGHTS = {
    "Sector": 0.15,
    "Sub-sector / Business Model": 0.20,
    "Geography": 0.10,
    "Customer Base": 0.10,
    "Revenue Model": 0.10,
    "Growth Profile": 0.12,
    "Profitability / Margin Profile": 0.13,
    "Company Size": 0.10,
}

MULTIPLE_LIMITS = {
    "EV/EBITDA": 250.0,
    "P/E": 500.0,
    "P/S": 100.0,
    "P/B": 100.0,
}


def validate_similarity_weights(weights: Mapping[str, float]) -> None:
    """Require complete, finite, non-negative weights that total exactly 100%."""
    missing = set(SIMILARITY_CRITERIA) - set(weights)
    if missing:
        raise ValueError(f"Missing similarity weights: {', '.join(sorted(missing))}.")
    values = np.asarray([weights[name] for name in SIMILARITY_CRITERIA], dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Similarity weights must be finite and non-negative.")
    if not np.isclose(values.sum(), 1.0, atol=1e-6):
        raise ValueError("Similarity weights must total 100%.")


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip() or value.strip().casefold() in {
            "unknown", "data unavailable", "not available", "mevcut değil", "bilinmiyor",
        }
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _tokens(value: Any) -> set[str]:
    if _missing(value):
        return set()
    values = value if isinstance(value, (list, tuple, set)) else str(value).replace(";", ",").split(",")
    return {str(item).strip().casefold() for item in values if str(item).strip()}


def _categorical_similarity(left: Any, right: Any) -> float:
    if _missing(left) or _missing(right):
        return np.nan
    a, b = str(left).strip().casefold(), str(right).strip().casefold()
    if a == b:
        return 1.0
    return 0.6 if a in b or b in a else 0.0


def _overlap_similarity(left: Any, right: Any) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return np.nan
    return len(a & b) / len(a | b)


def _numeric_similarity(left: Any, right: Any, floor: float) -> float:
    try:
        a, b = float(left), float(right)
    except (TypeError, ValueError):
        return np.nan
    if not np.isfinite(a) or not np.isfinite(b):
        return np.nan
    scale = max(abs(a), abs(b), floor)
    return float(np.clip(1.0 - abs(a - b) / scale, 0.0, 1.0))


def _size_similarity(left: Any, right: Any) -> float:
    try:
        a, b = float(left), float(right)
    except (TypeError, ValueError):
        return np.nan
    if not np.isfinite(a) or not np.isfinite(b) or a <= 0 or b <= 0:
        return np.nan
    return float(np.exp(-abs(np.log(a / b))))


def comparable_similarity(
    target: Mapping[str, Any],
    peers: pd.DataFrame,
    weights: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """Score peers transparently and renormalize only across available criteria.

    Missing provider fields stay missing. They are excluded from the denominator
    for that peer rather than being replaced with neutral or synthetic values.
    """
    weights = dict(weights or DEFAULT_SIMILARITY_WEIGHTS)
    validate_similarity_weights(weights)
    rows: list[dict[str, Any]] = []
    for ticker, peer in peers.iterrows():
        subsector = _categorical_similarity(target.get("Subsector"), peer.get("Subsector"))
        business_model = _overlap_similarity(target.get("Business Model"), peer.get("Business Model"))
        if np.isfinite(subsector) and np.isfinite(business_model):
            sub_business = 0.7 * subsector + 0.3 * business_model
        else:
            sub_business = subsector if np.isfinite(subsector) else business_model
        scores = {
            "Sector": _categorical_similarity(target.get("Sector"), peer.get("Sector")),
            "Sub-sector / Business Model": sub_business,
            "Geography": _overlap_similarity(target.get("Geography"), [peer.get("Country")]),
            "Customer Base": _overlap_similarity(
                target.get("Customer Structure"), peer.get("Customer Structure")
            ),
            "Revenue Model": _overlap_similarity(target.get("Revenue Model"), peer.get("Revenue Model")),
            "Growth Profile": _numeric_similarity(
                target.get("Revenue Growth"), peer.get("Revenue Growth"), 0.05
            ),
            "Profitability / Margin Profile": _numeric_similarity(
                target.get("EBITDA Margin"), peer.get("EBITDA Margin"), 0.05
            ),
            "Company Size": _size_similarity(target.get("Revenue"), peer.get("Revenue")),
        }
        available_weight = sum(weights[name] for name, score in scores.items() if np.isfinite(score))
        weighted_total = sum(
            weights[name] * score for name, score in scores.items() if np.isfinite(score)
        )
        overall = weighted_total / available_weight if available_weight > 0 else np.nan
        row: dict[str, Any] = {
            "Ticker": ticker,
            "Comparable Company": peer.get("Company", ticker),
            "Weighted Total": weighted_total,
            "Available Weight": available_weight,
            "Overall Similarity": overall,
        }
        for name in SIMILARITY_CRITERIA:
            row[f"{name} Score"] = scores[name]
            row[f"{name} Weight"] = weights[name]
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows).sort_values(
        ["Overall Similarity", "Ticker"], ascending=[False, True], na_position="last"
    )
    result.insert(0, "Similarity Rank", np.arange(1, len(result) + 1))
    return result.set_index("Ticker")


def peer_multiple_statistics(peers: pd.DataFrame) -> pd.DataFrame:
    """Return quartiles, median, mean, observation count, and IQR outlier count."""
    rows = []
    for multiple, ceiling in MULTIPLE_LIMITS.items():
        values = pd.to_numeric(peers.get(multiple), errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        ).dropna()
        values = values[(values > 0) & (values <= ceiling)]
        if values.empty:
            continue
        q1, median, q3 = values.quantile([0.25, 0.50, 0.75])
        iqr = q3 - q1
        outliers = ((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum()
        rows.append({
            "Multiple": multiple,
            "25th Percentile": q1,
            "Median": median,
            "Mean": values.mean(),
            "75th Percentile": q3,
            "Observations": int(values.size),
            "Outliers": int(outliers),
        })
    return pd.DataFrame(rows).set_index("Multiple") if rows else pd.DataFrame()


def identify_multiple_outliers(peers: pd.DataFrame) -> pd.DataFrame:
    """Identify extreme peer multiples using the standard 1.5×IQR rule."""
    rows = []
    for multiple, ceiling in MULTIPLE_LIMITS.items():
        values = pd.to_numeric(peers.get(multiple), errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        ).dropna()
        valid = values[(values > 0) & (values <= ceiling)]
        if len(valid) < 4:
            continue
        q1, q3 = valid.quantile([0.25, 0.75])
        iqr = q3 - q1
        mask = (valid < q1 - 1.5 * iqr) | (valid > q3 + 1.5 * iqr)
        for ticker, value in valid.loc[mask].items():
            rows.append({
                "Comparable Company": peers.loc[ticker].get("Company", ticker),
                "Ticker": ticker,
                "Multiple": multiple,
                "Observed Value": value,
                "Reason": "Outside the 1.5×IQR range",
            })
    return pd.DataFrame(rows)


def football_field_ranges(
    sensitivity: pd.DataFrame,
    base_wacc: float,
    base_terminal_growth: float,
    comparable_prices: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build like-for-like implied-share-price ranges for a football field."""
    rows: list[dict[str, Any]] = []
    if not sensitivity.empty:
        wacc_index = np.asarray(sensitivity.index, dtype=float)
        terminal_columns = np.asarray(sensitivity.columns, dtype=float)
        base_terminal = sensitivity.columns[np.argmin(abs(terminal_columns - base_terminal_growth))]
        base_rate = sensitivity.index[np.argmin(abs(wacc_index - base_wacc))]
        wacc_values = pd.to_numeric(sensitivity[base_terminal], errors="coerce").dropna()
        terminal_values = pd.to_numeric(sensitivity.loc[base_rate], errors="coerce").dropna()
        for method, values, methodology in (
            ("DCF — WACC Sensitivity", wacc_values, "Terminal growth held at the base assumption"),
            ("DCF — Terminal Growth Sensitivity", terminal_values, "WACC held at the base assumption"),
        ):
            if not values.empty:
                rows.append({
                    "Method": method,
                    "Low": values.min(),
                    "Midpoint": values.median(),
                    "High": values.max(),
                    "Methodology": methodology,
                })
    if comparable_prices is not None and not comparable_prices.empty:
        for multiple, label in (
            ("EV/Revenue", "Trading Comparables — EV/Revenue"),
            ("EV/EBITDA", "Trading Comparables — EV/EBITDA"),
        ):
            if multiple not in comparable_prices.index:
                continue
            row = comparable_prices.loc[multiple]
            candidates = [
                row.get("Implied Price at 25th Percentile"),
                row.get("Implied Price"),
                row.get("Implied Price at 75th Percentile"),
            ]
            values = np.asarray(candidates, dtype=float)
            if np.isfinite(values).all():
                rows.append({
                    "Method": label,
                    "Low": values[0],
                    "Midpoint": values[1],
                    "High": values[2],
                    "Methodology": "Applied peer trading multiples to target fundamentals",
                })
    return pd.DataFrame(rows)
