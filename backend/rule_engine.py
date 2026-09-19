"""
Step 5 — Rule Engine (Hard Constraint Check)
=============================================
Checks must-match attributes for same-category pairs.
If ANY must-match attribute differs, the pair is HARD-CAPPED
regardless of AI similarity score.
"""

import json
import logging

logger = logging.getLogger(__name__)

# Must-match attributes per category — if ANY of these differ,
# the pair cannot be classified as Identical or Duplicate.
MUST_MATCH_ATTRIBUTES = {
    "Bolt": ["material", "diameter", "length", "standard"],
    "Valve": ["type", "size", "pressure_rating", "body_material"],
}

# Non-critical attributes — differences here result in Near-Duplicate, not No Match
NON_CRITICAL_ATTRIBUTES = {
    "Bolt": ["thread"],
    "Valve": ["end_connection"],
}

# Values that are functionally interchangeable
INTERCHANGEABLE_VALUES = {
    "material": [{"STAINLESS STEEL 316", "STAINLESS STEEL 316L"}],
    "standard": [{"DIN 933", "ISO 4017"}],
}


def check_hard_constraints(attrs_a: dict, attrs_b: dict, category: str) -> dict:
    """
    Compare two items' attributes against must-match rules.

    Returns:
        dict with keys:
          - passed: bool — True if all must-match attributes are identical
          - failed_attributes: list of attribute names that differ
          - matched_attributes: list of attribute names that match
          - evidence: dict with per-attribute comparison details
          - non_critical_diffs: list of non-critical attributes that differ
    """
    must_match = MUST_MATCH_ATTRIBUTES.get(category, [])
    non_critical = NON_CRITICAL_ATTRIBUTES.get(category, [])

    failed_attributes = []
    matched_attributes = []
    non_critical_diffs = []
    interchangeable_diffs = []
    evidence = {}

    # Check must-match attributes
    for attr in must_match:
        val_a = (attrs_a.get(attr) or "").strip().upper()
        val_b = (attrs_b.get(attr) or "").strip().upper()

        evidence[attr] = {"item_a": attrs_a.get(attr), "item_b": attrs_b.get(attr)}

        if val_a == "" and val_b == "":
            # Both unknown — skip, don't penalize
            evidence[attr]["match"] = None  # unknown
            logger.info(f"    ? {attr}: both unknown — skipped")
        elif val_a == val_b:
            matched_attributes.append(attr)
            evidence[attr]["match"] = True
        else:
            # Check if interchangeable
            is_interchangeable = False
            if attr in INTERCHANGEABLE_VALUES:
                for equiv_set in INTERCHANGEABLE_VALUES[attr]:
                    if val_a in equiv_set and val_b in equiv_set:
                        is_interchangeable = True
                        break
            
            if is_interchangeable:
                interchangeable_diffs.append(attr)
                evidence[attr]["match"] = False
                logger.info(f"    ~ {attr}: interchangeable values '{val_a}' vs '{val_b}'")
            else:
                failed_attributes.append(attr)
                evidence[attr]["match"] = False

    # Check non-critical attributes
    for attr in non_critical:
        val_a = (attrs_a.get(attr) or "").strip().upper()
        val_b = (attrs_b.get(attr) or "").strip().upper()

        evidence[attr] = {"item_a": attrs_a.get(attr), "item_b": attrs_b.get(attr)}

        if val_a == "" and val_b == "":
            evidence[attr]["match"] = None  # unknown
        elif val_a == val_b:
            matched_attributes.append(attr)
            evidence[attr]["match"] = True
        else:
            non_critical_diffs.append(attr)
            evidence[attr]["match"] = False

    passed = len(failed_attributes) == 0

    if passed:
        logger.info(f"  ✅ Rule engine PASSED — all must-match attributes identical")
    else:
        logger.info(f"  ❌ Rule engine FAILED — differing attributes: {failed_attributes}")

    for attr, detail in evidence.items():
        status = "✓" if detail["match"] else "✗"
        logger.info(f"    {status} {attr}: '{detail['item_a']}' vs '{detail['item_b']}'")

    return {
        "passed": passed,
        "failed_attributes": failed_attributes,
        "matched_attributes": matched_attributes,
        "non_critical_diffs": non_critical_diffs,
        "interchangeable_diffs": interchangeable_diffs,
        "evidence": evidence,
    }
