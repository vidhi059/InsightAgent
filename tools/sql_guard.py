"""
sql_guard.py
------------
Safety layer: only allow SELECT statements.
Rejects INSERT, UPDATE, DELETE, DROP, etc.

Why this matters (interview answer):
    The LLM generates SQL from user input. If we ran whatever it produced,
    a bad prompt could destroy data. We check BEFORE executing.
"""

import re


# Words that must never appear as the first SQL keyword
FORBIDDEN = {"insert", "update", "delete", "drop", "alter",
             "create", "replace", "truncate", "attach", "detach"}


def is_safe_sql(sql: str) -> tuple[bool, str]:
    """
    Returns (True, "") if the SQL is a safe SELECT.
    Returns (False, reason) if it is not.
    """
    # Strip whitespace and comments, lowercase for checking
    cleaned = sql.strip().lstrip("-").strip()
    first_word = re.split(r"\s+", cleaned)[0].lower()

    if first_word in FORBIDDEN:
        return False, f"Rejected: '{first_word.upper()}' statements are not allowed. Only SELECT is permitted."

    if first_word != "select":
        return False, f"Rejected: SQL must start with SELECT, got '{first_word.upper()}'."

    return True, ""
