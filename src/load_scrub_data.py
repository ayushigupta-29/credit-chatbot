"""
ETL — scrub_comparison_master.csv → encrypted SQLite
------------------------------------------------------
One-time script. Run from project root:

    python src/load_scrub_data.py

Reads notebooks/scrub_comparison_master.csv and populates 4 tables:
  - customer_scrub_snapshot  (two rows per customer: Nov 2025 + Jan 2026)
  - customer_scrub_delta     (one row per changed driver per customer)
  - segment_driver_patterns  (aggregated, no PII)
  - customer_consents        (empty — populated at runtime by users)

Output: data/credit_data.db.enc (encrypted with KB_ENCRYPTION_KEY from .env)
"""

import os
import sys
import math

import pandas as pd

# Ensure src/ is importable when run from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from db import create_schema, save_db
from score_drivers import load_drivers, DRIVERS_DB

import sqlite3

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH  = os.path.join(BASE_DIR, "notebooks", "scrub_comparison_master.csv")

SCRUB_FROM = "2025-11-01"
SCRUB_TO   = "2026-01-01"

# ── Driver definitions — loaded from score_drivers.db ─────────────────────────
# Each entry: dict with driver_key, csv_col_from, csv_col_to, csv_delta_col,
#             good_if_increase, good_if_decrease
def _load_drivers() -> list[dict]:
    drivers_conn = sqlite3.connect(DRIVERS_DB)
    rows = load_drivers(drivers_conn)
    drivers_conn.close()
    return rows

DRIVERS = _load_drivers()


def _nan_to_none(val):
    """Convert NaN / inf to None for SQLite insertion."""
    if val is None:
        return None
    try:
        if math.isnan(val) or math.isinf(val):
            return None
    except (TypeError, ValueError):
        pass
    return val


def _direction(delta, good_if_increase: int, good_if_decrease: int) -> str | None:
    """
    Classify delta direction using per-driver polarity from score_drivers.db.
    Returns None when:
      - delta is zero / missing
      - the relevant polarity is 2 (no effect) — row won't be inserted
    """
    if delta is None or (isinstance(delta, float) and math.isnan(delta)):
        return None
    if delta < 0:
        if good_if_decrease == 1:
            return "improved"
        if good_if_decrease == 0:
            return "worsened"
        return None  # 2 = no effect
    if delta > 0:
        if good_if_increase == 1:
            return "improved"
        if good_if_increase == 0:
            return "worsened"
        return None  # 2 = no effect
    return None  # unchanged


def load_csv() -> pd.DataFrame:
    print(f"Reading CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, dtype={"phone": str})
    print(f"  Rows: {len(df):,}  |  Columns: {len(df.columns)}")
    return df


def populate_snapshots(df: pd.DataFrame, conn: sqlite3.Connection) -> int:
    """
    Insert two rows per customer: Nov 2025 and Jan 2026 snapshots.
    Rows with no score data are skipped.
    """
    rows_inserted = 0
    cur = conn.cursor()

    for _, row in df.iterrows():
        phone = str(row["phone"]).strip()

        # Nov 2025 snapshot
        score_n = _nan_to_none(row.get("score_nov25"))
        if score_n is not None:
            cur.execute(
                """
                INSERT INTO customer_scrub_snapshot
                    (customer_phone, scrub_date, score, band,
                     total_accounts, active_accounts,
                     has_dpd30_12m, has_dpd60_24m, has_dpd90_36m,
                     has_npa, has_writeoff, cc_util_pct, enq_6m, enq_12m,
                     cc_count_active)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    phone, SCRUB_FROM,
                    int(score_n),
                    row.get("band_nov25"),
                    _nan_to_none(row.get("total_accounts_n25")),
                    _nan_to_none(row.get("active_accounts_n25")),
                    _nan_to_none(row.get("has_dpd30_12m_n25")),
                    _nan_to_none(row.get("has_dpd60_24m_n25")),
                    _nan_to_none(row.get("has_dpd90_36m_n25")),
                    _nan_to_none(row.get("has_npa_n25")),
                    _nan_to_none(row.get("has_writeoff_n25")),
                    _nan_to_none(row.get("cc_util_pct_n25")),
                    _nan_to_none(row.get("enq_6m_n25")),
                    _nan_to_none(row.get("enq_12m_n25")),
                    _nan_to_none(row.get("cc_count_active_n25")),
                ),
            )
            rows_inserted += 1

        # Jan 2026 snapshot
        score_j = _nan_to_none(row.get("score_jan26"))
        if score_j is not None:
            cur.execute(
                """
                INSERT INTO customer_scrub_snapshot
                    (customer_phone, scrub_date, score, band,
                     total_accounts, active_accounts,
                     has_dpd30_12m, has_dpd60_24m, has_dpd90_36m,
                     has_npa, has_writeoff, cc_util_pct, enq_6m, enq_12m,
                     cc_count_active)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    phone, SCRUB_TO,
                    int(score_j),
                    row.get("band_jan26"),
                    _nan_to_none(row.get("total_accounts_j26")),
                    _nan_to_none(row.get("active_accounts_j26")),
                    _nan_to_none(row.get("has_dpd30_12m_j26")),
                    _nan_to_none(row.get("has_dpd60_24m_j26")),
                    _nan_to_none(row.get("has_dpd90_36m_j26")),
                    _nan_to_none(row.get("has_npa_j26")),
                    _nan_to_none(row.get("has_writeoff_j26")),
                    _nan_to_none(row.get("cc_util_pct_j26")),
                    _nan_to_none(row.get("enq_6m_j26")),
                    _nan_to_none(row.get("enq_12m_j26")),
                    _nan_to_none(row.get("cc_count_active_j26")),
                ),
            )
            rows_inserted += 1

    conn.commit()
    return rows_inserted


def populate_deltas(df: pd.DataFrame, conn: sqlite3.Connection) -> int:
    """
    Insert one row per driver that actually changed (delta != 0) per customer.
    Each row carries score_from, score_to, score_delta on every record.
    """
    rows_inserted = 0
    cur = conn.cursor()

    for _, row in df.iterrows():
        phone        = str(row["phone"]).strip()
        score_from_v = _nan_to_none(row.get("score_nov25"))
        score_to_v   = _nan_to_none(row.get("score_jan26"))
        score_delta_v = _nan_to_none(row.get("score_delta"))
        segment_v    = row.get("segment")

        for d in DRIVERS:
            driver_name = d["driver_key"]
            col_from    = d["csv_col_from"]
            col_to      = d["csv_col_to"]
            delta_col   = d["csv_delta_col"]
            gii         = d["good_if_increase"]
            gid         = d["good_if_decrease"]

            delta_val = _nan_to_none(row.get(delta_col))
            direction = _direction(delta_val, gii, gid)
            if direction is None:
                continue  # no change, missing, or no-effect driver — skip

            val_from = _nan_to_none(row.get(col_from))
            val_to   = _nan_to_none(row.get(col_to))

            cur.execute(
                """
                INSERT INTO customer_scrub_delta
                    (customer_phone, scrub_from, scrub_to,
                     score_from, score_to, score_delta, segment,
                     driver, value_from, value_to, delta_value, direction)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    phone, SCRUB_FROM, SCRUB_TO,
                    int(score_from_v) if score_from_v is not None else None,
                    int(score_to_v)   if score_to_v   is not None else None,
                    int(score_delta_v) if score_delta_v is not None else None,
                    segment_v,
                    driver_name,
                    str(val_from) if val_from is not None else None,
                    str(val_to)   if val_to   is not None else None,
                    float(delta_val),
                    direction,
                ),
            )
            rows_inserted += 1

    conn.commit()
    return rows_inserted


def populate_patterns(df: pd.DataFrame, conn: sqlite3.Connection) -> int:
    """
    Aggregate statistics per segment × driver (no PII).
    Computes pct_flag_from/to (mean of binary flag or mean value for numerics),
    median_delta, and score_corr (Pearson correlation with score_delta).
    """
    rows_inserted = 0
    cur = conn.cursor()

    segments = df["segment"].dropna().unique()

    for d in DRIVERS:
        driver_name = d["driver_key"]
        col_from    = d["csv_col_from"]
        col_to      = d["csv_col_to"]
        delta_col   = d["csv_delta_col"]
        for segment in segments:
            seg_df = df[df["segment"] == segment].copy()
            if seg_df.empty:
                continue

            col_from_vals  = pd.to_numeric(seg_df[col_from],  errors="coerce") if col_from  in seg_df.columns else pd.Series(dtype=float)
            col_to_vals    = pd.to_numeric(seg_df[col_to],    errors="coerce") if col_to    in seg_df.columns else pd.Series(dtype=float)
            delta_vals     = pd.to_numeric(seg_df[delta_col], errors="coerce") if delta_col in seg_df.columns else pd.Series(dtype=float)
            score_delta_v  = pd.to_numeric(seg_df["score_delta"], errors="coerce")

            pct_flag_from = _nan_to_none(col_from_vals.mean())
            pct_flag_to   = _nan_to_none(col_to_vals.mean())
            median_delta  = _nan_to_none(delta_vals.median())

            # Pearson correlation between driver delta and score delta
            score_corr = None
            valid = delta_vals.notna() & score_delta_v.notna()
            if valid.sum() >= 3:
                corr = delta_vals[valid].corr(score_delta_v[valid])
                score_corr = _nan_to_none(corr)

            cur.execute(
                """
                INSERT INTO segment_driver_patterns
                    (scrub_from, scrub_to, segment, driver,
                     pct_flag_from, pct_flag_to, median_delta, score_corr)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    SCRUB_FROM, SCRUB_TO,
                    segment, driver_name,
                    pct_flag_from, pct_flag_to, median_delta, score_corr,
                ),
            )
            rows_inserted += 1

    conn.commit()
    return rows_inserted


def main():
    print("=" * 60)
    print("  Credit Chatbot — Scrub Data ETL")
    print("=" * 60)

    df = load_csv()

    # Create fresh in-memory DB
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    print("\nSchema created.")

    print("\n[1/3] Populating customer_scrub_snapshot ...")
    n_snap = populate_snapshots(df, conn)
    print(f"      Inserted {n_snap:,} rows")

    print("\n[2/3] Populating customer_scrub_delta ...")
    n_delta = populate_deltas(df, conn)
    print(f"      Inserted {n_delta:,} rows")

    print("\n[3/3] Populating segment_driver_patterns ...")
    n_pat = populate_patterns(df, conn)
    print(f"      Inserted {n_pat:,} rows")

    # customer_consents stays empty — populated at runtime
    print("\n      customer_consents: 0 rows (populated at runtime)")

    print("\nSaving encrypted DB ...")
    save_db(conn)
    conn.close()

    from db import DB_ENC_PATH
    size_kb = os.path.getsize(DB_ENC_PATH) / 1024
    print(f"      Written: {DB_ENC_PATH}")
    print(f"      Size:    {size_kb:.1f} KB")

    print("\n" + "=" * 60)
    print("  ETL complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
