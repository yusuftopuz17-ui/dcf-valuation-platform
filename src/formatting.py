"""Central financial formatting utilities."""

from __future__ import annotations

import math


def money(value: float, currency: str = "USD", compact: bool = False, decimals: int = 2) -> str:
    if value is None or not math.isfinite(float(value)):
        return "N/A"
    symbol = "$" if currency == "USD" else f"{currency} "
    value = float(value); sign = "-" if value < 0 else ""; absolute = abs(value)
    if compact:
        for scale, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
            if absolute >= scale:
                return f"{sign}{symbol}{absolute / scale:,.1f}{suffix}"
    return f"{sign}{symbol}{absolute:,.{decimals}f}"


def percent(value: float, decimals: int = 1) -> str:
    if value is None or not math.isfinite(float(value)):
        return "N/A"
    return f"{float(value) * 100:,.{decimals}f}%"


def multiple(value: float, decimals: int = 1) -> str:
    if value is None or not math.isfinite(float(value)):
        return "N/A"
    return f"{float(value):,.{decimals}f}x"


def ratio(value: float, decimals: int = 2) -> str:
    if value is None or not math.isfinite(float(value)):
        return "N/A"
    return f"{float(value):,.{decimals}f}"


def basis_points(value: float) -> str:
    if value is None or not math.isfinite(float(value)):
        return "N/A"
    return f"{float(value) * 10000:,.0f} bps"


def scale_label(value: float, currency: str = "USD") -> tuple[float, str]:
    maximum = abs(float(value))
    if maximum >= 1e9:
        return 1e9, f"{currency} milyar"
    if maximum >= 1e6:
        return 1e6, f"{currency} milyon"
    return 1, currency

