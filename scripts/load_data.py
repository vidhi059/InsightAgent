"""
load_data.py
------------
Reads the flat superstore.csv and loads it into a normalized SQLite database.

Normalized schema (4 tables):
  - customers   : one row per unique customer
  - products    : one row per unique product
  - orders      : one row per unique order (header info)
  - order_items : one row per line item (the fact table)

Run this script once to create/reset the database:
    python scripts/load_data.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
# BASE_DIR is the project root (one level up from /scripts)
BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "superstore.csv"
DB_PATH  = BASE_DIR / "db"  / "superstore.db"


def load_csv(csv_path: Path) -> pd.DataFrame:
    """Read the CSV and fix data types."""

    df = pd.read_csv(csv_path, encoding="latin1")

    # Convert date strings (M/D/YYYY) to ISO format (YYYY-MM-DD)
    # SQLite stores them as text; ISO format sorts correctly as text
    df["Order Date"] = pd.to_datetime(df["Order Date"], format="%m/%d/%Y").dt.strftime("%Y-%m-%d")
    df["Ship Date"]  = pd.to_datetime(df["Ship Date"],  format="%m/%d/%Y").dt.strftime("%Y-%m-%d")

    # Keep Postal Code as string to preserve leading zeros (e.g. "01234")
    df["Postal Code"] = df["Postal Code"].astype(str).str.zfill(5)

    print(f"CSV loaded: {len(df)} rows, {len(df.columns)} columns")
    return df


def build_customers_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract one row per unique customer.
    Columns: customer_id, customer_name, segment
    """
    customers = (
        df[["Customer ID", "Customer Name", "Segment"]]
        .drop_duplicates(subset="Customer ID")
        .rename(columns={
            "Customer ID"   : "customer_id",
            "Customer Name" : "customer_name",
            "Segment"       : "segment",
        })
        .reset_index(drop=True)
    )
    print(f"Customers table: {len(customers)} rows")
    return customers


def build_products_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract one row per unique product.
    Columns: product_id, product_name, category, sub_category
    """
    products = (
        df[["Product ID", "Product Name", "Category", "Sub-Category"]]
        .drop_duplicates(subset="Product ID")
        .rename(columns={
            "Product ID"    : "product_id",
            "Product Name"  : "product_name",
            "Category"      : "category",
            "Sub-Category"  : "sub_category",
        })
        .reset_index(drop=True)
    )
    print(f"Products table: {len(products)} rows")
    return products


def build_orders_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract one row per unique order (the order header).
    Columns: order_id, order_date, ship_date, ship_mode,
             customer_id, country, city, state, postal_code, region
    """
    orders = (
        df[[
            "Order ID", "Order Date", "Ship Date", "Ship Mode",
            "Customer ID", "Country", "City", "State", "Postal Code", "Region"
        ]]
        .drop_duplicates(subset="Order ID")
        .rename(columns={
            "Order ID"    : "order_id",
            "Order Date"  : "order_date",
            "Ship Date"   : "ship_date",
            "Ship Mode"   : "ship_mode",
            "Customer ID" : "customer_id",
            "Country"     : "country",
            "City"        : "city",
            "State"       : "state",
            "Postal Code" : "postal_code",
            "Region"      : "region",
        })
        .reset_index(drop=True)
    )
    print(f"Orders table: {len(orders)} rows")
    return orders


def build_order_items_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per line item — this is the fact table.
    Columns: row_id, order_id, product_id, sales, quantity, discount, profit
    """
    order_items = df[[
        "Row ID", "Order ID", "Product ID",
        "Sales", "Quantity", "Discount", "Profit"
    ]].rename(columns={
        "Row ID"     : "row_id",
        "Order ID"   : "order_id",
        "Product ID" : "product_id",
        "Sales"      : "sales",
        "Quantity"   : "quantity",
        "Discount"   : "discount",
        "Profit"     : "profit",
    })
    print(f"Order items table: {len(order_items)} rows")
    return order_items


def create_schema(conn: sqlite3.Connection) -> None:
    """
    Create the 4 tables with proper types and foreign keys.
    DROP + CREATE so we can re-run the script safely.
    """
    conn.executescript("""
        PRAGMA foreign_keys = ON;

        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS products;

        -- One row per customer
        CREATE TABLE customers (
            customer_id   TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            segment       TEXT NOT NULL
        );

        -- One row per product
        CREATE TABLE products (
            product_id   TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            category     TEXT NOT NULL,
            sub_category TEXT NOT NULL
        );

        -- One row per order (header info)
        CREATE TABLE orders (
            order_id    TEXT PRIMARY KEY,
            order_date  TEXT NOT NULL,   -- stored as YYYY-MM-DD
            ship_date   TEXT NOT NULL,
            ship_mode   TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            country     TEXT NOT NULL,
            city        TEXT NOT NULL,
            state       TEXT NOT NULL,
            postal_code TEXT NOT NULL,
            region      TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        -- One row per line item (the fact table)
        CREATE TABLE order_items (
            row_id     INTEGER PRIMARY KEY,
            order_id   TEXT    NOT NULL,
            product_id TEXT    NOT NULL,
            sales      REAL    NOT NULL,
            quantity   INTEGER NOT NULL,
            discount   REAL    NOT NULL,
            profit     REAL    NOT NULL,
            FOREIGN KEY (order_id)   REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
    """)
    print("Schema created successfully")


def load_to_sqlite(
    customers:   pd.DataFrame,
    products:    pd.DataFrame,
    orders:      pd.DataFrame,
    order_items: pd.DataFrame,
    db_path:     Path,
) -> None:
    """Write all four DataFrames into the SQLite database."""

    # Ensure the db/ directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)

    # Create tables
    create_schema(conn)

    # Insert data — if_exists="append" because we just created empty tables
    customers.to_sql("customers",   conn, if_exists="append", index=False)
    products.to_sql("products",     conn, if_exists="append", index=False)
    orders.to_sql("orders",         conn, if_exists="append", index=False)
    order_items.to_sql("order_items", conn, if_exists="append", index=False)

    conn.commit()
    conn.close()
    print(f"\nDatabase saved to: {db_path}")


def verify_database(db_path: Path) -> None:
    """Run a few sample queries to confirm everything loaded correctly."""

    conn = sqlite3.connect(db_path)

    print("\n── Verification Queries ──────────────────────────────")

    # 1. Row counts
    for table in ["customers", "products", "orders", "order_items"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")

    # 2. Total sales and profit
    result = conn.execute("""
        SELECT
            ROUND(SUM(sales), 2)  AS total_sales,
            ROUND(SUM(profit), 2) AS total_profit
        FROM order_items
    """).fetchone()
    print(f"\n  Total Sales:  ${result[0]:,.2f}")
    print(f"  Total Profit: ${result[1]:,.2f}")

    # 3. Sales by region (joining all tables)
    print("\n  Sales by Region:")
    rows = conn.execute("""
        SELECT
            o.region,
            ROUND(SUM(oi.sales), 2) AS total_sales
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        GROUP BY o.region
        ORDER BY total_sales DESC
    """).fetchall()
    for row in rows:
        print(f"    {row[0]}: ${row[1]:,.2f}")

    # 4. Top 3 categories by profit
    print("\n  Top 3 Categories by Profit:")
    rows = conn.execute("""
        SELECT
            p.category,
            ROUND(SUM(oi.profit), 2) AS total_profit
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        GROUP BY p.category
        ORDER BY total_profit DESC
        LIMIT 3
    """).fetchall()
    for row in rows:
        print(f"    {row[0]}: ${row[1]:,.2f}")

    conn.close()
    print("\n── Verification complete ✓ ───────────────────────────")


def main() -> None:
    print("=" * 50)
    print("Superstore Data Loader")
    print("=" * 50)

    # Step 1: Load and clean the CSV
    df = load_csv(CSV_PATH)

    # Step 2: Split into normalized tables
    customers   = build_customers_table(df)
    products    = build_products_table(df)
    orders      = build_orders_table(df)
    order_items = build_order_items_table(df)

    # Step 3: Write to SQLite
    load_to_sqlite(customers, products, orders, order_items, DB_PATH)

    # Step 4: Verify with sample queries
    verify_database(DB_PATH)


if __name__ == "__main__":
    main()
