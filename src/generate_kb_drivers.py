"""
Generate KB Score Driver Reference Doc
----------------------------------------
Generates knowledge_base/09_score_driver_reference.md from the approved
drivers in data/score_drivers.db (once Points 1 & 2 are implemented).

Until score_drivers.db exists, generates from the hardcoded driver list below.

Run from project root:
    python src/generate_kb_drivers.py

After running, re-ingest to update ChromaDB:
    python src/ingest.py
"""

import os
import sqlite3

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVERS_DB  = os.path.join(BASE_DIR, "data", "score_drivers.db")
OUTPUT_PATH = os.path.join(BASE_DIR, "knowledge_base", "09_score_driver_reference.md")

# ── Hardcoded fallback (used until score_drivers.db exists) ───────────────────
# Columns: driver_key, label, category, good_if_increase, good_if_decrease
FALLBACK_DRIVERS = [
    ("has_dpd30_12m",    "DPD 30+ (last 12 months)",             "dpd",         0, 1),
    ("has_dpd60_24m",    "DPD 60+ (last 24 months)",             "dpd",         0, 1),
    ("has_dpd90_36m",    "DPD 90+ (last 36 months)",             "dpd",         0, 1),
    ("has_npa",          "NPA (non-performing asset) account",   "dpd",         0, 1),
    ("has_writeoff",     "Write-off or settlement on file",      "dpd",         0, 1),
    ("cc_util_pct",      "Credit card / OD utilisation %",       "utilisation", 0, 1),
    ("enq_6m",           "Enquiries in last 6 months",           "enquiries",   0, 1),
    ("enq_12m",          "Enquiries in last 12 months",          "enquiries",   0, 1),
    ("num_dpd30_12m",    "Number of DPD 30+ incidents (12m)",    "dpd",         0, 1),
    ("total_accounts",   "Total number of credit accounts",      "accounts",    1, 0),
    ("active_accounts",  "Number of active accounts",            "accounts",    1, 2),
    ("total_outstanding","Total outstanding loan/card balance",  "utilisation", 0, 1),
]

# ── Direction labels ───────────────────────────────────────────────────────────
_DIRECTION_LABEL = {0: "Bad for score", 1: "Good for score", 2: "No effect"}

# ── Category descriptions ──────────────────────────────────────────────────────
CATEGORY_HEADINGS = {
    "dpd":         "Payment Delinquency (DPD / NPA / Write-off)",
    "utilisation": "Credit Utilisation and Outstanding Balance",
    "enquiries":   "Credit Enquiries",
    "accounts":    "Account Counts",
}


def load_from_db():
    """Load approved drivers from score_drivers.db. Returns None if DB not ready."""
    if not os.path.exists(DRIVERS_DB):
        return None
    conn = sqlite3.connect(DRIVERS_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT driver_key, label, category, good_if_increase, good_if_decrease
            FROM score_driver_reference
            WHERE is_approved = 1
            ORDER BY category, driver_key
        """)
        rows = cur.fetchall()
        conn.close()
        return [(r["driver_key"], r["label"], r["category"],
                 r["good_if_increase"], r["good_if_decrease"]) for r in rows]
    except Exception:
        conn.close()
        return None


def generate_doc(drivers: list) -> str:
    lines = [
        "# Credit Score Driver Reference",
        "",
        "This document lists every factor tracked in our bureau data that affects a credit score.",
        "For each factor, both directions of change are explicitly stated.",
        "Do not infer or assume the opposite of any statement — both directions are written out here.",
        "",
        "---",
        "",
    ]

    by_category = {}
    for row in drivers:
        driver_key, label, category, good_if_increase, good_if_decrease = row
        by_category.setdefault(category, []).append(row)

    for category, heading in CATEGORY_HEADINGS.items():
        if category not in by_category:
            continue
        lines.append(f"## {heading}")
        lines.append("")
        for driver_key, label, _, good_if_increase, good_if_decrease in by_category[category]:
            lines.append(f"### {label}")
            inc_label = _DIRECTION_LABEL[good_if_increase]
            dec_label = _DIRECTION_LABEL[good_if_decrease]
            lines.append(f"- **If this value increases:** {inc_label}")
            lines.append(f"- **If this value decreases:** {dec_label}")
            # Add plain-English explanation
            lines.append(_plain_english(driver_key, good_if_increase, good_if_decrease))
            lines.append("")

    return "\n".join(lines)


def _plain_english(driver_key: str, good_if_increase: int, good_if_decrease: int) -> str:
    """One-line plain-English explanation per driver."""
    explanations = {
        "has_dpd30_12m":     "- A DPD flag means at least one payment was 30+ days late in the last 12 months. Having this flag (value = 1) is bad. Clearing it (1 → 0) is good. Setting it (0 → 1) is bad.",
        "has_dpd60_24m":     "- A DPD 60+ flag means at least one payment was 60+ days late in the last 24 months. Clearing it improves the score. Setting it lowers the score.",
        "has_dpd90_36m":     "- A DPD 90+ flag means at least one payment was 90+ days late in the last 36 months. Clearing it improves the score. Setting it lowers the score.",
        "has_npa":           "- An NPA flag means at least one account has been classified as non-performing. Clearing it is good. Setting it is bad.",
        "has_writeoff":      "- A write-off/settlement flag means a lender wrote off a debt or accepted a partial settlement. Clearing it improves the score. Setting it lowers the score.",
        "cc_util_pct":       "- Credit utilisation is the % of available credit limit currently used. Lower is better (ideally under 30%). Higher utilisation signals financial stress. A decrease is good; an increase is bad.",
        "enq_6m":            "- Each loan or card application triggers a hard enquiry. More enquiries in 6 months signals credit-seeking behaviour and lowers the score. Fewer enquiries is better.",
        "enq_12m":           "- Same as enquiries last 6 months but over a 12-month window. Fewer enquiries is better.",
        "num_dpd30_12m":     "- The count of DPD 30+ incidents (not just whether one exists). More incidents means more missed payments — worse. Fewer incidents means payment behaviour is improving.",
        "total_accounts":    "- More accounts (over time) shows experience managing different types of credit. An increase is generally positive. A sharp decrease means accounts were closed, which can hurt credit mix and age.",
        "active_accounts":   "- More active accounts shows ongoing credit management. An increase is positive. A decrease has no standard effect — it could mean a loan was paid off (neutral-positive) or a card was closed (slightly negative).",
        "total_outstanding": "- Total outstanding balance across all loans and cards. A decrease means debt is being paid down, which is positive. An increase means more debt, which can be negative.",
    }
    return explanations.get(driver_key, "")


def main():
    drivers = load_from_db()
    source = "score_drivers.db"
    if drivers is None:
        drivers = FALLBACK_DRIVERS
        source = "hardcoded fallback"
    print(f"Loaded {len(drivers)} approved drivers from {source}")

    doc = generate_doc(drivers)
    with open(OUTPUT_PATH, "w") as f:
        f.write(doc)

    print(f"Written: {OUTPUT_PATH}")
    print("Next step: python src/ingest.py")


if __name__ == "__main__":
    main()
