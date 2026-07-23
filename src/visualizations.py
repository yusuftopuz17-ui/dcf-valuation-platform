"""Reusable institutional Plotly visualizations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


COLORS = {"bg": "#050607", "panel": "#111419", "grid": "#252B33", "text": "#F4F6F8",
          "muted": "#A7B0BC", "teal": "#28C7B7", "green": "#36C98F", "amber": "#E5AA4F",
          "red": "#EF6268", "blue": "#5F8FE8", "purple": "#8979E6"}


def layout(fig: go.Figure, title: str, height: int = 430, y_format: str | None = None) -> go.Figure:
    fig.update_layout(title={"text": title, "x": 0.01, "font": {"size": 18}}, template="plotly_dark",
                      paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"], font={"family": "Inter, sans-serif", "color": COLORS["text"]},
                      height=height, margin={"l": 48, "r": 24, "t": 62, "b": 48}, hoverlabel={"bgcolor": "#151A20"},
                      legend={"orientation": "h", "y": 1.08, "x": 1, "xanchor": "right"})
    fig.update_xaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"])
    fig.update_yaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"], tickformat=y_format)
    return fig


def revenue_ebitda(financials: pd.DataFrame) -> go.Figure:
    years = financials.index.year.astype(str); scale = 1e9
    fig = go.Figure([go.Bar(x=years, y=financials["Revenue"] / scale, name="Hasılat", marker_color=COLORS["blue"]),
                     go.Scatter(x=years, y=financials["EBITDA"] / scale, name="EBITDA", mode="lines+markers", line={"color": COLORS["teal"], "width": 3})])
    return layout(fig, "Tarihsel Hasılat ve EBITDA (milyar)")


def historical_forecast(financials: pd.DataFrame, model: pd.DataFrame) -> go.Figure:
    years = list(financials.index.year.astype(str)) + list(model.index.astype(str))
    values = np.r_[financials["Revenue"], model["Revenue"]] / 1e9
    fig = go.Figure(go.Scatter(x=years, y=values, mode="lines+markers", line={"color": COLORS["teal"], "width": 3}, fill="tozeroy", fillcolor="rgba(40,199,183,.08)"))
    fig.add_vline(x=len(financials) - .5, line_dash="dash", line_color=COLORS["amber"], annotation_text="Tahmin başlangıcı")
    return layout(fig, "Tarihsel ve Tahmini Hasılat (milyar)")


def margin_chart(metrics: pd.DataFrame, model: pd.DataFrame) -> go.Figure:
    years = list(metrics.index.year.astype(str)) + list(model.index.astype(str))
    fig = go.Figure()
    fig.add_scatter(x=years, y=np.r_[metrics["EBITDA Margin"], model["EBITDA Margin"]], name="EBITDA Marjı", mode="lines+markers", line={"color": COLORS["teal"], "width": 3})
    fig.add_scatter(x=metrics.index.year.astype(str), y=metrics["EBIT Margin"], name="EBIT Marjı", mode="lines+markers", line={"color": COLORS["purple"]})
    return layout(fig, "Marj Gelişimi", y_format=".1%")


def fcf_bridge(model: pd.DataFrame) -> go.Figure:
    row = model.iloc[-1]
    values = [row["EBIT"], -row["EBIT"] * row["Tax Rate"], row["D&A"], -row["Capex"], -row["Change in NWC"], row["UFCF"]]
    fig = go.Figure(go.Waterfall(x=["EBIT", "Vergi", "D&A", "Capex", "NWC Değişimi", "UFCF"], y=np.asarray(values) / 1e9,
                                 measure=["relative"] * 5 + ["total"], connector={"line": {"color": COLORS["grid"]}},
                                 increasing={"marker": {"color": COLORS["green"]}}, decreasing={"marker": {"color": COLORS["red"]}}, totals={"marker": {"color": COLORS["teal"]}}))
    return layout(fig, "Son Tahmin Yılı UFCF Köprüsü (milyar)")


def bridge_chart(bridge: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Waterfall(x=bridge["Item"], y=bridge["Value"] / 1e9, measure=["absolute", "relative", "relative", "total"],
                                 increasing={"marker": {"color": COLORS["green"]}}, decreasing={"marker": {"color": COLORS["red"]}},
                                 totals={"marker": {"color": COLORS["teal"]}}))
    return layout(fig, "İşletme Değerinden Özsermaye Değerine Köprü (milyar)")


def valuation_comparison(results: dict) -> go.Figure:
    labels = ["DCF - Sürekli Büyüme", "DCF - Çıkış Çarpanı", "Benzer Şirketler", "Harmanlanmış"]
    values = [results["dcf_pg"]["Implied Price"], results["dcf_exit"]["Implied Price"], results["peer_median_price"], results["blended_value"]]
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=[COLORS["teal"], COLORS["purple"], COLORS["blue"], COLORS["amber"]], text=[f"${x:,.2f}" for x in values], textposition="outside"))
    fig.add_hline(y=results["market"]["Current Price"], line_dash="dash", line_color=COLORS["red"], annotation_text="Mevcut fiyat")
    return layout(fig, "Değerleme Yöntemleri Karşılaştırması", y_format="$,.0f")


def heatmap(table: pd.DataFrame, title: str, current_price: float) -> go.Figure:
    x = [f"{v:.1%}" if "Growth" in str(table.columns.name) else f"{v:.1f}x" for v in table.columns]
    y = [f"{v:.1%}" for v in table.index]
    fig = go.Figure(go.Heatmap(z=table.to_numpy(), x=x, y=y, colorscale=[[0, "#51252A"], [.5, "#463D2A"], [1, "#1E5A4A"]],
                               zmid=current_price, text=np.vectorize(lambda v: f"${v:,.0f}")(table.to_numpy()), texttemplate="%{text}",
                               hovertemplate="%{y} / %{x}<br>Hisse Değeri: $%{z:,.2f}<extra></extra>", colorbar={"title": "Hisse değeri"}))
    return layout(fig, title, 500)


def peer_heatmap(peers: pd.DataFrame) -> go.Figure:
    cols = ["EV/Revenue", "EV/EBITDA", "EV/EBIT", "P/E"]
    normalized = peers[cols].apply(lambda x: (x - x.median()) / (x.std(ddof=0) or 1))
    fig = go.Figure(go.Heatmap(z=normalized.to_numpy(), x=cols, y=normalized.index, colorscale="RdYlGn_r", zmid=0,
                               text=np.vectorize(lambda v: f"{v:.1f}")(peers[cols].to_numpy()), texttemplate="%{text}x"))
    return layout(fig, "Benzer Şirket Çarpanları", 440)


def peer_scatter(peers: pd.DataFrame, x: str, y: str, title: str) -> go.Figure:
    fig = go.Figure(go.Scatter(x=peers[x], y=peers[y], mode="markers+text", text=peers.index, textposition="top center",
                               marker={"size": 13, "color": COLORS["teal"], "line": {"width": 1, "color": COLORS["text"]}},
                               hovertemplate="%{text}<br>%{x:.1%}<br>%{y:.1f}x<extra></extra>"))
    return layout(fig, title)


def football_field(football: pd.DataFrame, current: float | None = None, blended: float | None = None) -> go.Figure:
    frame = football.sort_values("Median")
    fig = go.Figure()
    for _, row in frame.iterrows():
        fig.add_trace(go.Scatter(x=[row["Low"], row["High"]], y=[row["Method"]] * 2, mode="lines",
                                 line={"color": COLORS["blue"], "width": 12}, hovertemplate=f"{row['Method']}<br>Düşük: $%{{x:,.2f}}<extra></extra>", showlegend=False))
        fig.add_trace(go.Scatter(x=[row["Median"]], y=[row["Method"]], mode="markers", marker={"color": COLORS["text"], "size": 9}, showlegend=False,
                                 hovertemplate="Medyan: $%{x:,.2f}<extra></extra>"))
    if current is not None and np.isfinite(current):
        fig.add_vline(x=current, line_dash="dash", line_color=COLORS["red"], annotation_text="Mevcut fiyat")
    if blended is not None and np.isfinite(blended):
        fig.add_vline(x=blended, line_dash="dot", line_color=COLORS["teal"], annotation_text="Harmanlanmış değer")
    return layout(fig, "Football-Field Değerleme", 500, "$,.0f")


def scenarios_chart(scenarios: pd.DataFrame, current: float) -> go.Figure:
    fig = go.Figure(go.Bar(x=scenarios["Scenario"], y=scenarios["Implied Price"], marker_color=[COLORS["red"], COLORS["blue"], COLORS["green"]],
                           text=[f"${v:,.2f}" for v in scenarios["Implied Price"]], textposition="outside"))
    fig.add_hline(y=current, line_dash="dash", line_color=COLORS["amber"], annotation_text="Mevcut fiyat")
    return layout(fig, "Ayı, Baz ve Boğa Senaryoları", y_format="$,.0f")
