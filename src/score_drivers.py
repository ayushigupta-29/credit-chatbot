"""
Score Drivers DB Setup
-----------------------
Creates and seeds data/score_drivers.db — a plain SQLite reference DB.
No customer data. No encryption needed. Safe to commit.

Tables:
  master_reference        — maps coded integers (0/1/2) to human labels
                            for every column in every table that uses codes
  score_driver_reference  — all credit score drivers with polarity + approval
  score_driver_thresholds — quantified impact ranges per driver (empty at init)

Run from project root:
    python src/score_drivers.py
"""

import os
import sqlite3

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVERS_DB = os.path.join(BASE_DIR, "data", "score_drivers.db")

TS = "strftime('%Y-%m-%d %H:%M:%f', 'now')"

# ── Seed: master_reference ─────────────────────────────────────────────────────
# (value, type_id, type_key, code)
MASTER_REFERENCE_SEED = [
    # score_driver_reference:good_if_increase  — type_id 1
    ("Bad for score",   1, "score_driver_reference:good_if_increase", 0),
    ("Good for score",  1, "score_driver_reference:good_if_increase", 1),
    ("No effect",       1, "score_driver_reference:good_if_increase", 2),
    # score_driver_reference:good_if_decrease  — type_id 2
    ("Bad for score",   2, "score_driver_reference:good_if_decrease", 0),
    ("Good for score",  2, "score_driver_reference:good_if_decrease", 1),
    ("No effect",       2, "score_driver_reference:good_if_decrease", 2),
    # score_driver_reference:is_approved  — type_id 3
    ("Pending review",  3, "score_driver_reference:is_approved",      0),
    ("Approved",        3, "score_driver_reference:is_approved",      1),
    # score_driver_reference:delta_tracked  — type_id 4
    ("Not tracked",     4, "score_driver_reference:delta_tracked",    0),
    ("Tracked",         4, "score_driver_reference:delta_tracked",    1),
    # score_driver_thresholds:score_impact  — type_id 5
    ("Bad for score",   5, "score_driver_thresholds:score_impact",    0),
    ("Low positive",    5, "score_driver_thresholds:score_impact",    1),
    ("High positive",   5, "score_driver_thresholds:score_impact",    2),
    ("Neutral",         5, "score_driver_thresholds:score_impact",    3),
    ("Low negative",    5, "score_driver_thresholds:score_impact",    4),
    ("High negative",   5, "score_driver_thresholds:score_impact",    5),
]

# ── Seed: score_driver_reference ───────────────────────────────────────────────
# (driver_key, label, category,
#  good_if_increase, good_if_decrease,
#  csv_col_from, csv_col_to, csv_delta_col)
# All 12 seeded with delta_tracked=1, is_approved=1
DRIVERS_SEED = [
    ("has_dpd30_12m",    "DPD 30+ (last 12m)",             "dpd",         0, 1,
     "has_dpd30_12m_n25",     "has_dpd30_12m_j26",     "delta_has_dpd30_12m"),
    ("has_dpd60_24m",    "DPD 60+ (last 24m)",             "dpd",         0, 1,
     "has_dpd60_24m_n25",     "has_dpd60_24m_j26",     "delta_has_dpd60_24m"),
    ("has_dpd90_36m",    "DPD 90+ (last 36m)",             "dpd",         0, 1,
     "has_dpd90_36m_n25",     "has_dpd90_36m_j26",     "delta_has_dpd90_36m"),
    ("has_npa",          "NPA account",                     "dpd",         0, 1,
     "has_npa_n25",            "has_npa_j26",            "delta_has_npa"),
    ("has_writeoff",     "Write-off / settlement",          "dpd",         0, 1,
     "has_writeoff_n25",       "has_writeoff_j26",       "delta_has_writeoff"),
    ("cc_util_pct",      "CC/OD utilisation",               "utilisation", 0, 1,
     "cc_util_pct_n25",        "cc_util_pct_j26",        "delta_cc_util_pct"),
    ("enq_6m",           "Enquiries (last 6m)",             "enquiries",   0, 1,
     "enq_6m_n25",             "enq_6m_j26",             "delta_enq_6m"),
    ("enq_12m",          "Enquiries (last 12m)",            "enquiries",   0, 1,
     "enq_12m_n25",            "enq_12m_j26",            "delta_enq_12m"),
    ("num_dpd30_12m",    "No. of DPD 30+ incidents (12m)", "dpd",         0, 1,
     "num_dpd30_12m_n25",      "num_dpd30_12m_j26",      "delta_num_dpd30_12m"),
    ("total_accounts",   "Total accounts",                  "accounts",    1, 0,
     "total_accounts_n25",     "total_accounts_j26",     "delta_total_accounts"),
    ("active_accounts",  "Active accounts",                 "accounts",    1, 2,
     "active_accounts_n25",    "active_accounts_j26",    "delta_active_accounts"),
    ("total_outstanding","Total outstanding balance",        "utilisation", 0, 1,
     "total_outstanding_n25",  "total_outstanding_j26",  "delta_total_outstanding"),
]


def create_schema(conn):
    conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS master_reference (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT    NOT NULL DEFAULT ({TS}),
            is_active  INTEGER NOT NULL DEFAULT 1,
            value      TEXT    NOT NULL,
            type_id    INTEGER NOT NULL,
            type_key   TEXT    NOT NULL,
            updated_at TEXT    NOT NULL DEFAULT ({TS}),
            code       INTEGER NOT NULL,
            UNIQUE (type_key, code)
        );

        CREATE TABLE IF NOT EXISTS score_driver_reference (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_key       TEXT    NOT NULL UNIQUE,
            label            TEXT    NOT NULL,
            category         TEXT    NOT NULL,
            good_if_increase INTEGER NOT NULL,
            good_if_decrease INTEGER NOT NULL,
            csv_col_from     TEXT,
            csv_col_to       TEXT,
            csv_delta_col    TEXT,
            delta_tracked    INTEGER NOT NULL DEFAULT 0,
            is_approved      INTEGER NOT NULL DEFAULT 0,
            approved_at      TEXT,
            created_at       TEXT    NOT NULL DEFAULT ({TS}),
            updated_at       TEXT    NOT NULL DEFAULT ({TS})
        );

        CREATE TABLE IF NOT EXISTS score_driver_thresholds (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_key       TEXT    NOT NULL,
            change_direction TEXT    NOT NULL,
            range_from       REAL,
            range_to         REAL,
            score_impact     INTEGER NOT NULL,
            notes            TEXT,
            is_approved      INTEGER NOT NULL DEFAULT 0,
            approved_at      TEXT,
            created_at       TEXT    NOT NULL DEFAULT ({TS}),
            updated_at       TEXT    NOT NULL DEFAULT ({TS})
        );
    """)
    conn.commit()


def seed(conn):
    cur = conn.cursor()
    now = _now()

    # master_reference
    cur.executemany(
        f"""INSERT OR IGNORE INTO master_reference
            (created_at, is_active, value, type_id, type_key, updated_at, code)
            VALUES (?, 1, ?, ?, ?, ?, ?)""",
        [(now, v, tid, tk, now, code) for v, tid, tk, code in MASTER_REFERENCE_SEED],
    )

    # score_driver_reference — all approved
    cur.executemany(
        f"""INSERT OR IGNORE INTO score_driver_reference
            (driver_key, label, category,
             good_if_increase, good_if_decrease,
             csv_col_from, csv_col_to, csv_delta_col,
             delta_tracked, is_approved, approved_at,
             created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,1,1,?,?,?)""",
        [
            (dk, lbl, cat, gii, gid, cf, ct, dc, now, now, now)
            for dk, lbl, cat, gii, gid, cf, ct, dc in DRIVERS_SEED
        ],
    )
    conn.commit()


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def load_drivers(conn) -> list[dict]:
    """Return all delta_tracked=1 AND is_approved=1 drivers ordered by category."""
    cur = conn.cursor()
    cur.row_factory = sqlite3.Row
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT driver_key, label, category,
               good_if_increase, good_if_decrease,
               csv_col_from, csv_col_to, csv_delta_col
        FROM score_driver_reference
        WHERE delta_tracked = 1 AND is_approved = 1
        ORDER BY category, driver_key
    """)
    return [dict(r) for r in cur.fetchall()]


def main():
    os.makedirs(os.path.dirname(DRIVERS_DB), exist_ok=True)

    # Always recreate from scratch so seed is idempotent
    if os.path.exists(DRIVERS_DB):
        os.unlink(DRIVERS_DB)

    conn = sqlite3.connect(DRIVERS_DB)
    create_schema(conn)
    seed(conn)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM master_reference")
    n_master = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM score_driver_reference")
    n_drivers = cur.fetchone()[0]
    conn.close()

    print(f"Created: {DRIVERS_DB}")
    print(f"  master_reference:       {n_master} rows")
    print(f"  score_driver_reference: {n_drivers} rows (all approved)")
    print(f"  score_driver_thresholds: 0 rows (populate as needed)")


if __name__ == "__main__":
    main()
