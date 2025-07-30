import sqlite3
import pandas as pd
import os

DB_PATH = "forecast.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def create_forecast_table(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ds TEXT,
            sku TEXT,
            yhat REAL,
            yhat_lower REAL,
            yhat_upper REAL,
            reorder_trigger TEXT
        )
    """)
    conn.commit()

def save_forecast_df(conn, forecast_df):
    save_df = forecast_df[["ds", "sku", "yhat", "yhat_lower", "yhat_upper", "reorder_trigger"]].copy()
    save_df.to_sql("forecasts", conn, if_exists="append", index=False)

def get_all_forecasts(conn):
    return pd.read_sql_query("SELECT * FROM forecasts", conn)

def get_forecasts_by_filter(conn, sku=None, start_date=None, end_date=None):
    query = "SELECT * FROM forecasts WHERE 1=1"
    params = []

    if sku:
        query += " AND sku = ?"
        params.append(sku)
    if start_date:
        query += " AND ds >= ?"
        params.append(start_date)
    if end_date:
        query += " AND ds <= ?"
        params.append(end_date)

    return pd.read_sql_query(query, conn, params=params)

def delete_forecasts(conn, sku=None):
    cursor = conn.cursor()
    if sku:
        cursor.execute("DELETE FROM forecasts WHERE sku = ?", (sku,))
    else:
        cursor.execute("DELETE FROM forecasts")
    conn.commit()

def update_reorder_trigger(conn, forecast_id, new_trigger):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE forecasts SET reorder_trigger = ? WHERE id = ?",
        (new_trigger, forecast_id)
    )
    conn.commit()

