"""
Step 6 — AI Matching Layer
===========================
Embeds canonical descriptions with MiniLM, computes cosine similarity,
and combines with RapidFuzz token-sort-ratio for a final confidence score.

Only runs on pairs that PASSED the rule engine's hard constraints.
"""

import logging
import numpy as np
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Weights for combining signals
COSINE_WEIGHT = 0.6
FUZZ_WEIGHT = 0.4

# Global model reference — lazy loaded (shared with classifier)
_model = None


def _get_model():
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("📦 Loading MiniLM model for matching...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("✅ MiniLM model loaded")
    return _model


def compute_cosine_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between two texts using MiniLM embeddings."""
    model = _get_model()
    embeddings = model.encode([text_a, text_b])
    cos_sim = float(np.dot(embeddings[0], embeddings[1]) / (
        np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]) + 1e-8
    ))
    return max(0.0, min(1.0, cos_sim))  # Clamp to [0, 1]


def compute_fuzz_ratio(text_a: str, text_b: str) -> float:
    """Compute RapidFuzz token-sort-ratio (0-100), normalized to 0-1."""
    ratio = fuzz.token_sort_ratio(text_a, text_b)
    return ratio / 100.0


def compute_match_score(canonical_a: str, canonical_b: str) -> dict:
    """
    Compute a combined matching confidence score.

    Returns:
        dict with keys: combined_score (0-100), cosine_similarity, fuzz_ratio, details
    """
    cosine_sim = compute_cosine_similarity(canonical_a, canonical_b)
    fuzz_ratio = compute_fuzz_ratio(canonical_a, canonical_b)

    combined = (COSINE_WEIGHT * cosine_sim + FUZZ_WEIGHT * fuzz_ratio) * 100

    logger.info(f"  🤖 AI Match Score:")
    logger.info(f"    Cosine similarity: {cosine_sim:.4f}")
    logger.info(f"    Fuzz token-sort:   {fuzz_ratio:.4f}")
    logger.info(f"    Combined score:    {combined:.1f}/100")

    return {
        "combined_score": round(combined, 2),
        "cosine_similarity": round(cosine_sim, 4),
        "fuzz_ratio": round(fuzz_ratio, 4),
    }


def classify_match(score: float, rule_result: dict, attrs_a: dict, attrs_b: dict) -> tuple:
    """
    Classify a match pair into the 5-way taxonomy and return adjusted score.

    Step 7 — Match Classification:
      - Identical:                      >=95% score + all attributes exact
      - Duplicate:                      attributes exact, minor wording difference
      - Near-Duplicate:                 one non-critical attribute differs, or 80-95% score
      - Functionally Equivalent Candidate: same function, different spec
      - No Match:                       below threshold, or hard constraint failed

    Args:
        score: Combined AI score (0-100)
        rule_result: Output from rule_engine.check_hard_constraints()
        attrs_a: Extracted attributes for item A
        attrs_b: Extracted attributes for item B

    Returns:
        Tuple of (classification_label: str, adjusted_score: float)
    """
    # Hard constraint failed -> capped
    if not rule_result["passed"]:
        failed = rule_result["failed_attributes"]
        logger.info(f"  📋 Classification: No Match (hard constraint failed: {failed})")
        return "No Match", min(score, 15.0)

    # Check for functionally equivalent interchangeable differences
    has_interchangeable_diffs = len(rule_result.get("interchangeable_diffs", [])) > 0
    if has_interchangeable_diffs:
        adjusted_score = min(score, 79.9)
        logger.info(f"  📋 Classification: Functionally Equivalent Candidate (interchangeable diffs: {rule_result['interchangeable_diffs']}, score capped from {score:.1f} to {adjusted_score:.1f})")
        return "Functionally Equivalent Candidate", adjusted_score

    # Hard constraints passed — check score thresholds
    has_non_critical_diffs = len(rule_result.get("non_critical_diffs", [])) > 0

    if has_non_critical_diffs:
        adjusted_score = min(score, 84.9)
        logger.info(f"  📋 Classification: Near-Duplicate (non-critical diffs: {rule_result['non_critical_diffs']}, score capped from {score:.1f} to {adjusted_score:.1f})")
        return "Near-Duplicate", adjusted_score

    if score >= 95:
        logger.info(f"  📋 Classification: Identical (score={score:.1f}%, all attributes match)")
        return "Identical", score
    elif score >= 85:
        logger.info(f"  📋 Classification: Duplicate (score={score:.1f}%, attributes match, minor wording diff)")
        return "Duplicate", score
    elif score >= 80:
        logger.info(f"  📋 Classification: Near-Duplicate (score={score:.1f}%)")
        return "Near-Duplicate", score
    else:
        logger.info(f"  📋 Classification: No Match (score={score:.1f}% below threshold)")
        return "No Match", score
