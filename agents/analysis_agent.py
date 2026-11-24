"""
analysis_agent.py
-----------------
Analyzes a DataFrame for:
  1. Period-over-period % change (compares two halves of the data)
  2. Z-score anomaly detection (flags values beyond 2 std deviations)

Returns a plain-English summary string.
"""

import pandas as pd
import numpy as np


def analyze_trends(df: pd.DataFrame) -> str:
    """
    Takes any DataFrame (from a query result) and returns a text summary
    with % changes and anomaly flags.
    """
    if df is None or df.empty:
        return "No data available to analyze."

    lines = ["── Trend Analysis ──────────────────────────"]

    # Find numeric columns to analyze
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if not numeric_cols:
        return "No numeric columns found to analyze."

    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 2:
            continue

        # ── Period-over-period % change ───────────────────────────────────────
        # Split into two halves: first half vs second half
        mid   = len(series) // 2
        first = series.iloc[:mid].mean()
        last  = series.iloc[mid:].mean()

        if first != 0:
            pct_change = ((last - first) / abs(first)) * 100
            direction  = "▲" if pct_change > 0 else "▼"
            lines.append(
                f"{col}: {direction} {abs(pct_change):.1f}% "
                f"(first half avg: {first:,.2f} → second half avg: {last:,.2f})"
            )

        # ── Z-score anomaly detection ─────────────────────────────────────────
        mean  = series.mean()
        std   = series.std()

        if std > 0:
            z_scores  = (series - mean) / std
            anomalies = series[z_scores.abs() > 2]

            if not anomalies.empty:
                lines.append(
                    f"  ⚠ Anomalies in {col} (z-score > 2): "
                    + ", ".join(f"{v:,.2f}" for v in anomalies.values[:5])
                )

    lines.append("────────────────────────────────────────────")
    return "\n".join(lines)
