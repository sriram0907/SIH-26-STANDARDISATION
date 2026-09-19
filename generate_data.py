"""
Step 1 — Synthetic Dataset Generator
=====================================
Generates realistic CPSE material descriptions with controlled variations,
near-miss traps, and ground-truth mapping for validation.

Output:
  - data/cpse_variants.csv   (cpse_id, local_code, raw_description)
  - data/ground_truth.csv    (canonical_id, cpse_id, local_code)
"""

import csv
import os
import random
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical items — the "truth" behind every variant
# ---------------------------------------------------------------------------

CANONICAL_BOLTS = [
    {"id": "BOLT-001", "type": "HEX BOLT",      "material": "Stainless Steel 316",  "diameter": "M10", "length": "50",  "standard": "DIN 933",  "thread": "Full Thread"},
    {"id": "BOLT-002", "type": "HEX BOLT",      "material": "Stainless Steel 304",  "diameter": "M12", "length": "80",  "standard": "DIN 931",  "thread": "Partial Thread"},
    {"id": "BOLT-003", "type": "HEX BOLT",      "material": "Carbon Steel",         "diameter": "M16", "length": "100", "standard": "DIN 933",  "thread": "Full Thread"},
    {"id": "BOLT-004", "type": "CARRIAGE BOLT",  "material": "Stainless Steel 316",  "diameter": "M8",  "length": "30",  "standard": "ISO 8677", "thread": "Full Thread"},
    {"id": "BOLT-005", "type": "CARRIAGE BOLT",  "material": "Carbon Steel",         "diameter": "M10", "length": "40",  "standard": "ISO 8677", "thread": "Full Thread"},
    {"id": "BOLT-006", "type": "STUD BOLT",     "material": "Alloy Steel B7",       "diameter": "M20", "length": "120", "standard": "ASTM A193","thread": "Full Thread"},
    {"id": "BOLT-007", "type": "STUD BOLT",     "material": "Stainless Steel 316",  "diameter": "M16", "length": "90",  "standard": "ASTM A193","thread": "Full Thread"},
    {"id": "BOLT-008", "type": "HEX BOLT",      "material": "Alloy Steel",          "diameter": "M24", "length": "150", "standard": "DIN 931",  "thread": "Partial Thread"},
    {"id": "BOLT-009", "type": "FLANGE BOLT",   "material": "Carbon Steel",         "diameter": "M12", "length": "35",  "standard": "DIN 6921", "thread": "Full Thread"},
    {"id": "BOLT-010", "type": "EYE BOLT",      "material": "Stainless Steel 304",  "diameter": "M16", "length": "60",  "standard": "DIN 580",  "thread": "Full Thread"},
    {"id": "BOLT-011", "type": "U-BOLT",        "material": "Carbon Steel",         "diameter": "M10", "length": "100", "standard": "IS 5570",  "thread": "Full Thread"},
    {"id": "BOLT-012", "type": "HEX BOLT",      "material": "Stainless Steel 316",  "diameter": "M20", "length": "70",  "standard": "DIN 933",  "thread": "Full Thread"},
    {"id": "BOLT-013", "type": "ANCHOR BOLT",   "material": "Carbon Steel",         "diameter": "M24", "length": "300", "standard": "IS 5624",  "thread": "Partial Thread"},
    {"id": "BOLT-014", "type": "HEX BOLT",      "material": "Stainless Steel 304",  "diameter": "M8",  "length": "25",  "standard": "DIN 933",  "thread": "Full Thread"},
    {"id": "BOLT-015", "type": "T-BOLT",        "material": "Carbon Steel",         "diameter": "M12", "length": "50",  "standard": "DIN 787",  "thread": "Full Thread"},
]

CANONICAL_VALVES = [
    {"id": "VALVE-001", "type": "GATE",       "size": "2\"",    "pressure_rating": "150#",  "body_material": "Carbon Steel",        "end_connection": "Flanged"},
    {"id": "VALVE-002", "type": "GATE",       "size": "4\"",    "pressure_rating": "300#",  "body_material": "Stainless Steel 316",  "end_connection": "Flanged"},
    {"id": "VALVE-003", "type": "BALL",       "size": "1\"",    "pressure_rating": "150#",  "body_material": "Stainless Steel 316",  "end_connection": "Threaded"},
    {"id": "VALVE-004", "type": "BALL",       "size": "2\"",    "pressure_rating": "300#",  "body_material": "Carbon Steel",        "end_connection": "Flanged"},
    {"id": "VALVE-005", "type": "CHECK",      "size": "3\"",    "pressure_rating": "150#",  "body_material": "Carbon Steel",        "end_connection": "Flanged"},
    {"id": "VALVE-006", "type": "CHECK",      "size": "1\"",    "pressure_rating": "800#",  "body_material": "Stainless Steel 304",  "end_connection": "Threaded"},
    {"id": "VALVE-007", "type": "GLOBE",      "size": "2\"",    "pressure_rating": "150#",  "body_material": "Carbon Steel",        "end_connection": "Flanged"},
    {"id": "VALVE-008", "type": "BUTTERFLY",  "size": "6\"",    "pressure_rating": "150#",  "body_material": "Cast Iron",           "end_connection": "Wafer"},
    {"id": "VALVE-009", "type": "NEEDLE",     "size": "1/2\"",  "pressure_rating": "6000#", "body_material": "Stainless Steel 316",  "end_connection": "Threaded"},
    {"id": "VALVE-010", "type": "PLUG",       "size": "2\"",    "pressure_rating": "150#",  "body_material": "Carbon Steel",        "end_connection": "Flanged"},
]

# Near-miss trap definitions — these create items that differ from a canonical
# item by exactly ONE critical attribute to test the rule engine.
NEAR_MISS_TRAPS = [
    # Trap 1: SS316 vs SS310 — material grade swap
    {
        "id": "TRAP-001", "category": "Bolt",
        "base_canonical": "BOLT-001",
        "type": "HEX BOLT", "material": "Stainless Steel 310",
        "diameter": "M10", "length": "50", "standard": "DIN 933", "thread": "Full Thread",
        "description": "HEX BOLT SS310 M10x50 DIN933 FULL THREAD",
        "trap_note": "SS310 vs SS316 — material grade difference"
    },
    # Trap 1: Slightly different material grade
    {
        "id": "TRAP-001", "category": "Bolt",
        "base_canonical": "BOLT-002",
        "type": "HEX BOLT", "material": "Stainless Steel 304", # canonical is 316
        "diameter": "M12", "length": "50", "standard": "DIN 933", "thread": "Full Thread",
        "description": "HEX BOLT, STAINLESS STEEL 304, M12 x 50 mm, DIN 933",
        "trap_note": "Critical attribute mismatch (Material) -> No Match"
    },
    {
        "id": "TRAP-001B", "category": "Bolt",
        "base_canonical": "BOLT-002",
        "type": "HEX BOLT", "material": "Stainless Steel 304",
        "diameter": "M12", "length": "50", "standard": "DIN 933", "thread": "Full Thread",
        "description": "HEX BOLT, STAINLESS STEEL 304, M12 x 50 mm, DIN 933",
        "trap_note": "Identical string match"
    },
    # Trap 3: DIN931 vs DIN933 — standard / thread type difference
    {
        "id": "TRAP-003", "category": "Bolt",
        "base_canonical": "BOLT-001",
        "type": "HEX BOLT", "material": "Stainless Steel 316",
        "diameter": "M10", "length": "50", "standard": "DIN 931", "thread": "Partial Thread",
        "description": "HEX BOLT STAINLESS STEEL 316 M10 x 50 DIN931 PARTIAL THD",
        "trap_note": "DIN931 vs DIN933 — standard / thread type difference"
    },
    # Trap 4: SS316 vs SS316L — functionally equivalent material
    {
        "id": "TRAP-004", "category": "Bolt",
        "base_canonical": "BOLT-001",
        "type": "HEX BOLT", "material": "Stainless Steel 316L",
        "diameter": "M10", "length": "50", "standard": "DIN 933", "thread": "Full Thread",
        "description": "HEX BOLT SS316L M10x50 DIN933 FULL THREAD",
        "trap_note": "SS316L vs SS316 — interchangeable material"
    },
    # Trap 5: DIN 933 vs ISO 4017 — functionally equivalent standard
    {
        "id": "TRAP-005", "category": "Bolt",
        "base_canonical": "BOLT-001",
        "type": "HEX BOLT", "material": "Stainless Steel 316",
        "diameter": "M10", "length": "50", "standard": "ISO 4017", "thread": "Full Thread",
        "description": "HEX BOLT SS316 M10x50 ISO4017",
        "trap_note": "ISO 4017 vs DIN 933 — interchangeable standard"
    },
    # Trap 6: Duplicate with heavy word variations
    {
        "id": "TRAP-006", "category": "Bolt",
        "base_canonical": "BOLT-001",
        "type": "HEX BOLT", "material": "Stainless Steel 316",
        "diameter": "M10", "length": "50", "standard": "DIN 933", "thread": "Full Thread",
        "description": "BOLT HEXAGONAL HEAD STAINLESS S. 316 METRIC 10 LENGTH 50MM STANDARD DIN 933",
        "trap_note": "Heavy wording variation but same exact attributes -> Duplicate"
    },
]

# ---------------------------------------------------------------------------
# Variation functions — produce realistic CPSE description differences
# ---------------------------------------------------------------------------

MATERIAL_ABBREVIATIONS = {
    "Stainless Steel 316": ["SS316", "SS 316", "S.S. 316", "Stainless Steel 316", "SSteel 316"],
    "Stainless Steel 304": ["SS304", "SS 304", "S.S. 304", "Stainless Steel 304", "SSteel 304"],
    "Stainless Steel 310": ["SS310", "SS 310", "S.S. 310", "Stainless Steel 310"],
    "Carbon Steel":        ["CS", "C.S.", "Carbon Steel", "CSteel", "C Steel"],
    "Alloy Steel B7":      ["B7", "Alloy B7", "ASTM B7", "Alloy Steel B7"],
    "Alloy Steel":         ["AS", "Alloy Steel", "Alloy Stl"],
    "Cast Iron":           ["CI", "C.I.", "Cast Iron"],
}

VALVE_TYPE_VARIANTS = {
    "GATE":      ["Gate", "GATE", "gate"],
    "BALL":      ["Ball", "BALL", "ball"],
    "CHECK":     ["Check", "CHECK", "Chk"],
    "GLOBE":     ["Globe", "GLOBE", "globe"],
    "BUTTERFLY": ["Butterfly", "BUTTERFLY", "Bfly"],
    "NEEDLE":    ["Needle", "NEEDLE", "Ndl"],
    "PLUG":      ["Plug", "PLUG", "plug"],
}

CONNECTION_VARIANTS = {
    "Flanged":  ["Flanged", "FLGD", "FLG", "Flg", "FLANGED"],
    "Threaded": ["Threaded", "THD", "THRD", "Thd", "THREADED"],
    "Wafer":    ["Wafer", "WAFER", "Wfr"],
}


def vary_bolt_description(bolt: dict, variant_index: int) -> str:
    """Generate a varied description for a bolt item."""
    material = random.choice(MATERIAL_ABBREVIATIONS.get(bolt["material"], [bolt["material"]]))
    diameter = bolt["diameter"]
    length = bolt["length"]
    standard = bolt["standard"]
    bolt_type = bolt["type"]

    # Vary dimension formatting
    dim_formats = [
        f"{diameter}x{length}",
        f"{diameter} x {length}",
        f"{diameter}x{length}mm",
        f"{diameter} x {length} mm",
        f"{diameter}X{length}MM",
        f"{diameter} x {length} MM",
    ]
    dim = random.choice(dim_formats)

    # Vary standard formatting
    std_formats = [standard, standard.replace(" ", ""), standard.lower(), standard.upper()]
    std = random.choice(std_formats)

    # Vary case of bolt type
    type_formats = [bolt_type, bolt_type.lower(), bolt_type.title()]
    bt = random.choice(type_formats)

    # Build description in different orders
    patterns = [
        f"{bt} {material} {dim} {std}",
        f"{material} {bt} {dim} {std}",
        f"{bt} {dim} {material} {std}",
        f"{std} {bt} {material} {dim}",
    ]

    # Optionally add thread info
    thread_variants = ["Full Thread", "FT", "Full Thd", "Partial Thread", "PT", "Partial Thd"]
    thread = bolt["thread"]
    if random.random() > 0.4:
        short_thread = thread if random.random() > 0.5 else (
            random.choice(["FT", "Full Thd"]) if "Full" in thread else random.choice(["PT", "Partial Thd"])
        )
        pattern = random.choice(patterns)
        return f"{pattern} {short_thread}"

    return random.choice(patterns)


def vary_valve_description(valve: dict, variant_index: int) -> str:
    """Generate a varied description for a valve item."""
    vtype = random.choice(VALVE_TYPE_VARIANTS.get(valve["type"], [valve["type"]]))
    material = random.choice(MATERIAL_ABBREVIATIONS.get(valve["body_material"], [valve["body_material"]]))
    connection = random.choice(CONNECTION_VARIANTS.get(valve["end_connection"], [valve["end_connection"]]))

    size = valve["size"]
    # Vary size formatting
    size_formats = [size, size.replace("\"", " inch"), size.replace("\"", "\""), size.replace("\"", " IN")]
    sz = random.choice(size_formats)

    pr = valve["pressure_rating"]
    # Vary pressure rating formatting
    pr_formats = [pr, pr.replace("#", " Class"), pr.replace("#", " CL"), pr.replace("#", "LB")]
    p = random.choice(pr_formats)

    patterns = [
        f"{vtype} Valve {sz} {p} {material} {connection}",
        f"{sz} {vtype} Valve {material} {p} {connection}",
        f"{material} {vtype} Valve {sz} {p} {connection}",
        f"{vtype} VLV {sz} {p} {material} {connection}",
    ]

    return random.choice(patterns)


def generate_dataset(output_dir: str = "data"):
    """Generate the synthetic CPSE variants CSV and ground truth CSV."""
    random.seed(42)  # Reproducibility for the demo

    os.makedirs(output_dir, exist_ok=True)

    variants_path = os.path.join(output_dir, "cpse_variants.csv")
    ground_truth_path = os.path.join(output_dir, "ground_truth.csv")

    cpse_ids = ["CPSE-A", "CPSE-B", "CPSE-C"]
    variants_rows = []
    ground_truth_rows = []
    local_code_counter = 1000

    # --- Generate bolt variants ---
    for bolt in CANONICAL_BOLTS:
        num_variants = random.choice([2, 3])
        assigned_cpses = random.sample(cpse_ids, num_variants)

        for i, cpse in enumerate(assigned_cpses):
            local_code = f"{cpse}-BLT-{local_code_counter}"
            local_code_counter += 1
            description = vary_bolt_description(bolt, i)

            variants_rows.append({
                "cpse_id": cpse,
                "local_code": local_code,
                "raw_description": description,
                "quantity_on_hand": random.randint(50, 800),
            })
            ground_truth_rows.append({
                "canonical_id": bolt["id"],
                "cpse_id": cpse,
                "local_code": local_code,
            })

            logger.info(f"  Generated bolt variant: {local_code} -> {description}")

    # --- Generate valve variants ---
    for valve in CANONICAL_VALVES:
        num_variants = random.choice([2, 3])
        assigned_cpses = random.sample(cpse_ids, num_variants)

        for i, cpse in enumerate(assigned_cpses):
            local_code = f"{cpse}-VLV-{local_code_counter}"
            local_code_counter += 1
            description = vary_valve_description(valve, i)

            variants_rows.append({
                "cpse_id": cpse,
                "local_code": local_code,
                "raw_description": description,
                "quantity_on_hand": random.randint(50, 800),
            })
            ground_truth_rows.append({
                "canonical_id": valve["id"],
                "cpse_id": cpse,
                "local_code": local_code,
            })

            logger.info(f"  Generated valve variant: {local_code} -> {description}")

    # --- Generate near-miss trap variants ---
    for trap in NEAR_MISS_TRAPS:
        if trap["id"] == "TRAP-001":
            cpse = "CPSE-A"
        elif trap["id"] == "TRAP-001B":
            cpse = "CPSE-B"
        else:
            cpse = random.choice(cpse_ids)
            
        local_code = f"{cpse}-TRAP-{local_code_counter}"
        local_code_counter += 1

        variants_rows.append({
            "cpse_id": cpse,
            "local_code": local_code,
            "raw_description": trap["description"],
            "quantity_on_hand": random.randint(50, 800),
        })
        ground_truth_rows.append({
            "canonical_id": trap["id"],
            "cpse_id": cpse,
            "local_code": local_code,
        })

        logger.info(f"  Generated NEAR-MISS TRAP: {local_code} -> {trap['description']} ({trap['trap_note']})")

    # --- Write CSVs ---
    with open(variants_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["cpse_id", "local_code", "raw_description", "quantity_on_hand"])
        writer.writeheader()
        writer.writerows(variants_rows)

    with open(ground_truth_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["canonical_id", "cpse_id", "local_code"])
        writer.writeheader()
        writer.writerows(ground_truth_rows)

    logger.info(f"✅ Generated {len(variants_rows)} variant descriptions -> {variants_path}")
    logger.info(f"✅ Generated {len(ground_truth_rows)} ground truth entries -> {ground_truth_path}")
    logger.info(f"   Including {len(NEAR_MISS_TRAPS)} near-miss traps")

    return variants_path, ground_truth_path


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("STEP 1: Synthetic Dataset Generation")
    logger.info("=" * 60)
    generate_dataset()
