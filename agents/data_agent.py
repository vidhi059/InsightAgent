"""
data_agent.py
-------------
Converts a natural-language question into SQL using Gemini,
executes it on SQLite, and returns a pandas DataFrame.

Includes:
- Phase 2: NL -> SQL single attempt
- Phase 3: Self-correction retry loop (max 3 attempts)
"""

import os
import sys
import sqlite3
import re
import time
import logging
from pathlib import Path

import pandas as pd
from google import genai
from dotenv import load_dotenv

# ── Path fix ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from tools.sql_guard     import is_safe_sql
from tools.schema_loader import get_schema_string

# ── Config ─────────────────────────────────────────────────────────────────────
load_dotenv()

DB_PATH = BASE_DIR / "db" / "superstore.db"


def get_api_key() -> str:
    """Read API key from Streamlit secrets (cloud) or .env (local)."""
    try:
        import streamlit as st
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.getenv("GEMINI_API_KEY", "")

# Try models in order until one works
MODELS = [
    "gemini-3.5-flash-lite",  # most available on free tier
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
]

client = genai.Client(api_key=get_api_key())

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ── Gemini call with retry ─────────────────────────────────────────────────────

def call_gemini(prompt: str, retries: int = 5, wait: int = 8) -> str:
    """
    Calls Gemini with automatic retry on 503 (server busy).
    Tries multiple models if one is unavailable.
    """
    for model in MODELS:
        for attempt in range(1, retries + 1):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                logger.info(f"Gemini responded using model: {model}")
                return response.text.strip()
            except Exception as e:
                err = str(e)
                if "503" in err or "UNAVAILABLE" in err:
                    logger.warning(f"Model {model} busy (attempt {attempt}/{retries}). Waiting {wait}s...")
                    time.sleep(wait)
                elif "404" in err or "NOT_FOUND" in err:
                    logger.warning(f"Model {model} not available, trying next...")
                    break  # try next model immediately
                else:
                    raise  # real error, don't retry

    raise RuntimeError("All Gemini models are currently unavailable. Please try again in a few minutes.")


# ── Prompt builders ────────────────────────────────────────────────────────────

def build_prompt(question: str, schema: str) -> str:
    """First attempt prompt — clean question with full schema."""
    return f"""You are an expert SQL assistant for a SQLite sales database.

{schema}

RULES:
1. Return ONLY the SQL query. No explanation, no markdown, no code fences.
2. The query MUST start with SELECT.
3. Use only the tables and columns listed in the schema above.
4. For date filters use the format YYYY-MM-DD (dates are stored as text).
5. Always use table aliases to avoid ambiguous column names.
6. If the question cannot be answered with the available data, return:
   SELECT 'Cannot answer: <reason>' AS message;

User question: {question}

SQL query:"""


def build_correction_prompt(question: str, schema: str, bad_sql: str, error: str) -> str:
    """
    Retry prompt — includes the previous bad SQL and the error message
    so Gemini can fix its mistake.
    """
    return f"""You are an expert SQL assistant for a SQLite sales database.

{schema}

You previously generated this SQL query:
{bad_sql}

It produced this error:
{error}

Fix the SQL query so it works correctly.

RULES:
1. Return ONLY the corrected SQL. No explanation, no markdown, no code fences.
2. The query MUST start with SELECT.
3. Use only the tables and columns in the schema above.
4. For dates use YYYY-MM-DD format.

Original question: {question}

Corrected SQL query:"""


# ── SQL cleaner ────────────────────────────────────────────────────────────────

def clean_sql(raw: str) -> str:
    """Strip markdown code fences if Gemini adds them."""
    cleaned = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE).strip()
    cleaned = cleaned.strip("`").strip()
    return cleaned


# ── Query runner ───────────────────────────────────────────────────────────────

def run_query(sql: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Run a SELECT query and return a DataFrame."""
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(sql, conn)
    finally:
        conn.close()
    return df


# ── Main function with self-correction (Phase 3) ───────────────────────────────

def query_data(question: str, max_attempts: int = 3) -> dict:
    """
    Converts a natural-language question to SQL, runs it, and returns results.
    Self-corrects up to max_attempts times if the SQL fails.

    Returns:
        {
            "success":  bool,
            "sql":      str,
            "data":     DataFrame,
            "error":    str,
            "attempts": int   # how many tries it took
        }
    """
    schema   = get_schema_string()
    last_sql = ""
    last_err = ""

    for attempt in range(1, max_attempts + 1):
        logger.info(f"SQL attempt {attempt}/{max_attempts} for: {question[:60]}")

        # Build the right prompt: first try = clean, retries = include error
        if attempt == 1:
            prompt = build_prompt(question, schema)
        else:
            prompt = build_correction_prompt(question, schema, last_sql, last_err)

        # Ask Gemini
        try:
            raw_sql = call_gemini(prompt)
        except RuntimeError as e:
            return {
                "success":  False,
                "sql":      "",
                "data":     pd.DataFrame(),
                "error":    str(e),
                "attempts": attempt,
            }

        sql = clean_sql(raw_sql)
        logger.info(f"Generated SQL:\n{sql}")

        # Safety check
        safe, reason = is_safe_sql(sql)
        if not safe:
            return {
                "success":  False,
                "sql":      sql,
                "data":     pd.DataFrame(),
                "error":    reason,
                "attempts": attempt,
            }

        # Execute query
        try:
            df = run_query(sql)

            if df.empty:
                logger.warning("Query returned 0 rows.")

            logger.info(f"Query succeeded on attempt {attempt}. Rows returned: {len(df)}")
            return {
                "success":  True,
                "sql":      sql,
                "data":     df,
                "error":    "",
                "attempts": attempt,
            }

        except Exception as e:
            last_sql = sql
            last_err = str(e)
            logger.warning(f"SQL error on attempt {attempt}: {last_err}")

    # All attempts exhausted
    return {
        "success":  False,
        "sql":      last_sql,
        "data":     pd.DataFrame(),
        "error":    f"Failed after {max_attempts} attempts. Last error: {last_err}",
        "attempts": max_attempts,
    }


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_questions = [
        "What is the total sales and profit for each region?",
        "Which are the top 5 products by profit?",
        "How many orders were placed in 2017?",
    ]

    for q in test_questions:
        print(f"\nQuestion: {q}")
        result = query_data(q)
        if result["success"]:
            print(f"SQL:\n{result['sql']}")
            print(f"\nResult:\n{result['data'].to_string(index=False)}")
            print(f"(solved in {result['attempts']} attempt(s))")
        else:
            print(f"Error: {result['error']}")
        print("-" * 60)
