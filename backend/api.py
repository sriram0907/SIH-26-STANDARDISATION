"""
FastAPI Backend — API Endpoints
================================
REST API for the harmonization platform.
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend import database, pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Material Code Harmonization API",
    description="AI-driven material code harmonization platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    database.init_db()
    logger.info("🚀 API server started")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

@app.post("/api/run-pipeline")
async def run_pipeline_endpoint():
    """Trigger the full harmonization pipeline."""
    try:
        result = pipeline.run_pipeline()
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@app.get("/api/items")
async def get_items():
    """List all processed items."""
    items = database.get_all_items()
    return {"items": items, "count": len(items)}


@app.get("/api/items/category/{category}")
async def get_items_by_category(category: str):
    """List items filtered by category."""
    items = database.get_items_by_category(category)
    return {"items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Match Pairs
# ---------------------------------------------------------------------------

@app.get("/api/matches")
async def get_matches(status: str = None):
    """List match pairs, optionally filtered by status."""
    if status:
        matches = database.get_matches_by_status(status)
    else:
        matches = database.get_pending_reviews()
    return {"matches": matches, "count": len(matches)}


@app.post("/api/matches/{pair_id}/approve")
async def approve_match(pair_id: int, reviewer: str = "demo_user"):
    """Approve a match pair and assign a CNMC code."""
    try:
        cnmc_code = database.approve_match(pair_id, reviewer)
        return {"status": "approved", "cnmc_code": cnmc_code, "pair_id": pair_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/matches/{pair_id}/reject")
async def reject_match(pair_id: int, reviewer: str = "demo_user"):
    """Reject a match pair."""
    try:
        database.reject_match(pair_id, reviewer)
        return {"status": "rejected", "pair_id": pair_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/api/dashboard")
async def get_dashboard():
    """Get dashboard statistics."""
    stats = database.get_dashboard_stats()
    return stats


@app.get("/api/audit-log")
async def get_audit_log():
    """Get audit log entries."""
    log = database.get_audit_log()
    return {"log": log, "count": len(log)}


@app.get("/api/cnmc-codes")
async def get_cnmc_codes():
    """Get CNMC cross-reference table."""
    codes = database.get_cnmc_cross_reference()
    return {"codes": codes, "count": len(codes)}


@app.get("/api/procurement-intelligence")
async def get_procurement_intelligence():
    """Get procurement intelligence data per CNMC group."""
    data = database.get_procurement_intelligence()
    return {"cnmc_groups": data, "count": len(data)}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@app.get("/api/search")
async def search_materials(q: str = ""):
    """Search items by local code, description, or standard."""
    if not q or len(q.strip()) < 2:
        return {"items": [], "count": 0}
    items = database.search_items(q.strip())
    return {"items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Material Code Harmonization API"}
