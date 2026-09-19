def calculate_assignment_score(features, max_distance, avg_flight_time):
    W_DEADLINE = 10.0
    W_ENERGY = 3.0
    W_DISTANCE = 1.0
    W_BALANCE = 2.0
    W_CHARGE = 4.0
    
    normalized_distance = features["raw_distance"] / max(max_distance, 1e-6)
    balance_cost = features["raw_utilization"] / max(avg_flight_time, 1e-6)
    
    score = (
        W_DEADLINE * features["deadline_cost"]
        + W_ENERGY * features["energy_cost"]
        + W_DISTANCE * normalized_distance
        + W_BALANCE * balance_cost
        + W_CHARGE * features["charging_risk"]
    )
    
    return {
        "score": score,
        "deadline": W_DEADLINE * features["deadline_cost"],
        "energy": W_ENERGY * features["energy_cost"],
        "distance": W_DISTANCE * normalized_distance,
        "balance": W_BALANCE * balance_cost,
        "charging": W_CHARGE * features["charging_risk"]
    }
