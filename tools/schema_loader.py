"""
schema_loader.py
----------------
Reads the SQLite database and returns a plain-text description of the schema.

We pass this string to the LLM so it knows exactly what tables and columns
exist before it writes any SQL.

Why not hardcode the schema?
    If we ever add a column or rename a table, this function automatically
    picks up the change. The LLM always sees the real schema.
"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH  = BASE_DIR / "db" / "superstore.db"


def get_schema_string(db_path: Path = DB_PATH) -> str:
    """
    Returns a human-readable schema string like:

        Table: customers
          customer_id   TEXT
          customer_name TEXT
          segment       TEXT
        ...
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    lines = ["Database schema (SQLite):", ""]

    for table in tables:
        lines.append(f"Table: {table}")
        # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
        cursor.execute(f"PRAGMA table_info({table})")
        for col in cursor.fetchall():
            col_name = col[1]
            col_type = col[2]
            pk_flag  = " (PRIMARY KEY)" if col[5] else ""
            lines.append(f"  {col_name:<20} {col_type}{pk_flag}")
        lines.append("")  # blank line between tables

    conn.close()
    return "\n".join(lines)


if __name__ == "__main__":
    # Quick test: run this file directly to see the schema
    print(get_schema_string())
