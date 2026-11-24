"""
main.py — Streamlit Chat UI
---------------------------
Run with:  streamlit run app/main.py
"""

import sys
import os
from pathlib import Path

# Allow imports from project root
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Auto-load database if it doesn't exist (needed on Streamlit Cloud)
DB_PATH = BASE_DIR / "db" / "superstore.db"
CSV_PATH = BASE_DIR / "data" / "superstore.csv"
if not DB_PATH.exists() and CSV_PATH.exists():
    from scripts.load_data import main as load_db
    load_db()

import streamlit as st
from agents.orchestrator import run_agent

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title = "Sales Analytics Agent",
    page_icon  = "📊",
    layout     = "wide",
)

# ── Session state ──────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

if "context" not in st.session_state:
    st.session_state.context = {}

if "pending_report" not in st.session_state:
    st.session_state.pending_report = None

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Sales Agent")
    st.markdown("Ask anything about the Superstore sales data.")
    st.divider()

    st.markdown("**Example questions:**")
    examples = [
        "What is the total sales by region?",
        "Which category has the highest profit?",
        "Show me the top 5 customers by sales",
        "How did sales change year over year?",
        "Which products are losing money?",
        "Generate a weekly sales report",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["prefill"] = ex

    st.divider()
    if st.button("🗑 Clear conversation", use_container_width=True):
        st.session_state.history  = []
        st.session_state.context  = {}
        st.session_state.pending_report = None
        st.rerun()

# ── Main chat area ─────────────────────────────────────────────────────────────
st.title("📊 Agentic Sales Analytics")
st.caption("Powered by Gemini · Superstore Database · Ask in plain English")

# Display conversation history
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        content = msg["content"]
        # If it's a tool call summary, show it in an expander
        if content.startswith("[Tool:"):
            with st.expander("🔧 Agent action", expanded=False):
                st.code(content)
        else:
            st.markdown(content)

# Show chart if available
if st.session_state.context.get("last_chart"):
    chart_path = st.session_state.context["last_chart"]
    if Path(chart_path).exists():
        st.image(chart_path, use_container_width=True)

# ── Human-in-the-loop: report confirmation ─────────────────────────────────────
if st.session_state.context.get("pending_report"):
    report_path = st.session_state.context["pending_report"]
    ext = Path(report_path).suffix.lower()

    st.warning("⚠️ A report is ready. Review before downloading.")

    # Preview
    if ext == ".html":
        with st.expander("📧 Preview Email Report", expanded=True):
            html_content = Path(report_path).read_text(encoding="utf-8")
            st.components.v1.html(html_content, height=500, scrolling=True)

    col1, col2 = st.columns(2)
    with col1:
        with open(report_path, "rb") as f:
            label = "📥 Download Report"
            fname = Path(report_path).name
            st.download_button(label, f, file_name=fname, use_container_width=True)
    with col2:
        if st.button("❌ Discard Report", use_container_width=True):
            st.session_state.context.pop("pending_report", None)
            st.rerun()

# ── Chat input ─────────────────────────────────────────────────────────────────
prefill = st.session_state.pop("prefill", "")
user_input = st.chat_input("Ask a question about sales data...", key="chat_input")

# Allow sidebar example buttons to prefill
if prefill and not user_input:
    user_input = prefill

if user_input:
    # Show user message immediately
    with st.chat_message("user"):
        st.markdown(user_input)

    # Run the agent
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer, new_history, new_context = run_agent(
                    user_input,
                    st.session_state.history,
                )
                st.session_state.history = new_history
                st.session_state.context = new_context

                # Show the answer
                st.markdown(answer)

                # Show chart inline if just generated
                if new_context.get("last_chart"):
                    chart_path = new_context["last_chart"]
                    if Path(chart_path).exists():
                        st.image(chart_path, use_container_width=True)

                # Show data table if available
                if new_context.get("last_data") is not None:
                    df = new_context["last_data"]
                    if not df.empty:
                        with st.expander(f"📋 View data ({len(df)} rows)", expanded=False):
                            st.dataframe(df, use_container_width=True)

            except Exception as e:
                st.error(f"Agent error: {str(e)}")

    st.rerun()
