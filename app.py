"""
Streamlit UI — Review Queue + Dashboard
=========================================
Single-page app with sidebar navigation for the harmonization platform.
Communicates with the FastAPI backend.
"""

import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="Material Code Harmonization Platform",
    page_icon="🔩",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS for premium styling
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    /* Main page styling */
    .main .block-container {
        padding-top: 1.5rem;
        max-width: 1400px;
    }

    /* Header styling */
    .platform-header {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        padding: 1.8rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .platform-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    .platform-header p {
        margin: 0.3rem 0 0 0;
        opacity: 0.8;
        font-size: 0.95rem;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 1.2rem 1.5rem;
        border-radius: 12px;
        border-left: 4px solid;
        color: white;
        box-shadow: 0 4px 16px rgba(0,0,0,0.2);
    }
    .metric-card.blue   { border-left-color: #4facfe; }
    .metric-card.green  { border-left-color: #43e97b; }
    .metric-card.purple { border-left-color: #a18cd1; }
    .metric-card.orange { border-left-color: #ffa751; }
    .metric-card.red    { border-left-color: #ff6b6b; }
    .metric-card .metric-value {
        font-size: 2rem;
        font-weight: 700;
        margin: 0.3rem 0;
    }
    .metric-card .metric-label {
        font-size: 0.85rem;
        opacity: 0.7;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Match type badges */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-identical    { background: #43e97b33; color: #43e97b; border: 1px solid #43e97b55; }
    .badge-duplicate    { background: #4facfe33; color: #4facfe; border: 1px solid #4facfe55; }
    .badge-near-dup     { background: #ffa75133; color: #ffa751; border: 1px solid #ffa75155; }
    .badge-func-equiv   { background: #a18cd133; color: #a18cd1; border: 1px solid #a18cd155; }
    .badge-no-match     { background: #ff6b6b33; color: #ff6b6b; border: 1px solid #ff6b6b55; }

    /* Evidence box */
    .evidence-box {
        background: #1a1a2e;
        border: 1px solid #2d2d44;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        color: #e0e0e0;
    }
    .attr-match   { color: #43e97b; }
    .attr-differ  { color: #ff6b6b; }

    /* Status badges */
    .status-pending  { color: #ffa751; }
    .status-approved { color: #43e97b; }
    .status-auto-approved { color: #43e97b; }
    .status-rejected { color: #ff6b6b; }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0c29 0%, #1a1a2e 100%);
    }
    [data-testid="stSidebar"] .stMarkdown {
        color: #e0e0e0;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def api_get(endpoint: str):
    """Make a GET request to the API."""
    try:
        resp = requests.get(f"{API_BASE}{endpoint}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot connect to API server. Make sure FastAPI is running on port 8000.")
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_post(endpoint: str, params: dict = None):
    """Make a POST request to the API."""
    try:
        resp = requests.post(f"{API_BASE}{endpoint}", params=params, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot connect to API server. Make sure FastAPI is running on port 8000.")
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def get_badge_class(match_type: str) -> str:
    """Map match type to CSS badge class."""
    mapping = {
        "Identical": "badge-identical",
        "Duplicate": "badge-duplicate",
        "Near-Duplicate": "badge-near-dup",
        "Functionally Equivalent Candidate": "badge-func-equiv",
        "No Match": "badge-no-match",
    }
    return mapping.get(match_type, "")


def render_evidence_details(match):
    """Render the evidence details for a match pair in an expander."""
    with st.expander(f"📄 Evidence Details — Pair #{match['id']}", expanded=False):
        evidence = match.get("evidence", {})
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence)
            except json.JSONDecodeError:
                evidence = {}

        rule_ev = evidence.get("rule_engine", {})
        ai_ev = evidence.get("ai_matching", {})

        col_ev1, col_ev2 = st.columns(2)

        with col_ev1:
            st.markdown("**Rule Engine Results:**")
            passed = rule_ev.get("passed", False)
            st.markdown(f"- Hard constraints: {'✅ PASSED' if passed else '❌ FAILED'}", unsafe_allow_html=True)
            if rule_ev.get("matched_attributes"):
                st.markdown(f"- Matched: {', '.join(rule_ev['matched_attributes'])}", unsafe_allow_html=True)
            if rule_ev.get("failed_attributes"):
                st.markdown(f"- ❌ Differing: **{', '.join(rule_ev['failed_attributes'])}**", unsafe_allow_html=True)
            if rule_ev.get("non_critical_diffs"):
                st.markdown(f"- ⚠️ Non-critical diffs: {', '.join(rule_ev['non_critical_diffs'])}", unsafe_allow_html=True)
            if rule_ev.get("interchangeable_diffs"):
                st.markdown(f"- 🔄 Interchangeable diffs: {', '.join(rule_ev['interchangeable_diffs'])}", unsafe_allow_html=True)

            # Attribute comparison table
            attr_details = rule_ev.get("attribute_details", {})
            if attr_details:
                st.markdown("**Attribute Comparison:**")
                for attr, detail in attr_details.items():
                    icon = "✅" if detail.get("match") else "❌"
                    st.markdown(f"  {icon} `{attr}`: `{detail.get('item_a', 'N/A')}` vs `{detail.get('item_b', 'N/A')}`", unsafe_allow_html=True)

        with col_ev2:
            st.markdown("**AI Matching Scores:**")
            st.markdown(f"- Cosine similarity: `{ai_ev.get('cosine_similarity', 'N/A')}`", unsafe_allow_html=True)
            st.markdown(f"- Fuzz ratio: `{ai_ev.get('fuzz_ratio', 'N/A')}`", unsafe_allow_html=True)
            st.markdown(f"- Combined score: `{ai_ev.get('combined_score', 'N/A')}`", unsafe_allow_html=True)
            st.markdown(f"- Signal: `{evidence.get('signal', 'N/A')}`", unsafe_allow_html=True)


def render_header():
    """Render the platform header."""
    st.markdown("""
    <div class="platform-header">
        <h1>🔩 Material Code Harmonization Platform</h1>
        <p>AI-driven CPSE material description standardization & cross-reference engine</p>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## ⚙️ Navigation")
    page = st.radio(
        "Select View",
        ["🏠 Dashboard", "🔍 Material Search", "📋 Review Queue", "🔗 CNMC Cross-Reference",
         "📈 Procurement Intelligence", "📦 Inventory Visibility", "🏛️ Legacy Code Manager",
         "📜 Audit Log"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("### 🚀 Pipeline Controls")

    if st.button("▶️ Run Full Pipeline", use_container_width=True, type="primary"):
        with st.spinner("Running harmonization pipeline... This may take a minute."):
            result = api_post("/api/run-pipeline")
            if result:
                st.cache_data.clear()
                st.success(f"✅ Pipeline complete!")
                st.json(result.get("result", {}))
                st.rerun()

    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown("""
    **CNMC** = Common National Material Code

    This platform harmonizes material descriptions
    across CPSEs (Central Public Sector Enterprises)
    to identify duplicates and assign unified codes.
    """)


# ---------------------------------------------------------------------------
# Page: Dashboard
# ---------------------------------------------------------------------------

def render_dashboard():
    """Render the main dashboard with metrics and charts."""
    render_header()

    stats = api_get("/api/dashboard")
    if not stats:
        st.info("Run the pipeline first to see dashboard data.")
        return

    # Top-level metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown(f"""
        <div class="metric-card blue">
            <div class="metric-label">Raw Entries</div>
            <div class="metric-value">{stats.get('total_raw_items', 0)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card green">
            <div class="metric-label">CNMC Codes Assigned</div>
            <div class="metric-value">{stats.get('total_cnmc_codes', 0)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card purple">
            <div class="metric-label">Total Match Pairs</div>
            <div class="metric-value">{stats.get('total_match_pairs', 0)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card orange">
            <div class="metric-label">Pending Reviews</div>
            <div class="metric-value">{stats.get('pending_reviews', 0)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown(f"""
        <div class="metric-card red">
            <div class="metric-label">Approved / Rejected</div>
            <div class="metric-value">{stats.get('approved_matches', 0)} / {stats.get('rejected_matches', 0)}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### 📊 Match Type Distribution")
        match_dist = stats.get("match_type_distribution", {})
        if match_dist:
            df_match = pd.DataFrame(
                list(match_dist.items()),
                columns=["Match Type", "Count"]
            )
            st.bar_chart(df_match.set_index("Match Type"), color="#4facfe")
        else:
            st.info("No match data yet.")

    with col_right:
        st.markdown("#### 📦 Category Distribution")
        cat_dist = stats.get("category_distribution", {})
        if cat_dist:
            df_cat = pd.DataFrame(
                list(cat_dist.items()),
                columns=["Category", "Count"]
            )
            st.bar_chart(df_cat.set_index("Category"), color="#43e97b")
        else:
            st.info("No category data yet.")

    # Before / After summary
    st.markdown("---")
    st.markdown("#### 🔄 Harmonization Impact")
    total_raw = stats.get("total_raw_items", 0)
    total_cnmc = stats.get("total_cnmc_codes", 0)
    duplicates_found = stats.get("approved_matches", 0)

    if total_raw > 0:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Before: Raw Entries", total_raw)
        with col2:
            st.metric("After: Unique CNMCs", total_cnmc)
        with col3:
            reduction = round((duplicates_found / total_raw) * 100, 1) if total_raw > 0 else 0
            st.metric("Duplicates Detected", duplicates_found, f"-{reduction}% redundancy")


# ---------------------------------------------------------------------------
# Page: Review Queue
# ---------------------------------------------------------------------------

def render_review_queue():
    """Render the match pair review queue."""
    render_header()
    st.markdown("### 📋 Match Review Queue")
    st.markdown("Review AI-identified matches. Approve to assign CNMC codes or reject false positives.")

    # Filter controls
    col_filter1, col_filter2 = st.columns([1, 3])
    with col_filter1:
        status_filter = st.selectbox(
            "Filter by status",
            ["pending", "all", "approved", "rejected"],
            index=0,
        )
    with col_filter2:
        show_auto_approved = st.checkbox("Show Auto-Approved", value=True)
        show_rejected = st.checkbox("Show Rejected", value=True)

    # Fetch matches
    if status_filter == "all":
        data = api_get("/api/matches")
    else:
        data = api_get(f"/api/matches?status={status_filter}")

    if not data or not data.get("matches"):
        st.info("No match pairs found. Run the pipeline first.")
        return

    matches = data["matches"]

    if "last_action" in st.session_state and status_filter == "pending":
        last = st.session_state["last_action"]
        if not any(m["id"] == last["match"]["id"] for m in matches):
            last["match"]["status"] = last["new_status"]
            if last.get("cnmc_code"):
                last["match"]["cnmc_id"] = last["cnmc_code"]
            matches.insert(min(last["index"], len(matches)), last["match"])

    st.markdown(f"**Showing {len(matches)} match pairs**")

    for idx, match in enumerate(matches):
        match_type = match["match_type"]
        confidence = match["confidence"]
        status = match["status"]

        # Skip rendering based on toggle state
        if status in ("auto-approved", "Auto-Approved") and not show_auto_approved:
            continue
        if status == "rejected" and not show_rejected:
            continue

        badge_class = get_badge_class(match_type)
        status_class = f"status-{status}"

        # Determine the top-right status text
        if status in ("approved", "auto-approved", "Auto-Approved"):
            status_display = f'<span style="color:#43e97b;"><strong>✓ Match Approved</strong></span> → Both mapped to <strong style="color:white;">{match.get("cnmc_id", "")}</strong>'
        elif status == "rejected":
            status_display = f'<span style="color:#ff6b6b;"><strong>✗ Match Rejected</strong></span> → Materials remain separate'
        elif status == "auto-resolved":
            status_display = f'<span style="color:#43e97b;"><strong>✓ Auto-resolved via prior merge</strong></span> → Both mapped to <strong style="color:white;">{match.get("cnmc_id", "")}</strong>'
        else:
            status_display = f'Status: <span class="{status_class}"><strong>{status.upper()}</strong></span>'

        # Fetch existing/assigned CNMCs
        cnmc_a_badge = f'<div style="margin-top:0.5rem; font-size:0.75rem;"><span style="background:#2d2d44; padding:2px 6px; border-radius:4px; color:#43e97b;">Current CNMC: {match.get("cnmc_a", "")}</span></div>' if match.get("cnmc_a") else '<div style="margin-top:0.5rem; font-size:0.75rem;"><span style="background:#2d2d44; padding:2px 6px; border-radius:4px; color:#888;">Current CNMC: Unassigned</span></div>'
        cnmc_b_badge = f'<div style="margin-top:0.5rem; font-size:0.75rem;"><span style="background:#2d2d44; padding:2px 6px; border-radius:4px; color:#43e97b;">Current CNMC: {match.get("cnmc_b", "")}</span></div>' if match.get("cnmc_b") else '<div style="margin-top:0.5rem; font-size:0.75rem;"><span style="background:#2d2d44; padding:2px 6px; border-radius:4px; color:#888;">Current CNMC: Unassigned</span></div>'

        # Card container
        with st.container():
            card_html = (
                f'<div style="background:#1a1a2e;border-radius:12px;padding:1.2rem;margin-bottom:1rem;border:1px solid #2d2d44;box-shadow:0 4px 16px rgba(0,0,0,0.15);">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">'
                f'<span class="badge {badge_class}">{match_type}</span>'
                f'<span style="color:#888;font-size:0.85rem;">Confidence: <strong style="color:white;">{confidence:.1f}%</strong> &nbsp;|&nbsp; {status_display}</span>'
                f'</div>'
            )

            if status in ("approved", "auto-approved", "Auto-Approved", "auto-resolved"):
                # Visual relationship display for approved
                card_html += (
                    f'<div style="display:flex; justify-content:space-between; align-items:center; margin-top:1rem; background:#16213e; padding:1rem; border-radius:8px;">'
                    f'<div style="text-align:center; flex:1;">'
                    f'<div style="color:#4facfe;font-size:0.8rem;font-weight:600;">{match["cpse_a"]}</div>'
                    f'<div style="color:#ccc;font-size:0.9rem;">{match["code_a"]}</div>'
                    f'</div>'
                    f'<div style="color:#888; flex:0.5; text-align:center; font-size:1.5rem;">↘</div>'
                    f'<div style="text-align:center; flex:1; background:#2d2d44; padding:0.5rem; border-radius:8px; border:1px solid #43e97b;">'
                    f'<div style="color:#43e97b;font-size:1rem;font-weight:700;">{match.get("cnmc_id", "")}</div>'
                    f'</div>'
                    f'<div style="color:#888; flex:0.5; text-align:center; font-size:1.5rem;">↙</div>'
                    f'<div style="text-align:center; flex:1;">'
                    f'<div style="color:#4facfe;font-size:0.8rem;font-weight:600;">{match["cpse_b"]}</div>'
                    f'<div style="color:#ccc;font-size:0.9rem;">{match["code_b"]}</div>'
                    f'</div>'
                    f'</div>'
                )
            else:
                card_html += (
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:0.8rem;">'
                    f'<div style="background:#16213e;padding:0.8rem;border-radius:8px;">'
                    f'<div style="color:#4facfe;font-size:0.75rem;font-weight:600;margin-bottom:0.3rem;">{match["cpse_a"]} — {match["code_a"]}</div>'
                    f'<div style="color:#ccc;font-size:0.85rem;">{match["desc_a"]}</div>'
                    f'<div style="color:#888;font-size:0.75rem;margin-top:0.3rem;">→ {match.get("canon_a", "N/A")}</div>'
                    f'{cnmc_a_badge}'
                    f'</div>'
                    f'<div style="background:#16213e;padding:0.8rem;border-radius:8px;">'
                    f'<div style="color:#43e97b;font-size:0.75rem;font-weight:600;margin-bottom:0.3rem;">{match["cpse_b"]} — {match["code_b"]}</div>'
                    f'<div style="color:#ccc;font-size:0.85rem;">{match["desc_b"]}</div>'
                    f'<div style="color:#888;font-size:0.75rem;margin-top:0.3rem;">→ {match.get("canon_b", "N/A")}</div>'
                    f'{cnmc_b_badge}'
                    f'</div>'
                    f'</div>'
                )
                
            card_html += '</div>'
            st.markdown(card_html, unsafe_allow_html=True)

            # Evidence rendering: pending shows directly, others use lazy load
            if status == "pending":
                render_evidence_details(match)
            elif status in ("auto-approved", "Auto-Approved", "rejected"):
                evidence_key = f"evidence_loaded_{match['id']}"
                with st.expander(f"📄 Evidence Details — Pair #{match['id']}", expanded=False):
                    if st.button("Load Evidence", key=f"load_ev_{match['id']}"):
                        st.session_state[evidence_key] = True
                    if st.session_state.get(evidence_key):
                        evidence = match.get("evidence", {})
                        if isinstance(evidence, str):
                            try:
                                evidence = json.loads(evidence)
                            except json.JSONDecodeError:
                                evidence = {}
                        rule_ev = evidence.get("rule_engine", {})
                        ai_ev = evidence.get("ai_matching", {})
                        col_ev1, col_ev2 = st.columns(2)
                        with col_ev1:
                            st.markdown("**Rule Engine Results:**")
                            passed = rule_ev.get("passed", False)
                            st.markdown(f"- Hard constraints: {'✅ PASSED' if passed else '❌ FAILED'}")
                            if rule_ev.get("matched_attributes"):
                                st.markdown(f"- Matched: {', '.join(rule_ev['matched_attributes'])}")
                            if rule_ev.get("failed_attributes"):
                                st.markdown(f"- ❌ Differing: **{', '.join(rule_ev['failed_attributes'])}**")
                        with col_ev2:
                            st.markdown("**AI Matching Scores:**")
                            st.markdown(f"- Cosine similarity: `{ai_ev.get('cosine_similarity', 'N/A')}`")
                            st.markdown(f"- Fuzz ratio: `{ai_ev.get('fuzz_ratio', 'N/A')}`")
                            st.markdown(f"- Combined score: `{ai_ev.get('combined_score', 'N/A')}`")
                            st.markdown(f"- Signal: `{evidence.get('signal', 'N/A')}`")

            if status == "pending":
                col_btn1, col_btn2, col_spacer = st.columns([1, 1, 4])
                with col_btn1:
                    if st.button(f"✅ Approve", key=f"approve_{match['id']}",
                                 type="primary", use_container_width=True):
                        result = api_post(f"/api/matches/{match['id']}/approve")
                        if result:
                            st.cache_data.clear()
                            if result.get("discard_cnmc"):
                                msg = f"Merged {result.get('discard_cnmc')} into {result.get('cnmc_code')}. Both now resolve to {result.get('cnmc_code')}."
                            else:
                                msg = f"Both items assigned to new {result.get('cnmc_code')}."
                            st.session_state["last_action"] = {
                                "match": match.copy(),
                                "index": idx,
                                "msg": msg,
                                "new_status": "approved",
                                "cnmc_code": result.get("cnmc_code")
                            }
                            st.rerun()
                with col_btn2:
                    if st.button(f"❌ Reject", key=f"reject_{match['id']}",
                                 use_container_width=True):
                        result = api_post(f"/api/matches/{match['id']}/reject")
                        if result:
                            st.cache_data.clear()
                            cnmc_a = result.get('cnmc_a') or 'no code assigned'
                            cnmc_b = result.get('cnmc_b') or 'no code assigned'
                            msg = f"No change. CPSE-A retains {cnmc_a}, CPSE-B retains {cnmc_b}."
                            st.session_state["last_action"] = {
                                "match": match.copy(),
                                "index": idx,
                                "msg": msg,
                                "new_status": "rejected"
                            }
                            st.rerun()

            if "last_action" in st.session_state and match["id"] == st.session_state["last_action"]["match"]["id"]:
                st.info(st.session_state["last_action"]["msg"])
                if st.button("Dismiss Message", key=f"dismiss_{match['id']}"):
                    del st.session_state["last_action"]
                    st.rerun()

            st.markdown("---")


# ---------------------------------------------------------------------------
# Page: CNMC Cross-Reference
# ---------------------------------------------------------------------------

def render_cnmc_crossref():
    """Render CNMC cross-reference table."""
    render_header()
    st.markdown("### 🔗 CNMC Cross-Reference Table")
    st.markdown("Unified material codes with all original CPSE local codes preserved.")

    data = api_get("/api/cnmc-codes")
    if not data or not data.get("codes"):
        st.info("No CNMC codes assigned yet. Approve matches in the Review Queue.")
        return

    # Build CSV for ERP Export
    csv_rows = []
    for code_entry in data["codes"]:
        for item in code_entry.get("linked_items", []):
            csv_rows.append({
                "CNMC_ID": code_entry["cnmc_code"],
                "Canonical_Description": code_entry.get("canonical_description", ""),
                "CPSE_ID": item.get("cpse_id", ""),
                "Local_Code": item.get("local_code", ""),
                "Quantity_On_Hand": item.get("quantity_on_hand", 0)
            })
    
    if csv_rows:
        df_export = pd.DataFrame(csv_rows)
        csv_data = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📦 Validated ERP Export (CSV/API for PoC — production integrates via SAP/ERP connectors)",
            data=csv_data,
            file_name="cnmc_validated_export.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True
        )
        st.markdown("<br>", unsafe_allow_html=True)

    for code_entry in data["codes"]:
        render_cnmc_card(code_entry)


# ---------------------------------------------------------------------------
# Shared Component: CNMC Card
# ---------------------------------------------------------------------------

def render_cnmc_card(code_entry):
    """Render a single CNMC cross-reference card with linked items and evidence."""
    cnmc = code_entry["cnmc_code"]
    canon = code_entry.get("canonical_description", "")
    linked = code_entry.get("linked_items", [])
    total_qty = sum(item.get("quantity_on_hand", 0) for item in linked)

    with st.container():
        card_html = (
            f'<div style="background:#1a1a2e;border-radius:12px;padding:1.2rem;margin-bottom:1rem;border-left:4px solid #43e97b;border-right:1px solid #2d2d44;border-top:1px solid #2d2d44;border-bottom:1px solid #2d2d44;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="color:#43e97b;font-weight:700;font-size:1.1rem;">{cnmc}</span>'
            f'<span style="color:#888;font-size:0.85rem;">Total Known Units: <strong style="color:white;">{total_qty}</strong> | {code_entry.get("created_at", "")}</span>'
            f'</div>'
            f'<div style="color:#ccc;margin-top:0.5rem;font-size:0.9rem;">📝 {canon}</div>'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

        # Linked items
        if linked:
            df = pd.DataFrame(linked)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
        # Evidence panels for pairs forming this cluster
        matches = code_entry.get("matches", [])
        if matches:
            st.markdown("<div style='margin-top: 0.5rem; color: #888; font-size: 0.85rem;'>Underlying Mapping Evidence:</div>", unsafe_allow_html=True)
            for match in matches:
                render_evidence_details(match)


# ---------------------------------------------------------------------------
# Page: Material Search
# ---------------------------------------------------------------------------

def render_material_search():
    """Render the Material Search page."""
    render_header()
    st.markdown("### 🔍 Material Search")
    st.markdown("Search by CPSE local code, raw description, standard code, or **CNMC code** (e.g. `CPSE-A-BLT-1000`, `hex bolt 316`, `DIN 933`, `CNMC-000001`).")

    query = st.text_input("🔎 Search materials", placeholder="Type a code, description, standard, or CNMC code...")

    if not query or len(query.strip()) < 2:
        st.info("Enter at least 2 characters to search.")
        return

    # Fetch search results
    data = api_get(f"/api/search?q={query}")
    if not data or not data.get("items"):
        st.warning(f"No material found matching '{query}'")
        return

    items = data["items"]
    st.markdown(f"**{len(items)} item(s) match your search**")

    # Group matching items by their CNMC code
    cnmc_groups = {}  # cnmc_code -> list of items
    unassigned = []
    for item in items:
        cnmc = item.get("cnmc_code")
        if cnmc:
            if cnmc not in cnmc_groups:
                cnmc_groups[cnmc] = []
            cnmc_groups[cnmc].append(item)
        else:
            unassigned.append(item)

    # If only a few CNMCs, show full detail directly
    if len(cnmc_groups) <= 3:
        # Show full CNMC cards
        for cnmc_code in cnmc_groups:
            cnmc_data = _fetch_cnmc_detail(cnmc_code)
            if cnmc_data:
                render_cnmc_card(cnmc_data)
    else:
        # Show summary list with expandable detail
        st.markdown(f"**Matches span {len(cnmc_groups)} CNMC groups** — click to expand details:")
        for cnmc_code, group_items in cnmc_groups.items():
            cnmc_data = _fetch_cnmc_detail(cnmc_code)
            canon = cnmc_data["canonical_description"] if cnmc_data else "N/A"
            item_count = len(cnmc_data["linked_items"]) if cnmc_data else len(group_items)
            with st.expander(f"📦 {cnmc_code} — {canon} ({item_count} items)"):
                if cnmc_data:
                    render_cnmc_card(cnmc_data)
                else:
                    for item in group_items:
                        st.markdown(f"- `{item['local_code']}`: {item['raw_description']}")

    # Show unassigned items (not in any CNMC)
    if unassigned:
        st.markdown("---")
        st.markdown(f"**{len(unassigned)} matching item(s) not yet assigned to a CNMC:**")
        for item in unassigned:
            raw = item['raw_description']
            code = item['local_code']
            st.markdown(f"- `{code}` ({item['cpse_id']}): {raw}")


def _fetch_cnmc_detail(cnmc_code: str):
    """Fetch full CNMC detail from the API for a specific code."""
    data = api_get("/api/cnmc-codes")
    if not data or not data.get("codes"):
        return None
    for code_entry in data["codes"]:
        if code_entry["cnmc_code"] == cnmc_code:
            return code_entry
    return None


# (render_processed_items removed — merged into render_legacy_code_manager)


# ---------------------------------------------------------------------------
# Page: Audit Log
# ---------------------------------------------------------------------------

def render_audit_log():
    """Render the audit log."""
    render_header()
    st.markdown("### 📜 Audit Log")
    st.markdown("Complete decision trail: who decided, when, and which signal drove the outcome.")

    data = api_get("/api/audit-log")
    if not data or not data.get("log"):
        st.info("No audit entries yet.")
        return

    rows = []
    for entry in data["log"]:
        details = entry.get("details", "{}")
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except json.JSONDecodeError:
                details = {"raw": details}

        rows.append({
            "Timestamp": entry.get("created_at", ""),
            "Action": entry.get("action", ""),
            "Reviewer": entry.get("reviewer", ""),
            "Signal": entry.get("signal", ""),
            "Details": json.dumps(details, indent=0) if isinstance(details, dict) else str(details),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True, height=600)


# ---------------------------------------------------------------------------
# Page: Procurement Intelligence
# ---------------------------------------------------------------------------

def render_procurement_intelligence():
    render_header()
    st.markdown("### 📈 Procurement Intelligence")
    st.markdown("Active procurement demand analysis per CNMC — identifies stock reuse and consolidation opportunities across CPSEs.")
    
    data = api_get("/api/procurement-intelligence")
    if not data or not data.get("cnmc_groups"):
        st.info("No procurement intelligence data available. Run the pipeline first.")
        return

    groups = data["cnmc_groups"]

    # Summary metrics
    total_requisitions = sum(len(g["demand_items"]) for g in groups)
    total_demand_units = sum(g["total_demand"] for g in groups)
    reuse_count = sum(1 for g in groups if g.get("stock_reuse_suggestions"))
    consol_count = sum(1 for g in groups if g.get("consolidation_opportunity"))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card blue">
            <div class="metric-label">Active Requisitions</div>
            <div class="metric-value">{total_requisitions}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card orange">
            <div class="metric-label">Total Demand (Units)</div>
            <div class="metric-value">{total_demand_units:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card green">
            <div class="metric-label">Stock Reuse Opportunities</div>
            <div class="metric-value">{reuse_count}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card purple">
            <div class="metric-label">Consolidation Opportunities</div>
            <div class="metric-value">{consol_count}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("### Demand Aggregation Summary")
    summary_data = []
    chart_data = []
    for g in groups:
        if g["total_demand"] > 0:
            cpses = list(set([d["cpse_id"] for d in g["demand_items"]]))
            summary_data.append({
                "CNMC Code": g["cnmc_code"],
                "Total Demand": g["total_demand"],
                "CPSE Count": len(cpses),
                "CPSEs": ", ".join(cpses)
            })
            for d in g["demand_items"]:
                chart_data.append({
                    "CNMC": g["cnmc_code"],
                    "CPSE": d["cpse_id"],
                    "Quantity": d["quantity_needed"]
                })
                
    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        top_item = df_summary.loc[df_summary["Total Demand"].idxmax()]
        if top_item["CPSE Count"] > 1:
            st.info(f"💡 **Insight:** {top_item['CNMC Code']} has demand from {top_item['CPSE Count']} CPSEs for a combined {top_item['Total Demand']:,} units — eligible for consolidated bulk procurement.")
            
        st.markdown("**Demand Distribution (Quantity per CPSE)**")
        df_chart = pd.DataFrame(chart_data)
        if not df_chart.empty:
            chart_pivot = df_chart.pivot_table(index="CNMC", columns="CPSE", values="Quantity", aggfunc="sum").fillna(0)
            st.bar_chart(chart_pivot)
            
    st.markdown("---")

    # Per-CNMC cards
    for group in groups:
        cnmc = group["cnmc_code"]
        canon = group.get("canonical_description", "")
        demand_items = group.get("demand_items", [])
        stock_items = group.get("stock_items", [])
        reuse_suggestions = group.get("stock_reuse_suggestions", [])
        consolidation = group.get("consolidation_opportunity")

        has_opportunity = bool(reuse_suggestions or consolidation)
        border_color = "#ffa751" if has_opportunity else "#4facfe"

        with st.container():
            st.markdown(f"""
            <div style="background: #1a1a2e; border-radius: 12px; padding: 1.2rem;
                        margin-bottom: 1rem; border-left: 4px solid {border_color};
                        border-right: 1px solid #2d2d44; border-top: 1px solid #2d2d44;
                        border-bottom: 1px solid #2d2d44;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: {border_color}; font-weight: 700; font-size: 1.1rem;">{cnmc}</span>
                    <span style="color: #888; font-size: 0.85rem;">Demand: <strong style="color: #ffa751;">{group['total_demand']:,} units</strong> &nbsp;|&nbsp; Stock: <strong style="color: #43e97b;">{group['total_stock']:,} units</strong></span>
                </div>
                <div style="color: #ccc; margin-top: 0.5rem; font-size: 0.9rem;">📝 {canon}</div>
            </div>
            """, unsafe_allow_html=True)

            # Opportunity banners
            for suggestion in reuse_suggestions:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #3d2800 0%, #2d1f00 100%); border: 1px solid #ffa75155;
                            border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 0.5rem; color: #ffa751; font-size: 0.9rem;">
                    🔄 <strong>Stock Reuse:</strong> {suggestion}
                </div>
                """, unsafe_allow_html=True)

            if consolidation:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #0a1628 0%, #162040 100%); border: 1px solid #4facfe55;
                            border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 0.5rem; color: #4facfe; font-size: 0.9rem;">
                    🚀 <strong>Consolidation:</strong> {consolidation}
                </div>
                """, unsafe_allow_html=True)

            # Demand and Stock tables side by side
            col_demand, col_stock = st.columns(2)
            with col_demand:
                st.markdown("**📋 Active Demand:**")
                if demand_items:
                    df_demand = pd.DataFrame(demand_items)
                    df_demand.columns = [c.replace("_", " ").title() for c in df_demand.columns]
                    st.dataframe(df_demand, use_container_width=True, hide_index=True)
                else:
                    st.markdown("<span style='color:#888;'>No active demand</span>", unsafe_allow_html=True)

            with col_stock:
                st.markdown("**📦 Existing Stock:**")
                if stock_items:
                    df_stock = pd.DataFrame(stock_items)
                    df_stock.columns = [c.replace("_", " ").title() for c in df_stock.columns]
                    st.dataframe(df_stock, use_container_width=True, hide_index=True)
                else:
                    st.markdown("<span style='color:#888;'>No stock held</span>", unsafe_allow_html=True)

            st.markdown("---")

# ---------------------------------------------------------------------------
# Page: Inventory Visibility
# ---------------------------------------------------------------------------

def render_inventory_visibility():
    render_header()
    st.markdown("### 📦 Inventory Visibility")
    st.markdown("Aggregate view focused on known stock by CPSE per CNMC.")
    
    data = api_get("/api/cnmc-codes")
    if not data or not data.get("codes"):
        st.info("No CNMC codes assigned yet.")
        return
        
    for code_entry in data["codes"]:
        cnmc = code_entry["cnmc_code"]
        canon = code_entry.get("canonical_description", "")
        linked = code_entry.get("linked_items", [])
        
        # Aggregate demand/stock by CPSE
        cpse_stock = {}
        for item in linked:
            cpse = item["cpse_id"]
            cpse_stock[cpse] = cpse_stock.get(cpse, 0) + item.get("quantity_on_hand", 0)
            
        stock_holders = [cpse for cpse, qty in cpse_stock.items() if qty > 0]
        
        with st.container():
            st.markdown(f"""
            <div style="background: #1a1a2e; border-radius: 12px; padding: 1.2rem;
                        margin-bottom: 0.5rem; border-left: 4px solid #a18cd1;
                        border-right: 1px solid #2d2d44; border-top: 1px solid #2d2d44;
                        border-bottom: 1px solid #2d2d44;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #a18cd1; font-weight: 700; font-size: 1.1rem;">{cnmc}</span>
                </div>
                <div style="color: #ccc; margin-top: 0.5rem; font-size: 0.9rem;">
                    📝 {canon}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if len(stock_holders) > 1:
                st.info(f"🤝 **Cross-CPSE Stock Sharing Opportunity:** Both {', '.join(stock_holders)} hold stock of {cnmc}.")
            elif len(stock_holders) == 1:
                st.markdown(f"Only {stock_holders[0]} holds stock.")
            else:
                st.markdown("No CPSE holds stock.")
                
            if cpse_stock:
                total_stock = sum(cpse_stock.values())
                breakdown = [{"CPSE": cpse, "Quantity On Hand": qty} for cpse, qty in cpse_stock.items()]
                breakdown.append({"CPSE": "Total", "Quantity On Hand": total_stock})
                df_stock = pd.DataFrame(breakdown)
                st.markdown("**Per-CPSE Inventory Breakdown:**")
                st.dataframe(df_stock, use_container_width=True, hide_index=True)
            
            st.markdown("---")

# ---------------------------------------------------------------------------
# Page: Legacy Code Manager  (merged with former Processed Items)
# ---------------------------------------------------------------------------

_LEGACY_STATUS_COLORS = {
    "Merged":      ("#43e97b", "#0a2e1a"),
    "Retained":    ("#4facfe", "#0a1628"),
    "Deprecated":  ("#ff6b6b", "#2e0a0a"),
    "Pending":     ("#ffa751", "#2e1a00"),
}

def _legacy_status(local_code: str, cnmc_map: dict) -> tuple[str, str]:
    """Return (legacy_status_label, cnmc_id_or_empty) for a given local_code."""
    cnmc = cnmc_map.get(local_code)
    if cnmc:
        return "Merged", cnmc
    return "Pending", ""


def render_legacy_code_manager():
    render_header()
    st.markdown("### 🏛️ Legacy Code Manager")
    st.markdown(
        "Complete item-level view: classification details from the pipeline "
        "combined with each code's migration status and CNMC assignment."
    )

    items_data = api_get("/api/items")
    cnmc_data  = api_get("/api/cnmc-codes")

    if not items_data or not items_data.get("items"):
        st.info("No items processed yet. Run the pipeline first.")
        return

    items = items_data["items"]

    # Build local_code -> CNMC mapping
    cnmc_map: dict[str, str] = {}
    if cnmc_data and cnmc_data.get("codes"):
        for code_entry in cnmc_data["codes"]:
            cnmc = code_entry["cnmc_code"]
            for linked in code_entry.get("linked_items", []):
                cnmc_map[linked["local_code"]] = cnmc

    # Build unified rows
    rows = []
    for item in items:
        status, cnmc_id = _legacy_status(item["local_code"], cnmc_map)
        rows.append({
            "CPSE ID":               item["cpse_id"],
            "Local Code":            item["local_code"],
            "Raw Description":       item["raw_description"],
            "Category":              item.get("category", "—"),
            "Confidence":            item.get("category_confidence", "—"),
            "Classification Path":   item.get("classification_path", "—"),
            "Canonical Description": item.get("canonical_description", "—"),
            "Legacy Status":         status,
            "CNMC ID":               cnmc_id,
        })

    df_full = pd.DataFrame(rows)

    # ── Summary metrics ────────────────────────────────────────────────────
    total   = len(df_full)
    merged  = int((df_full["Legacy Status"] == "Merged").sum())
    pending = int((df_full["Legacy Status"] == "Pending").sum())
    retained = int((df_full["Legacy Status"] == "Retained").sum())
    deprecated = int((df_full["Legacy Status"] == "Deprecated").sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    for col, label, val, css in [
        (c1, "Total Items",  total,      "blue"),
        (c2, "Merged",       merged,     "green"),
        (c3, "Pending",      pending,    "orange"),
        (c4, "Retained",     retained,   "blue"),
        (c5, "Deprecated",   deprecated, "red"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card {css}">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{val}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Filter bar ─────────────────────────────────────────────────────────
    col_filter, col_search, _ = st.columns([2, 3, 3])
    with col_filter:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Merged", "Pending", "Retained", "Deprecated"],
            key="lcm_status_filter",
        )
    with col_search:
        search_term = st.text_input(
            "Search (code / description / CNMC)",
            placeholder="e.g. VALVE, CPSE-A, CNMC-000001",
            key="lcm_search",
        )

    df = df_full.copy()
    if status_filter != "All":
        df = df[df["Legacy Status"] == status_filter]
    if search_term:
        mask = df.apply(
            lambda r: search_term.upper() in str(r).upper(), axis=1
        )
        df = df[mask]

    st.markdown(f"**Showing {len(df)} of {total} items**")

    # ── Export button ──────────────────────────────────────────────────────
    csv_bytes = df_full.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Export Migration Report (CSV)",
        data=csv_bytes,
        file_name=f"legacy_migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        type="primary",
        use_container_width=False,
        key="lcm_csv_export",
    )

    # ── Table ──────────────────────────────────────────────────────────────
    st.dataframe(df, use_container_width=True, hide_index=True, height=600)

# ---------------------------------------------------------------------------
# Page Router
# ---------------------------------------------------------------------------

if "🏠 Dashboard" in page:
    render_dashboard()
elif "🔍 Material Search" in page:
    render_material_search()
elif "📋 Review Queue" in page:
    render_review_queue()
elif "🔗 CNMC Cross-Reference" in page:
    render_cnmc_crossref()
elif "📈 Procurement Intelligence" in page:
    render_procurement_intelligence()
elif "📦 Inventory Visibility" in page:
    render_inventory_visibility()
elif "🏛️ Legacy Code Manager" in page:
    render_legacy_code_manager()
elif "📜 Audit Log" in page:
    render_audit_log()

