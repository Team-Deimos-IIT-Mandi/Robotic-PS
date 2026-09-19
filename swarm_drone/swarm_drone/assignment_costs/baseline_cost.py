def calculate_baseline_score(feasible):
    if feasible:
        best_candidate = min(feasible, key=lambda c: c.get("cost", float('inf')))
        return best_candidate, f"Best scoring idle drone (cost: {best_candidate.get('cost', 0):.2f})"
    return None, "No drone available with sufficient time and return energy; retry later"
