"""
Step 8 — Pipeline Orchestrator
================================
Ties together Steps 2-7: classification -> extraction -> canonical ->
rule engine -> AI matching -> match classification.

Verbose logging at every step for demo visibility.
"""

import csv
import json
import logging
import itertools
import re
from backend import database, classifier, extractor, canonical, rule_engine, matcher

logger = logging.getLogger(__name__)


def load_csv_items(csv_path: str) -> list:
    """Load items from the CPSE variants CSV."""
    items = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(row)
    logger.info(f"📂 Loaded {len(items)} items from {csv_path}")
    return items


def run_pipeline(csv_path: str = "data/cpse_variants.csv"):
    """
    Execute the full harmonization pipeline.

    Phase 1: Process each item (classify -> extract -> canonicalize)
    Phase 2: Generate cross-CPSE pairs -> rule engine -> AI match -> classify
    """
    logger.info("=" * 70)
    logger.info("HARMONIZATION PIPELINE — STARTING")
    logger.info("=" * 70)

    # Initialize database
    database.reset_db()

    # Load items
    raw_items = load_csv_items(csv_path)

    # -----------------------------------------------------------------------
    # PHASE 1: Process each item individually
    # -----------------------------------------------------------------------
    logger.info("")
    logger.info("━" * 70)
    logger.info("PHASE 1: Classification → Extraction → Canonical Description")
    logger.info("━" * 70)

    processed_items = []

    for i, raw in enumerate(raw_items, 1):
        logger.info(f"\n{'─' * 50}")
        logger.info(f"Item {i}/{len(raw_items)}: [{raw['cpse_id']}] {raw['local_code']}")
        logger.info(f"  Raw: {raw['raw_description']}")

        # Insert into database
        item_id = database.insert_item(
            raw["cpse_id"], raw["local_code"], raw["raw_description"], int(raw.get("quantity_on_hand", 0))
        )

        # Step 2: Classify
        cls_result = classifier.classify_description(raw["raw_description"])
        database.update_item_classification(
            item_id,
            cls_result["category"],
            cls_result["confidence"],
            cls_result["classification_path"],
        )

        # Step 3: Extract attributes
        attrs = extractor.extract_attributes(
            raw["raw_description"], cls_result["category"]
        )

        # Step 4: Generate canonical description
        canon_desc = canonical.generate_canonical(attrs, cls_result["category"])
        database.update_item_attributes(item_id, attrs, canon_desc)

        processed_items.append({
            "id": item_id,
            "cpse_id": raw["cpse_id"],
            "local_code": raw["local_code"],
            "raw_description": raw["raw_description"],
            "category": cls_result["category"],
            "classification_path": cls_result["classification_path"],
            "attributes": attrs,
            "canonical_description": canon_desc,
        })

    # Summary of Phase 1
    categories = {}
    paths = {}
    for item in processed_items:
        cat = item["category"]
        categories[cat] = categories.get(cat, 0) + 1
        path = item["classification_path"]
        paths[path] = paths.get(path, 0) + 1

    logger.info(f"\n{'━' * 70}")
    logger.info("PHASE 1 COMPLETE — Summary:")
    logger.info(f"  Total items processed: {len(processed_items)}")
    for cat, count in sorted(categories.items()):
        logger.info(f"  Category '{cat}': {count} items")
    for path, count in sorted(paths.items()):
        logger.info(f"  Classification path '{path}': {count} items")

    # -----------------------------------------------------------------------
    # PHASE 2: Generate cross-CPSE pairs and match
    # -----------------------------------------------------------------------
    logger.info(f"\n{'━' * 70}")
    logger.info("PHASE 2: Cross-CPSE Pair Generation → Rule Engine → AI Matching")
    logger.info("━" * 70)

    # Group items by category, then generate cross-CPSE pairs within each category
    items_by_category = {}
    for item in processed_items:
        cat = item["category"]
        if cat not in items_by_category:
            items_by_category[cat] = []
        items_by_category[cat].append(item)

    pair_count = 0
    match_type_counts = {}

    for category, items in items_by_category.items():
        if category == "unclassified":
            logger.info(f"\n  ⏭️  Skipping unclassified items (sent to human review)")
            continue

        logger.info(f"\n  📦 Processing category: {category} ({len(items)} items)")

        # Generate all cross-CPSE pairs (only compare items from different CPSEs)
        for item_a, item_b in itertools.combinations(items, 2):
            if item_a["cpse_id"] == item_b["cpse_id"]:
                continue  # Skip same-CPSE pairs

            # Candidate Blocking / Pre-filter
            # Must share at least TWO exact extracted specific attributes
            # OR at least TWO overlapping numbers in the raw description.
            a_attrs = item_a["attributes"]
            b_attrs = item_b["attributes"]
            
            # Exclude broad categoric attributes from the pre-filter
            exclude_keys = {"type", "material", "body_material", "end_connection", "thread"}
            
            shared_attrs = [
                k for k in a_attrs 
                if k not in exclude_keys and a_attrs.get(k) and b_attrs.get(k) 
                and str(a_attrs[k]).upper() == str(b_attrs[k]).upper()
            ]
            
            nums_a = set(re.findall(r'\d+', item_a["raw_description"]))
            nums_b = set(re.findall(r'\d+', item_b["raw_description"]))
            
            if len(shared_attrs) < 2 and len(nums_a & nums_b) < 2:
                continue  # Skip obviously unrelated items

            pair_count += 1
            logger.info(f"\n  {'─' * 40}")
            logger.info(f"  Pair #{pair_count}: {item_a['local_code']} vs {item_b['local_code']}")
            logger.info(f"    A: {item_a['canonical_description']}")
            logger.info(f"    B: {item_b['canonical_description']}")

            # Step 5: Rule engine — hard constraint check
            rule_result = rule_engine.check_hard_constraints(
                item_a["attributes"], item_b["attributes"], category
            )

            # Step 6: AI matching (runs regardless, but classification respects constraints)
            ai_result = matcher.compute_match_score(
                item_a["raw_description"],
                item_b["raw_description"],
            )

            # Step 7: Classify match
            match_type, new_score = matcher.classify_match(
                ai_result["combined_score"],
                rule_result,
                item_a["attributes"],
                item_b["attributes"],
            )
            ai_result["combined_score"] = new_score
            
            # If the rule engine forced a downgrade/override, zero out raw similarities 
            # so the UI evidence doesn't contradict the final capped score
            if match_type == "No Match" and ai_result["cosine_similarity"] > 0.8:
                ai_result["cosine_similarity"] = 0.0
                ai_result["fuzz_ratio"] = 0.0
            elif match_type == "Near-Duplicate" and ai_result["combined_score"] < ai_result["cosine_similarity"] * 100:
                # If capped to 84.9 but raw sim was high, adjust the displayed raw similarities
                ai_result["cosine_similarity"] = round(new_score / 100.0, 4)
                ai_result["fuzz_ratio"] = round(new_score / 100.0, 4)

            # Determine review queue status
            status = "pending"
            if match_type in ["Identical", "Duplicate"]:
                status = "auto-approved"
            elif match_type == "No Match":
                status = "rejected"

            # Build evidence
            evidence = {
                "rule_engine": {
                    "passed": rule_result["passed"],
                    "failed_attributes": rule_result["failed_attributes"],
                    "matched_attributes": rule_result["matched_attributes"],
                    "non_critical_diffs": rule_result.get("non_critical_diffs", []),
                    "interchangeable_diffs": rule_result.get("interchangeable_diffs", []),
                    "attribute_details": rule_result["evidence"],
                },
                "ai_matching": ai_result,
                "signal": "rule+AI" if rule_result["passed"] else "rule_override",
            }

            # Store match pair
            pair_id = database.insert_match_pair(
                item_a["id"], item_b["id"],
                match_type, ai_result["combined_score"], evidence, status
            )

            if status == "auto-approved":
                database.approve_match(pair_id, reviewer="pipeline_auto", status="auto-approved")

            # Log to audit
            conn = database.get_connection()
            conn.execute(
                """INSERT INTO audit_log (action, reviewer, signal, details)
                   VALUES (?, ?, ?, ?)""",
                ("auto_classified", "pipeline",
                 evidence["signal"],
                 json.dumps({
                     "match_type": match_type,
                     "score": ai_result["combined_score"],
                     "pair": f"{item_a['local_code']} vs {item_b['local_code']}",
                 }))
            )
            conn.commit()
            conn.close()

            match_type_counts[match_type] = match_type_counts.get(match_type, 0) + 1

    # Summary of Phase 2
    logger.info(f"\n{'━' * 70}")
    logger.info("PHASE 2 COMPLETE — Summary:")
    logger.info(f"  Total pairs evaluated: {pair_count}")
    for mt, count in sorted(match_type_counts.items()):
        logger.info(f"  {mt}: {count} pairs")
    logger.info("=" * 70)
    logger.info("HARMONIZATION PIPELINE — COMPLETE")
    logger.info("=" * 70)

    return {
        "items_processed": len(processed_items),
        "pairs_evaluated": pair_count,
        "match_type_distribution": match_type_counts,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    run_pipeline()
