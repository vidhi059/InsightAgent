"""
orchestrator.py
---------------
The brain of the agent. Receives the user message, decides which tool
to call, calls it, observes the result, and loops until done.

Tools available:
  - query_data      : NL -> SQL -> DataFrame
  - analyze_trends  : period-over-period % change + anomaly detection
  - make_chart      : generates a bar/line chart image
  - generate_report : fills a PPTX or email template with data

Multi-turn memory: conversation history is passed in and updated each turn.
"""

import os
import sys
import json
import logging
from pathlib import Path

from google import genai
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agents.data_agent     import query_data
from agents.analysis_agent import analyze_trends
from agents.viz_agent      import make_chart
from agents.report_agent   import generate_report

load_dotenv()
logger = logging.getLogger(__name__)


def get_api_key() -> str:
    """Read API key from Streamlit secrets (cloud) or .env (local)."""
    try:
        import streamlit as st
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.getenv("GEMINI_API_KEY", "")


client = genai.Client(api_key=get_api_key())

MODELS = [
    "gemini-3.5-flash-lite",  # most available on free tier
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
]

# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful sales analytics assistant.
You have access to a Superstore sales database with tables:
  orders, order_items, customers, products

When the user asks a data question, respond with a JSON tool call.
When you have enough information to answer, respond in plain English.

Available tools (respond with JSON only, no other text):
  {"tool": "query_data",     "question": "<natural language question>"}
  {"tool": "analyze_trends", "question": "<what to analyze>"}
  {"tool": "make_chart",     "question": "<what to chart>", "chart_type": "bar|line|pie"}
  {"tool": "generate_report","report_type": "weekly_sales|rep_summary|quarterly_trends"}
  {"tool": "answer",         "text": "<your plain English answer to the user>"}

Rules:
- If the user asks a data question, always call query_data first.
- If the user asks for a chart, call query_data then make_chart.
- If the user asks for a report, call generate_report.
- If you can answer from already-retrieved data, use the answer tool.
- Never fabricate numbers. All numbers must come from tool results.
"""


# ── Gemini call ────────────────────────────────────────────────────────────────

def call_gemini_orchestrator(messages: list) -> str:
    """Call Gemini with conversation history. Returns raw text."""
    import time

    # Build a single prompt from message history
    prompt = SYSTEM_PROMPT + "\n\n"
    for msg in messages:
        role = msg["role"].upper()
        prompt += f"{role}: {msg['content']}\n"
    prompt += "ASSISTANT:"

    for model in MODELS:
        for attempt in range(5):
            try:
                response = client.models.generate_content(
                    model=model, contents=prompt
                )
                return response.text.strip()
            except Exception as e:
                err = str(e)
                if "503" in err or "UNAVAILABLE" in err:
                    time.sleep(8)
                elif "404" in err or "NOT_FOUND" in err:
                    break
                else:
                    raise

    raise RuntimeError("Gemini unavailable. Try again in a few minutes.")


# ── Tool dispatcher ────────────────────────────────────────────────────────────

def dispatch_tool(tool_call: dict, context: dict) -> tuple[str, dict]:
    """
    Runs the requested tool and returns (result_text, updated_context).
    context stores data/charts collected during this conversation turn.
    """
    tool = tool_call.get("tool")

    if tool == "query_data":
        result = query_data(tool_call["question"])
        if result["success"]:
            context["last_data"] = result["data"]
            context["last_sql"]  = result["sql"]
            rows = result["data"].to_string(index=False)
            return f"Query succeeded ({len(result['data'])} rows):\n{rows}", context
        else:
            return f"Query failed: {result['error']}", context

    elif tool == "analyze_trends":
        if context.get("last_data") is None:
            return "No data available to analyze. Run query_data first.", context
        summary = analyze_trends(context["last_data"])
        context["last_analysis"] = summary
        return summary, context

    elif tool == "make_chart":
        if context.get("last_data") is None:
            return "No data available to chart. Run query_data first.", context
        chart_path = make_chart(
            df         = context["last_data"],
            question   = tool_call.get("question", ""),
            chart_type = tool_call.get("chart_type", "bar"),
        )
        context["last_chart"] = chart_path
        return f"Chart saved to: {chart_path}", context

    elif tool == "generate_report":
        report_path = generate_report(
            report_type = tool_call.get("report_type", "weekly_sales"),
            data        = context.get("last_data"),
            analysis    = context.get("last_analysis", ""),
            chart_path  = context.get("last_chart"),
        )
        context["pending_report"] = report_path
        return f"Report ready for preview: {report_path}", context

    elif tool == "answer":
        return tool_call.get("text", ""), context

    else:
        return f"Unknown tool: {tool}", context


# ── Parse LLM response ─────────────────────────────────────────────────────────

def parse_response(text: str) -> dict | None:
    """
    Try to parse a JSON tool call from the LLM response.
    Returns the dict if valid JSON with a 'tool' key, else None.
    """
    text = text.strip()
    # Sometimes wrapped in ```json ... ```
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        obj = json.loads(text)
        if "tool" in obj:
            return obj
    except Exception:
        pass
    return None


# ── Main agent loop ────────────────────────────────────────────────────────────

def run_agent(user_message: str, history: list) -> tuple[str, list, dict]:
    """
    Main entry point called by the Streamlit UI.

    Args:
        user_message: the user's latest message
        history:      list of {"role": "user"|"assistant", "content": str}

    Returns:
        (final_answer, updated_history, context)
        context may contain: last_data, last_chart, pending_report
    """
    # Add user message to history
    history = history + [{"role": "user", "content": user_message}]
    context = {}
    max_loops = 6  # prevent infinite loops

    for loop in range(max_loops):
        logger.info(f"Orchestrator loop {loop + 1}")

        # Ask the LLM what to do next
        raw = call_gemini_orchestrator(history)
        logger.info(f"LLM response: {raw[:200]}")

        # Try to parse a tool call
        tool_call = parse_response(raw)

        if tool_call is None:
            # LLM returned plain text — treat as final answer
            history.append({"role": "assistant", "content": raw})
            return raw, history, context

        if tool_call.get("tool") == "answer":
            answer = tool_call.get("text", raw)
            history.append({"role": "assistant", "content": answer})
            return answer, history, context

        # Execute the tool
        tool_result, context = dispatch_tool(tool_call, context)
        logger.info(f"Tool result preview: {tool_result[:200]}")

        # Add tool result to history so LLM knows what happened
        history.append({"role": "assistant", "content": f"[Tool: {tool_call['tool']}] {tool_result}"})

    # Fallback if loops exhausted
    fallback = "I was unable to fully answer your question. Please try rephrasing it."
    history.append({"role": "assistant", "content": fallback})
    return fallback, history, context
