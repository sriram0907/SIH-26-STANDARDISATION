import csv
import sqlite3

def get_equivalence_group(local_code, canon_id):
    if local_code in ["CPSE-A-TRAP-1067", "CPSE-B-TRAP-1068"]:
        return "GROUP_TRAP_1_304"
    if canon_id in ["BOLT-001", "TRAP-004", "TRAP-005", "TRAP-006"]:
        return "GROUP_BOLT_001"
    # TRAP-001 (1066) is SS310, BOLT-001 is SS316. They should NOT match.
    if local_code == "CPSE-A-TRAP-1066":
        return "GROUP_TRAP_1_310"
    if canon_id == "TRAP-003":
        return "GROUP_TRAP_003"
    return canon_id

def main():
    # 1. Load ground truth
    local_to_group = {}
    items = []
    with open("data/ground_truth.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            group = get_equivalence_group(row["local_code"], row["canonical_id"])
            local_to_group[row["local_code"]] = group
            items.append(row["local_code"])

    # Build Actual Positives (all pairs of local_codes that share a group)
    actual_positives = set()
    for i in range(len(items)):
        for j in range(i+1, len(items)):
            a, b = items[i], items[j]
            # Must be from different CPSEs based on business logic!
            if a.split('-')[1] != b.split('-')[1]:
                if local_to_group[a] == local_to_group[b]:
                    actual_positives.add(tuple(sorted([a, b])))

    # 2. Load predicted matches from DB
    predicted_positives = set()
    conn = sqlite3.connect("db/harmonize.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i_a.local_code, i_b.local_code, m.status, m.match_type 
        FROM match_pairs m
        JOIN items i_a ON m.item_a_id = i_a.id
        JOIN items i_b ON m.item_b_id = i_b.id
    """)
    for row in cursor.fetchall():
        code_a, code_b, status, match_type = row
        pair = tuple(sorted([code_a, code_b]))
        # if pending or auto-approved, it's a positive prediction
        if status in ["pending", "auto-approved"]:
            predicted_positives.add(pair)
    conn.close()

    # 3. Compute metrics
    tp = len(actual_positives.intersection(predicted_positives))
    fp = len(predicted_positives - actual_positives)
    fn = len(actual_positives - predicted_positives)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    print("\n" + "="*50)
    print("📊 AUTOMATED VALIDATION AGAINST GROUND TRUTH")
    print("="*50)
    print(f"True Positives  (TP) : {tp}")
    print(f"False Positives (FP) : {fp}")
    print(f"False Negatives (FN) : {fn}")
    print(f"Precision            : {precision:.1%}")
    print(f"Recall               : {recall:.1%}")
    print("="*50 + "\n")

    if fp > 0:
        print("False Positives:")
        for pair in (predicted_positives - actual_positives):
            print(f"  {pair[0]} (Group: {local_to_group.get(pair[0], 'Unknown')}) <-> {pair[1]} (Group: {local_to_group.get(pair[1], 'Unknown')})")
    
    if fn > 0:
        print("False Negatives Details:")
        
        # Connect to DB to get item details
        conn = sqlite3.connect("db/harmonize.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        for pair in (actual_positives - predicted_positives):
            code_a, code_b = pair[0], pair[1]
            
            # Get item A details
            cursor.execute("SELECT raw_description, attributes FROM items WHERE local_code = ?", (code_a,))
            item_a = cursor.fetchone()
            
            # Get item B details
            cursor.execute("SELECT raw_description, attributes FROM items WHERE local_code = ?", (code_b,))
            item_b = cursor.fetchone()
            
            # See if they were evaluated and blocked by rule engine
            cursor.execute("""
                SELECT evidence FROM match_pairs m 
                JOIN items ia ON m.item_a_id = ia.id 
                JOIN items ib ON m.item_b_id = ib.id 
                WHERE (ia.local_code = ? AND ib.local_code = ?) OR (ia.local_code = ? AND ib.local_code = ?)
            """, (code_a, code_b, code_b, code_a))
            
            match_row = cursor.fetchone()
            
            print(f"\n--- FN Pair: {code_a} <-> {code_b} (Group: {local_to_group.get(code_a, 'Unknown')}) ---")
            if item_a and item_b:
                print(f"  Item A: {item_a['raw_description']}")
                print(f"  Item B: {item_b['raw_description']}")
                print(f"  Attrs A: {item_a['attributes']}")
                print(f"  Attrs B: {item_b['attributes']}")
            
            if match_row:
                import json
                evidence = json.loads(match_row['evidence'])
                rule_ev = evidence.get("rule_engine", {})
                print(f"  Rule Engine Passed: {rule_ev.get('passed')}")
                if not rule_ev.get("passed"):
                    print(f"  Failed Attributes: {rule_ev.get('failed_attributes')}")
                    # Print why it failed
                    details = rule_ev.get("attribute_details", {})
                    for attr in rule_ev.get('failed_attributes', []):
                        if attr in details:
                            print(f"    - {attr}: '{details[attr].get('item_a')}' vs '{details[attr].get('item_b')}'")
            else:
                print("  (Not evaluated by matcher — likely blocked by category mismatch or pre-filter)")
                
        conn.close()


if __name__ == "__main__":
    main()
