"""
Step 2 — Classification Module (Scoring-Based)
================================================
Classifies material descriptions into categories (Bolt, Valve, etc.)
using a weighted scoring system with MiniLM fallback for uncertain cases.
"""

import re
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signal definitions — scored, NOT if/elif cascade
# ---------------------------------------------------------------------------

# Standard-code -> category mapping (weight=3, near-unambiguous signals)
STANDARD_CODE_SIGNALS = {
    # Bolt standards
    r"\bDIN\s*933\b":   ("Bolt", 3),
    r"\bDIN\s*931\b":   ("Bolt", 3),
    r"\bDIN\s*6921\b":  ("Bolt", 3),
    r"\bDIN\s*580\b":   ("Bolt", 3),
    r"\bDIN\s*787\b":   ("Bolt", 3),
    r"\bISO\s*8677\b":  ("Bolt", 3),
    r"\bIS\s*5570\b":   ("Bolt", 3),
    r"\bIS\s*5624\b":   ("Bolt", 3),
    r"\bASTM\s*A193\b": ("Bolt", 3),
    # Valve standards
    r"\bAPI\s*600\b":   ("Valve", 3),
    r"\bAPI\s*6D\b":    ("Valve", 3),
    r"\bAPI\s*602\b":   ("Valve", 3),
    r"\bAPI\s*608\b":   ("Valve", 3),
    r"\bBS\s*1868\b":   ("Valve", 3),
    r"\bBS\s*5351\b":   ("Valve", 3),
}

# Keyword/regex -> category mapping (weight=1, weaker signals)
KEYWORD_SIGNALS = {
    r"\bHEX\b":         ("Bolt", 1),
    r"\bBOLT\b":        ("Bolt", 1),
    r"\bSCREW\b":       ("Bolt", 1),
    r"\bSTUD\b":        ("Bolt", 1),
    r"\bNUT\b":         ("Bolt", 1),
    r"\bCARRIAGE\b":    ("Bolt", 1),
    r"\bFLANGE\s*BOLT\b": ("Bolt", 1),
    r"\bEYE\s*BOLT\b":  ("Bolt", 1),
    r"\bU-BOLT\b":      ("Bolt", 1),
    r"\bT-BOLT\b":      ("Bolt", 1),
    r"\bANCHOR\b":      ("Bolt", 1),
    r"\bM\d+\s*[xX×]\s*\d+\b": ("Bolt", 1),  # M10x50 pattern
    r"\bGATE\b":        ("Valve", 1),
    r"\bBALL\b":        ("Valve", 1),
    r"\bCHECK\b":       ("Valve", 1),
    r"\bGLOBE\b":       ("Valve", 1),
    r"\bBUTTERFLY\b":   ("Valve", 1),
    r"\bNEEDLE\b":      ("Valve", 1),
    r"\bPLUG\b":        ("Valve", 1),
    r"\bVALVE\b":       ("Valve", 1),
    r"\bVLV\b":         ("Valve", 1),
    r"\d+\s*#":         ("Valve", 1),  # Pressure rating like 150#
    r"\bFLANGED\b":     ("Valve", 1),
    r"\bFLGD\b":        ("Valve", 1),
    r"\bWAFER\b":       ("Valve", 1),
}

# Labeled examples for MiniLM fallback (used only for uncertain cases)
CATEGORY_EXAMPLES = {
    "Bolt": [
        "HEX BOLT STAINLESS STEEL 316 M10 x 50 mm DIN 933",
        "CARRIAGE BOLT CARBON STEEL M8 x 30 ISO 8677",
        "STUD BOLT ALLOY STEEL B7 M20 x 120 ASTM A193",
        "FLANGE BOLT CS M12 x 35 DIN 6921",
        "U-BOLT CARBON STEEL M10 x 100",
    ],
    "Valve": [
        "GATE VALVE 2 INCH 150 CLASS CARBON STEEL FLANGED",
        "BALL VALVE 1 INCH 300# STAINLESS STEEL 316 THREADED",
        "CHECK VALVE 3 INCH 150# CS FLANGED",
        "GLOBE VALVE 2 INCH 150# CARBON STEEL FLANGED",
        "BUTTERFLY VALVE 6 INCH 150# CAST IRON WAFER",
    ],
}

# Uncertainty margin — if top two category scores are within this margin, it's uncertain
UNCERTAINTY_MARGIN = 1

# MiniLM cosine similarity threshold for AI-assisted classification
MINILM_THRESHOLD = 0.6

# Global model reference — lazy loaded
_model = None


def _get_model():
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("📦 Loading MiniLM model for classification fallback...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("✅ MiniLM model loaded")
    return _model


def _compute_scores(description: str) -> dict:
    """
    Compute category scores by summing all matched signal weights.
    Does NOT stop at the first match — accumulates all signals.
    """
    scores = {}
    matched_signals = []
    text_upper = description.upper()

    # Check standard codes (weight=3)
    for pattern, (category, weight) in STANDARD_CODE_SIGNALS.items():
        if re.search(pattern, text_upper, re.IGNORECASE):
            scores[category] = scores.get(category, 0) + weight
            matched_signals.append(("standard_code", pattern, category, weight))

    # Check keywords (weight=1)
    for pattern, (category, weight) in KEYWORD_SIGNALS.items():
        if re.search(pattern, text_upper, re.IGNORECASE):
            scores[category] = scores.get(category, 0) + weight
            matched_signals.append(("keyword", pattern, category, weight))

    return scores, matched_signals


def _minilm_classify(description: str) -> tuple:
    """
    Use MiniLM embeddings to classify uncertain descriptions.
    Compares against labeled examples per category.
    Returns: (category, similarity_score)
    """
    model = _get_model()

    desc_embedding = model.encode([description])[0]
    best_category = None
    best_score = -1.0

    for category, examples in CATEGORY_EXAMPLES.items():
        example_embeddings = model.encode(examples)
        # Cosine similarity against each example
        for emb in example_embeddings:
            cos_sim = float(np.dot(desc_embedding, emb) / (
                np.linalg.norm(desc_embedding) * np.linalg.norm(emb) + 1e-8
            ))
            if cos_sim > best_score:
                best_score = cos_sim
                best_category = category

    return best_category, best_score


def classify_description(description: str) -> dict:
    """
    Classify a material description into a category.

    Returns:
        dict with keys: category, confidence, classification_path, details
    """
    scores, matched_signals = _compute_scores(description)

    # Sort categories by score
    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Log matched signals
    logger.info(f"  Classification signals for: {description[:60]}...")
    for sig_type, pattern, cat, weight in matched_signals:
        logger.info(f"    [{sig_type}] {pattern} -> {cat} (weight={weight})")

    # Case 1: Clear winner
    if len(sorted_cats) >= 1:
        top_cat, top_score = sorted_cats[0]

        # Check if there's a second category within uncertainty margin
        if len(sorted_cats) >= 2:
            second_cat, second_score = sorted_cats[1]
            if top_score - second_score <= UNCERTAINTY_MARGIN:
                # Uncertain — fall through to MiniLM
                logger.info(f"  ⚠️  Uncertain: {top_cat}={top_score} vs {second_cat}={second_score} (margin={UNCERTAINTY_MARGIN})")
            else:
                # Clear winner
                path = "standard_code_match" if top_score >= 3 else "keyword_match"
                logger.info(f"  ✅ Classified as {top_cat} via {path} (score={top_score})")
                return {
                    "category": top_cat,
                    "confidence": "high",
                    "classification_path": path,
                    "details": {"scores": dict(sorted_cats), "signals": len(matched_signals)},
                }
        elif top_score > 0:
            # Only one category matched
            path = "standard_code_match" if top_score >= 3 else "keyword_match"
            logger.info(f"  ✅ Classified as {top_cat} via {path} (score={top_score})")
            return {
                "category": top_cat,
                "confidence": "high",
                "classification_path": path,
                "details": {"scores": dict(sorted_cats), "signals": len(matched_signals)},
            }

    # Case 2: Uncertain or zero scores — use MiniLM fallback
    logger.info(f"  🤖 Using MiniLM fallback for classification...")
    ml_category, ml_score = _minilm_classify(description)

    if ml_score >= MINILM_THRESHOLD:
        logger.info(f"  🤖 MiniLM classified as {ml_category} (similarity={ml_score:.3f})")
        confidence = "medium" if ml_score >= 0.75 else "low"
        return {
            "category": ml_category,
            "confidence": f"AI-assisted, {confidence} confidence",
            "classification_path": "minilm_fallback",
            "details": {"ml_category": ml_category, "ml_score": round(ml_score, 4)},
        }

    # Case 3: Completely unresolved
    logger.info(f"  ❓ Unclassified — sending to human review queue")
    return {
        "category": "unclassified",
        "confidence": "none",
        "classification_path": "unclassified",
        "details": {"ml_best": ml_category, "ml_score": round(ml_score, 4)},
    }
