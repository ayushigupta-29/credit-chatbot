"""
DB Module — credit-chatbot personal credit data
-------------------------------------------------
Handles encrypted SQLite for per-user bureau snapshots, deltas,
segment patterns, and consent records.

The DB is never written to disk in plaintext.
Load/save flow:
  load_db()  → decrypt data/credit_data.db.enc → sqlite3.connect(":memory:")
  save_db()  → in-memory SQLite → bytes → encrypt → data/credit_data.db.enc
"""

import os
import sqlite3
import tempfile

from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_ENC_PATH = os.path.join(BASE_DIR, "data", "credit_data.db.enc")

load_dotenv(os.path.join(BASE_DIR, ".env"))
_KEY = os.environ.get("KB_ENCRYPTION_KEY")


def _get_fernet():
    from cryptography.fernet import Fernet
    if not _KEY:
        raise RuntimeError("KB_ENCRYPTION_KEY not found in .env")
    return Fernet(_KEY.encode())


# ── Schema ─────────────────────────────────────────────────────────────────────

def create_schema(conn):
    """Create all 4 tables and immutability triggers for created_at."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS customer_scrub_snapshot (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_phone   TEXT    NOT NULL,
            scrub_date       TEXT    NOT NULL,
            score            INTEGER,
            band             TEXT,
            total_accounts   INTEGER,
            active_accounts  INTEGER,
            has_dpd30_12m    INTEGER,
            has_dpd60_24m    INTEGER,
            has_dpd90_36m    INTEGER,
            has_npa          INTEGER,
            has_writeoff     INTEGER,
            cc_util_pct      REAL,
            enq_6m           INTEGER,
            enq_12m          INTEGER,
            created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
        );

        CREATE TABLE IF NOT EXISTS customer_scrub_delta (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_phone TEXT    NOT NULL,
            scrub_from     TEXT    NOT NULL,
            scrub_to       TEXT    NOT NULL,
            score_from     INTEGER,
            score_to       INTEGER,
            score_delta    INTEGER,
            segment        TEXT,
            driver         TEXT    NOT NULL,
            value_from     TEXT,
            value_to       TEXT,
            delta_value    REAL,
            direction      TEXT,
            created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
        );

        CREATE TABLE IF NOT EXISTS segment_driver_patterns (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            scrub_from    TEXT    NOT NULL,
            scrub_to      TEXT    NOT NULL,
            segment       TEXT    NOT NULL,
            driver        TEXT    NOT NULL,
            pct_flag_from REAL,
            pct_flag_to   REAL,
            median_delta  REAL,
            score_corr    REAL,
            created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
        );

        CREATE TABLE IF NOT EXISTS customer_consents (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_phone TEXT    NOT NULL,
            consent_type   TEXT    NOT NULL,
            consent_given  INTEGER NOT NULL,
            consent_text   TEXT,
            session_id     TEXT,
            created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
        );

        -- Immutability triggers: prevent created_at from being modified
        CREATE TRIGGER IF NOT EXISTS protect_snapshot_created_at
        BEFORE UPDATE ON customer_scrub_snapshot
        BEGIN
            SELECT RAISE(ABORT, 'created_at is immutable')
            WHERE NEW.created_at != OLD.created_at;
        END;

        CREATE TRIGGER IF NOT EXISTS protect_delta_created_at
        BEFORE UPDATE ON customer_scrub_delta
        BEGIN
            SELECT RAISE(ABORT, 'created_at is immutable')
            WHERE NEW.created_at != OLD.created_at;
        END;

        CREATE TRIGGER IF NOT EXISTS protect_patterns_created_at
        BEFORE UPDATE ON segment_driver_patterns
        BEGIN
            SELECT RAISE(ABORT, 'created_at is immutable')
            WHERE NEW.created_at != OLD.created_at;
        END;

        CREATE TRIGGER IF NOT EXISTS protect_consents_created_at
        BEFORE UPDATE ON customer_consents
        BEGIN
            SELECT RAISE(ABORT, 'created_at is immutable')
            WHERE NEW.created_at != OLD.created_at;
        END;
    """)
    conn.commit()


# ── Load / Save ────────────────────────────────────────────────────────────────

def load_db() -> sqlite3.Connection:
    """
    Decrypt data/credit_data.db.enc and load into an in-memory SQLite connection.
    If the file doesn't exist yet, returns an empty in-memory DB with schema ready.
    The encrypted file is decrypted to a short-lived temp file, then backed up
    to memory, then the temp file is deleted.
    """
    fernet = _get_fernet()

    if not os.path.exists(DB_ENC_PATH):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        return conn

    with open(DB_ENC_PATH, "rb") as f:
        encrypted_data = f.read()
    db_bytes = fernet.decrypt(encrypted_data)

    # Write to a temp file, backup to memory, then delete temp file
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    try:
        with os.fdopen(tmp_fd, "wb") as tmp_f:
            tmp_f.write(db_bytes)
        file_conn = sqlite3.connect(tmp_path)
        mem_conn = sqlite3.connect(":memory:")
        mem_conn.row_factory = sqlite3.Row
        file_conn.backup(mem_conn)
        file_conn.close()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return mem_conn


def save_db(conn: sqlite3.Connection):
    """
    Serialize the in-memory SQLite DB to bytes, encrypt with Fernet,
    and write to data/credit_data.db.enc.
    Plaintext bytes are only in a short-lived temp file, then deleted.
    """
    os.makedirs(os.path.dirname(DB_ENC_PATH), exist_ok=True)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    try:
        os.close(tmp_fd)
        file_conn = sqlite3.connect(tmp_path)
        conn.backup(file_conn)
        file_conn.close()
        with open(tmp_path, "rb") as f:
            db_bytes = f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    fernet = _get_fernet()
    encrypted = fernet.encrypt(db_bytes)
    with open(DB_ENC_PATH, "wb") as f:
        f.write(encrypted)


# ── Query helpers ──────────────────────────────────────────────────────────────

def get_user_snapshot(phone: str, conn: sqlite3.Connection) -> dict | None:
    """Return the latest scrub snapshot row for a user, or None if not found."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM customer_scrub_snapshot
        WHERE customer_phone = ?
        ORDER BY scrub_date DESC
        LIMIT 1
        """,
        (phone,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_user_deltas(phone: str, conn: sqlite3.Connection) -> list[dict]:
    """Return all delta rows for a user, ordered by most recent scrub_to first."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM customer_scrub_delta
        WHERE customer_phone = ?
        ORDER BY scrub_to DESC, driver
        """,
        (phone,),
    )
    return [dict(row) for row in cur.fetchall()]


def get_segment_patterns(conn: sqlite3.Connection) -> list[dict]:
    """Return all segment driver pattern rows."""
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM segment_driver_patterns ORDER BY segment, driver"
    )
    return [dict(row) for row in cur.fetchall()]


def save_consent(
    phone: str,
    consent_type: str,
    given: bool,
    text: str,
    session_id: str,
    conn: sqlite3.Connection,
):
    """Insert a consent record. Caller must call save_db() to persist."""
    conn.execute(
        """
        INSERT INTO customer_consents
            (customer_phone, consent_type, consent_given, consent_text, session_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (phone, consent_type, 1 if given else 0, text, session_id),
    )
    conn.commit()


# ── User context builder ───────────────────────────────────────────────────────

def build_user_context(phone: str, conn: sqlite3.Connection) -> dict | None:
    """
    Build a context dict for RAG injection from the user's snapshot + deltas.
    Returns None if the user is not in the DB.

    The returned dict is plain Python (no SQLite objects) — safe for
    Streamlit session state storage.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM customer_scrub_snapshot
        WHERE customer_phone = ?
        ORDER BY scrub_date
        """,
        (phone,),
    )
    snapshots = [dict(row) for row in cur.fetchall()]

    if not snapshots:
        return None

    latest = snapshots[-1]
    deltas = get_user_deltas(phone, conn)

    # Derive score_from / score_delta / segment from deltas or older snapshot
    score_from = None
    score_delta = None
    segment = None

    if deltas:
        score_from  = deltas[0].get("score_from")
        score_delta = deltas[0].get("score_delta")
        segment     = deltas[0].get("segment")
    elif len(snapshots) >= 2:
        score_from  = snapshots[0].get("score")
        score_to    = latest.get("score")
        score_delta = (score_to - score_from) if (score_to and score_from) else None

    return {
        "score_to":      latest.get("score"),
        "band_to":       latest.get("band"),
        "score_from":    score_from,
        "score_delta":   score_delta,
        "segment":       segment,
        "has_dpd30_12m": bool(latest.get("has_dpd30_12m")),
        "has_dpd60_24m": bool(latest.get("has_dpd60_24m")),
        "has_dpd90_36m": bool(latest.get("has_dpd90_36m")),
        "has_npa":       bool(latest.get("has_npa")),
        "has_writeoff":  bool(latest.get("has_writeoff")),
        "cc_util_pct":   latest.get("cc_util_pct"),
        "enq_6m":        latest.get("enq_6m"),
        "deltas": [
            {
                "driver":      d["driver"],
                "value_from":  d.get("value_from"),
                "value_to":    d.get("value_to"),
                "delta_value": d.get("delta_value"),
                "direction":   d.get("direction"),
            }
            for d in deltas
        ],
    }
