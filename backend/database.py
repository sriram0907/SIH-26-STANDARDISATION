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

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "harmonize.db")


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
            created_at  TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS procurement_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id         INTEGER REFERENCES items(id),
            cpse_id         TEXT NOT NULL,
            local_code      TEXT NOT NULL,
            quantity_needed INTEGER NOT NULL,
            supplier        TEXT DEFAULT NULL,
            request_date    TEXT DEFAULT NULL,
            created_at      TEXT DEFAULT (datetime('now'))
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
        DROP TABLE IF EXISTS procurement_requests;
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
    
    # First, get a mapping of item_id -> cnmc_code
    cnmc_rows = conn.execute("SELECT cnmc_code, item_ids FROM cnmc_codes").fetchall()
    item_to_cnmc = {}
    for r in cnmc_rows:
        try:
            for item_id in json.loads(r["item_ids"]):
                item_to_cnmc[item_id] = r["cnmc_code"]
        except json.JSONDecodeError:
            pass

    rows = conn.execute("""
        SELECT mp.id, mp.match_type, mp.confidence, mp.evidence, mp.status, mp.cnmc_id,
               mp.item_a_id, mp.item_b_id,
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
    
    results = [dict(r) for r in rows]
    for res in results:
        res["cnmc_a"] = item_to_cnmc.get(res["item_a_id"])
        res["cnmc_b"] = item_to_cnmc.get(res["item_b_id"])
    return results


def get_matches_by_status(status: str) -> list:
    """Get match pairs filtered by status."""
    conn = get_connection()
    
    # First, get a mapping of item_id -> cnmc_code
    cnmc_rows = conn.execute("SELECT cnmc_code, item_ids FROM cnmc_codes").fetchall()
    item_to_cnmc = {}
    for r in cnmc_rows:
        try:
            for item_id in json.loads(r["item_ids"]):
                item_to_cnmc[item_id] = r["cnmc_code"]
        except json.JSONDecodeError:
            pass

    rows = conn.execute("""
        SELECT mp.id, mp.match_type, mp.confidence, mp.evidence, mp.status, mp.cnmc_id,
               mp.item_a_id, mp.item_b_id,
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
    
    results = [dict(r) for r in rows]
    for res in results:
        res["cnmc_a"] = item_to_cnmc.get(res["item_a_id"])
        res["cnmc_b"] = item_to_cnmc.get(res["item_b_id"])
    return results


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
    """Approve a match pair: assign or merge CNMC, update audit log.
    
    Uses union-find logic: if either item already belongs to an existing CNMC,
    merge into that CNMC. If both items belong to different CNMCs, merge the
    two CNMCs into one. Only creates a new CNMC if neither item has one yet.
    """
    conn = get_connection()

    # Get the match pair
    pair = conn.execute("SELECT * FROM match_pairs WHERE id=?", (pair_id,)).fetchone()
    if not pair:
        conn.close()
        raise ValueError(f"Match pair {pair_id} not found")

    item_a_id = pair["item_a_id"]
    item_b_id = pair["item_b_id"]

    # Find existing CNMCs that already contain either item
    all_cnmc_rows = conn.execute("SELECT * FROM cnmc_codes").fetchall()
    
    cnmc_for_a = None
    cnmc_for_b = None
    for cnmc_row in all_cnmc_rows:
        member_ids = json.loads(cnmc_row["item_ids"])
        if item_a_id in member_ids:
            cnmc_for_a = cnmc_row
        if item_b_id in member_ids:
            cnmc_for_b = cnmc_row

    # Get canonical description from item A
    item_a = conn.execute("SELECT canonical_description FROM items WHERE id=?",
                          (item_a_id,)).fetchone()
    canon_desc = item_a["canonical_description"] if item_a else ""

    if cnmc_for_a and cnmc_for_b:
        if cnmc_for_a["cnmc_code"] == cnmc_for_b["cnmc_code"]:
            # Both already in the same CNMC — just update the match pair
            cnmc_code = cnmc_for_a["cnmc_code"]
        else:
            # Merge: union both CNMCs into one (keep the earlier code)
            keep = cnmc_for_a
            discard = cnmc_for_b
            keep_ids = set(json.loads(keep["item_ids"]))
            discard_ids = set(json.loads(discard["item_ids"]))
            merged_ids = sorted(keep_ids | discard_ids)
            
            conn.execute("UPDATE cnmc_codes SET item_ids=? WHERE cnmc_code=?",
                         (json.dumps(merged_ids), keep["cnmc_code"]))
            # Re-point all match_pairs that referenced the discarded CNMC
            conn.execute("UPDATE match_pairs SET cnmc_id=? WHERE cnmc_id=?",
                         (keep["cnmc_code"], discard["cnmc_code"]))
            conn.execute("DELETE FROM cnmc_codes WHERE cnmc_code=?",
                         (discard["cnmc_code"],))
            cnmc_code = keep["cnmc_code"]
    elif cnmc_for_a:
        # Add item B into A's existing CNMC
        existing_ids = set(json.loads(cnmc_for_a["item_ids"]))
        existing_ids.add(item_b_id)
        conn.execute("UPDATE cnmc_codes SET item_ids=? WHERE cnmc_code=?",
                     (json.dumps(sorted(existing_ids)), cnmc_for_a["cnmc_code"]))
        cnmc_code = cnmc_for_a["cnmc_code"]
    elif cnmc_for_b:
        # Add item A into B's existing CNMC
        existing_ids = set(json.loads(cnmc_for_b["item_ids"]))
        existing_ids.add(item_a_id)
        conn.execute("UPDATE cnmc_codes SET item_ids=? WHERE cnmc_code=?",
                     (json.dumps(sorted(existing_ids)), cnmc_for_b["cnmc_code"]))
        cnmc_code = cnmc_for_b["cnmc_code"]
    else:
        # Neither item has a CNMC yet — create a new one
        cnmc_code = get_next_cnmc_code()
        item_ids = json.dumps(sorted([item_a_id, item_b_id]))
        conn.execute(
            "INSERT INTO cnmc_codes (cnmc_code, item_ids, canonical_description) VALUES (?, ?, ?)",
            (cnmc_code, item_ids, canon_desc)
        )

    # Update match pair
    conn.execute(
        "UPDATE match_pairs SET status=?, cnmc_id=? WHERE id=?",
        (status, cnmc_code, pair_id)
    )

    # Audit log — use Python datetime.now() so the timestamp reflects
    # the actual local wall-clock time, not UTC (SQLite's datetime('now') default).
    conn.execute(
        """INSERT INTO audit_log (action, reviewer, signal, details, match_pair_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("approved", reviewer, "human", json.dumps({"cnmc_code": cnmc_code}), pair_id,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )

    conn.commit()
    conn.close()

    logger.info(f"✅ Match pair {pair_id} approved -> {cnmc_code} by {reviewer}")
    return cnmc_code


def reject_match(pair_id: int, reviewer: str = "demo_user") -> dict:
    """Reject a match pair, assign individual CNMCs if missing, and log the decision."""
    conn = get_connection()

    pair = conn.execute("SELECT * FROM match_pairs WHERE id=?", (pair_id,)).fetchone()
    if not pair:
        conn.close()
        raise ValueError(f"Match pair {pair_id} not found")

    item_a_id = pair["item_a_id"]
    item_b_id = pair["item_b_id"]

    # Check for existing CNMCs
    all_cnmc_rows = conn.execute("SELECT * FROM cnmc_codes").fetchall()
    cnmc_for_a = None
    cnmc_for_b = None
    for cnmc_row in all_cnmc_rows:
        member_ids = json.loads(cnmc_row["item_ids"])
        if item_a_id in member_ids:
            cnmc_for_a = cnmc_row["cnmc_code"]
        if item_b_id in member_ids:
            cnmc_for_b = cnmc_row["cnmc_code"]

    if not cnmc_for_a:
        item_a = conn.execute("SELECT canonical_description FROM items WHERE id=?", (item_a_id,)).fetchone()
        canon_desc_a = item_a["canonical_description"] if item_a else ""
        cnmc_for_a = get_next_cnmc_code()
        conn.execute(
            "INSERT INTO cnmc_codes (cnmc_code, item_ids, canonical_description) VALUES (?, ?, ?)",
            (cnmc_for_a, json.dumps([item_a_id]), canon_desc_a)
        )

    if not cnmc_for_b:
        item_b = conn.execute("SELECT canonical_description FROM items WHERE id=?", (item_b_id,)).fetchone()
        canon_desc_b = item_b["canonical_description"] if item_b else ""
        cnmc_for_b = get_next_cnmc_code()
        conn.execute(
            "INSERT INTO cnmc_codes (cnmc_code, item_ids, canonical_description) VALUES (?, ?, ?)",
            (cnmc_for_b, json.dumps([item_b_id]), canon_desc_b)
        )

    conn.execute("UPDATE match_pairs SET status='rejected' WHERE id=?", (pair_id,))

    details = {
        "reason": "Manual rejection",
        "cnmc_a": cnmc_for_a,
        "cnmc_b": cnmc_for_b
    }

    conn.execute(
        """INSERT INTO audit_log (action, reviewer, signal, details, match_pair_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("rejected", reviewer, "human", json.dumps(details), pair_id,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )

    conn.commit()
    conn.close()
    logger.info(f"❌ Match pair {pair_id} rejected by {reviewer} (A: {cnmc_for_a}, B: {cnmc_for_b})")
    
    return {"cnmc_a": cnmc_for_a, "cnmc_b": cnmc_for_b}


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


def log_audit_event(action: str, reviewer: str, signal: str,
                    details: dict, match_pair_id: int = None):
    """Insert a single audit log row with a local-time timestamp.

    ``created_at`` is set explicitly via Python's ``datetime.now()`` so the
    recorded time is the host's local wall-clock time, not SQLite's UTC
    ``datetime('now')`` default.  Each call captures its own independent
    timestamp at the exact moment that action is logged.
    """
    conn = get_connection()
    conn.execute(
        """INSERT INTO audit_log (action, reviewer, signal, details, match_pair_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (action, reviewer, signal, json.dumps(details), match_pair_id,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()


def get_cnmc_cross_reference() -> list:
    """Return CNMC cross-reference with linked item details and underlying matches."""
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
                
        # Fetch the match pairs that formed this CNMC
        matches = conn.execute("SELECT * FROM match_pairs WHERE cnmc_id=? AND status IN ('approved', 'auto-approved')", (cnmc["cnmc_code"],)).fetchall()
        
        result.append({
            "cnmc_code": cnmc["cnmc_code"],
            "canonical_description": cnmc["canonical_description"],
            "linked_items": items,
            "matches": [dict(m) for m in matches],
            "created_at": cnmc["created_at"],
        })
    conn.close()
    return result


# ---------------------------------------------------------------------------
# Procurement Requests
# ---------------------------------------------------------------------------

def insert_procurement_request(item_id: int, cpse_id: str, local_code: str,
                                quantity_needed: int, supplier: str = None,
                                request_date: str = None):
    """Insert a procurement request row."""
    conn = get_connection()
    conn.execute(
        """INSERT INTO procurement_requests
           (item_id, cpse_id, local_code, quantity_needed, supplier, request_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (item_id, cpse_id, local_code, quantity_needed, supplier, request_date)
    )
    conn.commit()
    conn.close()


def get_procurement_intelligence() -> list:
    """Build procurement intelligence per CNMC group.

    For each CNMC, returns:
    - demand_items: CPSEs with active procurement requests
    - stock_items: CPSEs holding existing stock
    - stock_reuse_suggestions: messages when one CPSE needs and another holds
    - consolidation_opportunity: message when 2+ CPSEs have active demand
    """
    conn = get_connection()
    cnmc_rows = conn.execute("SELECT * FROM cnmc_codes ORDER BY id").fetchall()
    proc_rows = conn.execute("SELECT * FROM procurement_requests").fetchall()

    # Build item_id -> procurement requests mapping
    item_procurement = {}  # item_id -> list of procurement rows
    for pr in proc_rows:
        item_procurement.setdefault(pr["item_id"], []).append(dict(pr))

    result = []
    for cnmc in cnmc_rows:
        item_ids = json.loads(cnmc["item_ids"])
        demand_items = []
        stock_items = []

        for iid in item_ids:
            item = conn.execute(
                "SELECT id, cpse_id, local_code, raw_description, quantity_on_hand FROM items WHERE id=?",
                (iid,)
            ).fetchone()
            if not item:
                continue

            item_dict = dict(item)

            # Check if this item has procurement requests
            procs = item_procurement.get(iid, [])
            if procs:
                for pr in procs:
                    demand_items.append({
                        "cpse_id": item_dict["cpse_id"],
                        "local_code": item_dict["local_code"],
                        "quantity_needed": pr["quantity_needed"],
                        "supplier": pr.get("supplier"),
                        "request_date": pr.get("request_date"),
                    })

            # Stock is always reported from quantity_on_hand
            if item_dict.get("quantity_on_hand", 0) > 0:
                stock_items.append({
                    "cpse_id": item_dict["cpse_id"],
                    "local_code": item_dict["local_code"],
                    "quantity_on_hand": item_dict["quantity_on_hand"],
                })

        total_demand = sum(d["quantity_needed"] for d in demand_items)
        total_stock = sum(s["quantity_on_hand"] for s in stock_items)

        # Build the set of CPSEs that have active procurement needs.
        demand_cpses = {d["cpse_id"] for d in demand_items}

        # Build per-CPSE stock totals from real quantity_on_hand values only.
        stock_by_cpse = {}
        for s in stock_items:
            stock_by_cpse.setdefault(s["cpse_id"], 0)
            stock_by_cpse[s["cpse_id"]] += s["quantity_on_hand"]

        # --- Stock-reuse suggestions ---
        # A "get it from CPSE-Y" suggestion is valid ONLY when:
        #   • CPSE-Y has quantity_on_hand > 0  (real stock, not just a need), AND
        #   • CPSE-Y is NOT itself in demand_cpses (it is a genuine holder,
        #     not another CPSE that also has an unmet procurement request).
        # This prevents suggesting a transfer from a CPSE that only has an open
        # need recorded in procurement_requests but no actual on-hand inventory.
        stock_reuse_suggestions = []
        for d in demand_items:
            for s_cpse, s_qty in stock_by_cpse.items():
                if (
                    s_cpse != d["cpse_id"]
                    and s_qty > 0
                    and s_cpse not in demand_cpses  # genuine holder, not another needer
                ):
                    stock_reuse_suggestions.append(
                        f"{d['cpse_id']} needs {d['quantity_needed']} units — "
                        f"{s_cpse} already holds {s_qty} units of this material, "
                        f"consider internal transfer before new purchase"
                    )

        # Deduplicate suggestions (same CPSE pair may appear multiple times)
        stock_reuse_suggestions = list(dict.fromkeys(stock_reuse_suggestions))

        # --- Consolidation opportunity ---
        # Fires ONLY when:
        #   • 2+ distinct CPSEs have active demand for this CNMC, AND
        #   • There is NO CPSE outside the demand set that holds genuine stock
        #     (i.e., no stock-reuse transfer is possible).
        # This keeps the two paths mutually exclusive: if a genuine transfer
        # opportunity exists the reuse suggestion is shown; when everyone is a
        # needer (zero stock anywhere, or all holders are also needers) we
        # instead recommend a consolidated bulk purchase.
        has_external_stock = any(
            cpse not in demand_cpses and qty > 0
            for cpse, qty in stock_by_cpse.items()
        )
        consolidation_opportunity = None
        if len(demand_cpses) >= 2 and not has_external_stock:
            consolidation_opportunity = (
                f"Consolidated procurement opportunity: {total_demand} total units "
                f"needed across {len(demand_cpses)} CPSEs — consider bulk purchase/negotiation"
            )

        # Only include CNMC groups that have at least some demand or are interesting
        if demand_items or stock_reuse_suggestions or consolidation_opportunity:
            result.append({
                "cnmc_code": cnmc["cnmc_code"],
                "canonical_description": cnmc["canonical_description"],
                "demand_items": demand_items,
                "stock_items": stock_items,
                "total_demand": total_demand,
                "total_stock": total_stock,
                "stock_reuse_suggestions": stock_reuse_suggestions,
                "consolidation_opportunity": consolidation_opportunity,
            })

    conn.close()
    return result


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_items(query: str) -> list:
    """Search items by local_code, raw_description, standard attribute, or CNMC code.
    
    Returns matching items enriched with their CNMC membership info.
    """
    conn = get_connection()
    q = f"%{query}%"
    
    # Build item -> CNMC mapping (needed for both CNMC search and enrichment)
    cnmc_rows = conn.execute("SELECT * FROM cnmc_codes").fetchall()
    item_to_cnmc = {}
    for cnmc in cnmc_rows:
        item_ids = json.loads(cnmc["item_ids"])
        for iid in item_ids:
            item_to_cnmc[iid] = cnmc["cnmc_code"]

    # Check if the query matches a CNMC code directly
    cnmc_matched_ids = set()
    for cnmc in cnmc_rows:
        if query.upper() in cnmc["cnmc_code"].upper():
            member_ids = json.loads(cnmc["item_ids"])
            cnmc_matched_ids.update(member_ids)
    
    # Search local_code and raw_description
    rows = conn.execute("""
        SELECT * FROM items 
        WHERE local_code LIKE ? COLLATE NOCASE
           OR raw_description LIKE ? COLLATE NOCASE
        ORDER BY id
    """, (q, q)).fetchall()
    
    found_ids = {r["id"] for r in rows}
    
    # Add CNMC-matched items that weren't found by text search
    for iid in cnmc_matched_ids:
        if iid not in found_ids:
            item = conn.execute("SELECT * FROM items WHERE id=?", (iid,)).fetchone()
            if item:
                rows = list(rows) + [item]
                found_ids.add(iid)
    
    # Also search in JSON attributes for standard field
    all_items = conn.execute("SELECT * FROM items").fetchall()
    for item in all_items:
        if item["id"] in found_ids:
            continue
        attrs = json.loads(item["attributes"]) if item["attributes"] else {}
        # Search standard, diameter, size, pressure_rating
        for key in ["standard", "diameter", "size", "pressure_rating", "length"]:
            val = attrs.get(key, "")
            if val and query.upper() in str(val).upper():
                found_ids.add(item["id"])
                rows = list(rows) + [item]
                break
    
    results = []
    for r in rows:
        item = dict(r)
        item["cnmc_code"] = item_to_cnmc.get(item["id"])
        results.append(item)
    
    conn.close()
    return results
