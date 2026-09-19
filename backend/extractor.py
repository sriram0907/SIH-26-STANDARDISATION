"""
Step 3 — Attribute Extraction
==============================
Per-category regex + normalization dictionaries to extract structured
attributes from raw material descriptions.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Normalization dictionaries
# ---------------------------------------------------------------------------

MATERIAL_NORMALIZATION = {
    # Stainless Steel 316L
    r"\bSS\s*316L\b":              "STAINLESS STEEL 316L",
    r"\bS\.?S\.?\s*316L\b":        "STAINLESS STEEL 316L",
    r"\bStainless\s+Steel\s*316L\b":"STAINLESS STEEL 316L",
    # Stainless Steel 316
    r"\bSS\s*316\b":               "STAINLESS STEEL 316",
    r"\bS\.?S\.?\s*316\b":         "STAINLESS STEEL 316",
    r"\bSSteel\s*316\b":           "STAINLESS STEEL 316",
    r"\bStainless\s+Steel\s*316\b":"STAINLESS STEEL 316",
    # Stainless Steel 304
    r"\bSS\s*304\b":               "Stainless Steel 304",
    r"\bS\.?S\.?\s*304\b":         "Stainless Steel 304",
    r"\bSSteel\s*304\b":           "Stainless Steel 304",
    r"\bStainless\s+Steel\s*304\b":"Stainless Steel 304",
    # Stainless Steel 310
    r"\bSS\s*310\b":               "Stainless Steel 310",
    r"\bS\.?S\.?\s*310\b":         "Stainless Steel 310",
    r"\bSSteel\s*310\b":           "Stainless Steel 310",
    r"\bStainless\s+Steel\s*310\b":"Stainless Steel 310",
    # Carbon Steel
    r"\bCS\b":                     "Carbon Steel",
    r"\bC\.?S\.?\b":               "Carbon Steel",
    r"\bCarbon\s+Steel\b":         "Carbon Steel",
    r"\bCSteel\b":                 "Carbon Steel",
    r"\bC\s+Steel\b":             "Carbon Steel",
    # Alloy Steel B7
    r"\bB7\b":                     "Alloy Steel B7",
    r"\bAlloy\s*B7\b":             "Alloy Steel B7",
    r"\bASTM\s*B7\b":              "Alloy Steel B7",
    r"\bAlloy\s+Steel\s+B7\b":     "Alloy Steel B7",
    # Alloy Steel (generic)
    r"\bAlloy\s+Steel\b":          "Alloy Steel",
    r"\bAlloy\s+Stl\b":            "Alloy Steel",
    r"\bAS\b":                     "Alloy Steel",
    # Cast Iron
    r"\bCI\b":                     "Cast Iron",
    r"\bC\.?I\.?\b":               "Cast Iron",
    r"\bCast\s+Iron\b":            "Cast Iron",
}

VALVE_TYPE_NORMALIZATION = {
    r"\bGate\b":       "Gate",
    r"\bBALL\b":       "Ball",
    r"\bBall\b":       "Ball",
    r"\bCHECK\b":      "Check",
    r"\bCheck\b":      "Check",
    r"\bChk\b":        "Check",
    r"\bGLOBE\b":      "Globe",
    r"\bGlobe\b":      "Globe",
    r"\bBUTTERFLY\b":  "Butterfly",
    r"\bButterfly\b":  "Butterfly",
    r"\bBfly\b":       "Butterfly",
    r"\bNEEDLE\b":     "Needle",
    r"\bNeedle\b":     "Needle",
    r"\bNdl\b":        "Needle",
    r"\bPLUG\b":       "Plug",
    r"\bPlug\b":       "Plug",
}

CONNECTION_NORMALIZATION = {
    r"\bFlanged\b":    "Flanged",
    r"\bFLANGED\b":    "Flanged",
    r"\bFLGD\b":       "Flanged",
    r"\bFLG\b":        "Flanged",
    r"\bFlg\b":        "Flanged",
    r"\bThreaded\b":   "Threaded",
    r"\bTHREADED\b":   "Threaded",
    r"\bTHD\b":        "Threaded",
    r"\bTHRD\b":       "Threaded",
    r"\bThd\b":        "Threaded",
    r"\bWafer\b":      "Wafer",
    r"\bWAFER\b":      "Wafer",
    r"\bWfr\b":        "Wafer",
}

BOLT_TYPE_NORMALIZATION = {
    r"\bHEX\s*BOLT\b":     "HEX BOLT",
    r"\bHex\s*Bolt\b":     "HEX BOLT",
    r"\bhex\s*bolt\b":     "HEX BOLT",
    r"\bCARRIAGE\s*BOLT\b":"CARRIAGE BOLT",
    r"\bCarriage\s*Bolt\b":"CARRIAGE BOLT",
    r"\bSTUD\s*BOLT\b":    "STUD BOLT",
    r"\bStud\s*Bolt\b":    "STUD BOLT",
    r"\bFLANGE\s*BOLT\b":  "FLANGE BOLT",
    r"\bFlange\s*Bolt\b":  "FLANGE BOLT",
    r"\bEYE\s*BOLT\b":     "EYE BOLT",
    r"\bEye\s*Bolt\b":     "EYE BOLT",
    r"\bU-BOLT\b":         "U-BOLT",
    r"\bu-bolt\b":         "U-BOLT",
    r"\bT-BOLT\b":         "T-BOLT",
    r"\bt-bolt\b":         "T-BOLT",
    r"\bANCHOR\s*BOLT\b":  "ANCHOR BOLT",
    r"\bAnchor\s*Bolt\b":  "ANCHOR BOLT",
}

THREAD_NORMALIZATION = {
    r"\bFull\s*Thread\b":    "Full Thread",
    r"\bFULL\s*THREAD\b":    "Full Thread",
    r"\bFull\s*Thd\b":       "Full Thread",
    r"\bFT\b":               "Full Thread",
    r"\bPartial\s*Thread\b": "Partial Thread",
    r"\bPARTIAL\s*THREAD\b": "Partial Thread",
    r"\bPartial\s*Thd\b":    "Partial Thread",
    r"\bPT\b":               "Partial Thread",
}


def _normalize_lookup(text: str, normalization_dict: dict) -> str | None:
    """Find the first matching normalization pattern and return canonical form."""
    for pattern, canonical in normalization_dict.items():
        if re.search(pattern, text, re.IGNORECASE):
            return canonical
    return None


def extract_bolt_attributes(description: str) -> dict:
    """
    Extract structured attributes from a bolt description.

    Returns dict with keys: type, material, diameter, length, standard, thread
    """
    attrs = {
        "type": None,
        "material": None,
        "diameter": None,
        "length": None,
        "standard": None,
        "thread": None,
    }

    # Bolt type
    attrs["type"] = _normalize_lookup(description, BOLT_TYPE_NORMALIZATION) or "BOLT"

    # Material — try specific grades first (SS316 before generic SS)
    # Sort by pattern length descending to match most specific first
    for pattern, canonical in sorted(MATERIAL_NORMALIZATION.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(pattern, description, re.IGNORECASE):
            attrs["material"] = canonical
            break

    # Diameter and length: M10x50, M10 x 50, M10X50MM, etc.
    dim_match = re.search(r"\bM(\d+)\s*[xX×]\s*(\d+)\s*(?:mm|MM)?\b", description, re.IGNORECASE)
    if dim_match:
        attrs["diameter"] = f"M{dim_match.group(1)}"
        attrs["length"] = f"{dim_match.group(2)} mm"

    # Standard code
    std_patterns = [
        (r"\bDIN\s*(\d+)\b", "DIN"),
        (r"\bISO\s*(\d+)\b", "ISO"),
        (r"\bIS\s*(\d+)\b", "IS"),
        (r"\bASTM\s*([A-Z]\d+)\b", "ASTM"),
    ]
    for pattern, prefix in std_patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            attrs["standard"] = f"{prefix} {match.group(1)}"
            break

    # Thread type
    attrs["thread"] = _normalize_lookup(description, THREAD_NORMALIZATION)

    logger.info(f"  🔩 Bolt attributes: {attrs}")
    return attrs


def extract_valve_attributes(description: str) -> dict:
    """
    Extract structured attributes from a valve description.

    Returns dict with keys: type, size, pressure_rating, body_material, end_connection
    """
    attrs = {
        "type": None,
        "size": None,
        "pressure_rating": None,
        "body_material": None,
        "end_connection": None,
    }

    # Valve type
    attrs["type"] = _normalize_lookup(description, VALVE_TYPE_NORMALIZATION)

    # Size: 2", 2 inch, 1/2", etc.
    size_match = re.search(r'(\d+(?:/\d+)?)\s*(?:"|inch|IN)(?:\b|(?=\s|$))', description, re.IGNORECASE)
    if size_match:
        attrs["size"] = f'{size_match.group(1)}"'

    # Pressure rating: 150#, 150 Class, 150 CL, 150LB, etc.
    pr_match = re.search(r"(\d+)\s*(?:#|Class|CL|LB)\b", description, re.IGNORECASE)
    if pr_match:
        attrs["pressure_rating"] = f"{pr_match.group(1)}#"

    # Body material
    for pattern, canonical in sorted(MATERIAL_NORMALIZATION.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(pattern, description, re.IGNORECASE):
            attrs["body_material"] = canonical
            break

    # End connection
    attrs["end_connection"] = _normalize_lookup(description, CONNECTION_NORMALIZATION)

    logger.info(f"  🔧 Valve attributes: {attrs}")
    return attrs


def extract_attributes(description: str, category: str) -> dict:
    """Route to the correct extractor based on category."""
    if category == "Bolt":
        return extract_bolt_attributes(description)
    elif category == "Valve":
        return extract_valve_attributes(description)
    else:
        logger.warning(f"  ⚠️  No extractor for category: {category}")
        return {}
