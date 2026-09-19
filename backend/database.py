"""
Database Layer
==============
SQLite schema and CRUD helpers for the harmonization platform.
"""

import sqlite3
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "harmonize.db")


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with row factory for dict-like access."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cpse_id         TEXT NOT NULL,
            local_code      TEXT NOT NULL UNIQUE,
            raw_description TEXT NOT NULL,
            category        TEXT DEFAULT NULL,
            category_confidence TEXT DEFAULT NULL,
            classification_path TEXT DEFAULT NULL,
            canonical_description TEXT DEFAULT NULL,
            attributes      TEXT DEFAULT NULL,
            quantity_on_hand INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS match_pairs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_a_id   INTEGER NOT NULL REFERENCES items(id),
            item_b_id   INTEGER NOT NULL REFERENCES items(id),
            match_type  TEXT NOT NULL,
            confidence  REAL DEFAULT 0.0,
            evidence    TEXT DEFAULT '{}',
            status      TEXT DEFAULT 'pending',
            cnmc_id     TEXT DEFAULT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(item_a_id, item_b_id)
        );

        CREATE TABLE IF NOT EXISTS cnmc_codes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            cnmc_code   TEXT NOT NULL UNIQUE,
            item_ids    TEXT NOT NULL,
            canonical_description TEXT DEFAULT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            action      TEXT NOT NULL,
            reviewer    TEXT DEFAULT 'system',
            signal      TEXT DEFAULT NULL,
            details     TEXT DEFAULT NULL,
            match_pair_id INTEGER DEFAULT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );
    """)

    conn.commit()
    conn.close()
    logger.info(f"✅ Database initialized at {DB_PATH}")


def reset_db():
    """Drop and recreate all tables — used for fresh pipeline runs."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        DROP TABLE IF EXISTS audit_log;
        DROP TABLE IF EXISTS cnmc_codes;
        DROP TABLE IF EXISTS match_pairs;
        DROP TABLE IF EXISTS items;
    """)
    conn.commit()
    conn.close()
    init_db()
    logger.info("🔄 Database reset complete")


# ---------------------------------------------------------------------------
# Item CRUD
# ---------------------------------------------------------------------------

def insert_item(cpse_id: str, local_code: str, raw_description: str, quantity: int = 0) -> int:
    """Insert a raw item and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO items (cpse_id, local_code, raw_description, quantity_on_hand) VALUES (?, ?, ?, ?)",
        (cpse_id, local_code, raw_description, quantity)
    )
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return item_id


def update_item_classification(item_id: int, category: str, confidence: str, path: str):
    """Update classification results for an item."""
    conn = get_connection()
    conn.execute(
        "UPDATE items SET category=?, category_confidence=?, classification_path=? WHERE id=?",
        (category, confidence, path, item_id)
    )
    conn.commit()
    conn.close()


def update_item_attributes(item_id: int, attributes: dict, canonical_desc: str):
    """Update extracted attributes and canonical description."""
    conn = get_connection()
    conn.execute(
        "UPDATE items SET attributes=?, canonical_description=? WHERE id=?",
        (json.dumps(attributes), canonical_desc, item_id)
    )
    conn.commit()
    conn.close()


def get_all_items() -> list:
    """Return all items as list of dicts."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM items ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_items_by_category(category: str) -> list:
    """Return items filtered by category."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM items WHERE category=? ORDER BY id", (category,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Match Pairs CRUD
# ---------------------------------------------------------------------------

def insert_match_pair(item_a_id: int, item_b_id: int, match_type: str,
                      confidence: float, evidence: dict, status: str = 'pending') -> int:
    """Insert a match pair result."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT OR IGNORE INTO match_pairs
           (item_a_id, item_b_id, match_type, confidence, evidence, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (item_a_id, item_b_id, match_type, confidence, json.dumps(evidence), status)
    )
    conn.commit()
    pair_id = cursor.lastrowid
    conn.close()
    return pair_id


def get_pending_reviews() -> list:
    """Get all pending match pairs with item details."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT mp.id, mp.match_type, mp.confidence, mp.evidence, mp.status, mp.cnmc_id,
               a.cpse_id as cpse_a, a.local_code as code_a, a.raw_description as desc_a,
               a.canonical_description as canon_a, a.attributes as attrs_a,
               b.cpse_id as cpse_b, b.local_code as code_b, b.raw_description as desc_b,
               b.canonical_description as canon_b, b.attributes as attrs_b
        FROM match_pairs mp
        JOIN items a ON mp.item_a_id = a.id
        JOIN items b ON mp.item_b_id = b.id
        ORDER BY mp.confidence DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_matches_by_status(status: str) -> list:
    """Get match pairs filtered by status."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT mp.id, mp.match_type, mp.confidence, mp.evidence, mp.status, mp.cnmc_id,
               a.cpse_id as cpse_a, a.local_code as code_a, a.raw_description as desc_a,
               a.canonical_description as canon_a,
               b.cpse_id as cpse_b, b.local_code as code_b, b.raw_description as desc_b,
               b.canonical_description as canon_b
        FROM match_pairs mp
        JOIN items a ON mp.item_a_id = a.id
        JOIN items b ON mp.item_b_id = b.id
        WHERE mp.status = ? OR (? = 'approved' AND mp.status = 'auto-approved')
        ORDER BY mp.confidence DESC
    """, (status, status)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Approve / Reject / CNMC
# ---------------------------------------------------------------------------

def get_next_cnmc_code() -> str:
    """Generate the next auto-incrementing CNMC code."""
    conn = get_connection()
    row = conn.execute("SELECT MAX(id) as max_id FROM cnmc_codes").fetchone()
    conn.close()
    next_id = (row["max_id"] or 0) + 1
    return f"CNMC-{next_id:06d}"


def approve_match(pair_id: int, reviewer: str = "demo_user", status: str = "approved") -> str:
    """Approve a match pair: assign CNMC, update audit log."""
    conn = get_connection()

    # Get the match pair
    pair = conn.execute("SELECT * FROM match_pairs WHERE id=?", (pair_id,)).fetchone()
    if not pair:
        conn.close()
        raise ValueError(f"Match pair {pair_id} not found")

    # Get or create CNMC code
    cnmc_code = get_next_cnmc_code()

    # Get both item IDs
    item_ids = json.dumps([pair["item_a_id"], pair["item_b_id"]])

    # Get canonical description from item A
    item_a = conn.execute("SELECT canonical_description FROM items WHERE id=?",
                          (pair["item_a_id"],)).fetchone()
    canon_desc = item_a["canonical_description"] if item_a else ""

    # Insert CNMC code
    conn.execute(
        "INSERT INTO cnmc_codes (cnmc_code, item_ids, canonical_description) VALUES (?, ?, ?)",
        (cnmc_code, item_ids, canon_desc)
    )

    # Update match pair
    conn.execute(
        "UPDATE match_pairs SET status=?, cnmc_id=? WHERE id=?",
        (status, cnmc_code, pair_id)
    )

    # Audit log
    conn.execute(
        """INSERT INTO audit_log (action, reviewer, signal, details, match_pair_id)
           VALUES (?, ?, ?, ?, ?)""",
        ("approved", reviewer, "human", json.dumps({"cnmc_code": cnmc_code}), pair_id)
    )

    conn.commit()
    conn.close()

    logger.info(f"✅ Match pair {pair_id} approved -> {cnmc_code} by {reviewer}")
    return cnmc_code


def reject_match(pair_id: int, reviewer: str = "demo_user"):
    """Reject a match pair, log the decision."""
    conn = get_connection()

    conn.execute("UPDATE match_pairs SET status='rejected' WHERE id=?", (pair_id,))

    conn.execute(
        """INSERT INTO audit_log (action, reviewer, signal, details, match_pair_id)
           VALUES (?, ?, ?, ?, ?)""",
        ("rejected", reviewer, "human", json.dumps({"reason": "Manual rejection"}), pair_id)
    )

    conn.commit()
    conn.close()
    logger.info(f"❌ Match pair {pair_id} rejected by {reviewer}")


# ---------------------------------------------------------------------------
# Dashboard / Stats
# ---------------------------------------------------------------------------

def get_dashboard_stats() -> dict:
    """Compute dashboard statistics."""
    conn = get_connection()

    total_items = conn.execute("SELECT COUNT(*) as c FROM items").fetchone()["c"]
    total_cnmc = conn.execute("SELECT COUNT(*) as c FROM cnmc_codes").fetchone()["c"]
    total_matches = conn.execute("SELECT COUNT(*) as c FROM match_pairs").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) as c FROM match_pairs WHERE status='pending'").fetchone()["c"]
    approved = conn.execute("SELECT COUNT(*) as c FROM match_pairs WHERE status IN ('approved', 'auto-approved', 'Auto-Approved')").fetchone()["c"]
    rejected = conn.execute("SELECT COUNT(*) as c FROM match_pairs WHERE status='rejected'").fetchone()["c"]

    # Match type distribution
    type_dist = conn.execute(
        "SELECT match_type, COUNT(*) as c FROM match_pairs GROUP BY match_type"
    ).fetchall()

    # Category distribution
    cat_dist = conn.execute(
        "SELECT category, COUNT(*) as c FROM items WHERE category IS NOT NULL GROUP BY category"
    ).fetchall()

    conn.close()

    # Initialize with all 5 types to ensure empty bars aren't dropped
    dist = {
        "Identical": 0,
        "Duplicate": 0,
        "Near-Duplicate": 0,
        "Functionally Equivalent Candidate": 0,
        "No Match": 0
    }
    for r in type_dist:
        dist[r["match_type"]] = r["c"]

    return {
        "total_raw_items": total_items,
        "total_cnmc_codes": total_cnmc,
        "total_match_pairs": total_matches,
        "pending_reviews": pending,
        "approved_matches": approved,
        "rejected_matches": rejected,
        "match_type_distribution": dist,
        "category_distribution": {r["category"]: r["c"] for r in cat_dist},
    }


def get_audit_log() -> list:
    """Return all audit log entries."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_cnmc_cross_reference() -> list:
    """Return CNMC cross-reference with linked item details."""
    conn = get_connection()
    cnmc_rows = conn.execute("SELECT * FROM cnmc_codes ORDER BY id").fetchall()
    result = []
    for cnmc in cnmc_rows:
        item_ids = json.loads(cnmc["item_ids"])
        items = []
        for iid in item_ids:
            item = conn.execute("SELECT cpse_id, local_code, raw_description, quantity_on_hand FROM items WHERE id=?",
                                (iid,)).fetchone()
            if item:
                items.append(dict(item))
        result.append({
            "cnmc_code": cnmc["cnmc_code"],
            "canonical_description": cnmc["canonical_description"],
            "linked_items": items,
            "created_at": cnmc["created_at"],
        })
    conn.close()
    return result
