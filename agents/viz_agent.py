"""
viz_agent.py
------------
Generates a chart image from a DataFrame and saves it to /output.
Supports bar, line, and pie charts.
Returns the file path of the saved image.
"""

import uuid
import logging
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")          # non-interactive backend (safe for Streamlit)
import matplotlib.pyplot as plt

BASE_DIR   = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)


def make_chart(
    df:         pd.DataFrame,
    question:   str = "",
    chart_type: str = "bar",
) -> str:
    """
    Creates a chart from df and saves it as a PNG.

    Args:
        df:         DataFrame with at least one text column and one numeric column
        question:   Used as the chart title
        chart_type: "bar", "line", or "pie"

    Returns:
        Absolute path to the saved PNG file.
    """
    if df is None or df.empty:
        raise ValueError("Cannot make a chart from empty data.")

    # Identify label column (first text column) and value column (first numeric)
    text_cols    = df.select_dtypes(include=["object"]).columns.tolist()
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if not numeric_cols:
        raise ValueError("No numeric column found to chart.")

    label_col = text_cols[0] if text_cols else df.columns[0]
    value_col = numeric_cols[0]

    labels = df[label_col].astype(str).tolist()
    values = df[value_col].tolist()

    fig, ax = plt.subplots(figsize=(10, 5))

    if chart_type == "bar":
        bars = ax.bar(labels, values, color="#4A90D9", edgecolor="white")
        ax.bar_label(bars, fmt="%.0f", padding=3, fontsize=8)
        plt.xticks(rotation=30, ha="right", fontsize=9)

    elif chart_type == "line":
        ax.plot(labels, values, marker="o", color="#4A90D9", linewidth=2)
        plt.xticks(rotation=30, ha="right", fontsize=9)

    elif chart_type == "pie":
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=140)
        ax.axis("equal")

    ax.set_title(question or f"{value_col} by {label_col}", fontsize=12, pad=15)
    ax.set_ylabel(value_col)
    plt.tight_layout()

    # Save with a unique filename
    filename  = f"chart_{uuid.uuid4().hex[:8]}.png"
    save_path = OUTPUT_DIR / filename
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    logger.info(f"Chart saved: {save_path}")
    return str(save_path)
