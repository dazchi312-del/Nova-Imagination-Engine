"""
Nova Core Scoring Module
Weighted score calculation for NOE dimension scores
"""

# Default weights from noe_config.yaml
WEIGHTS = {
    "quality": 0.30,
    "clarity": 0.25,
    "structure": 0.20,
    "hallucination_risk": 0.15,
    "identity_alignment": 0.10
}


def calculate_weighted_score(scores: dict, weights: dict = None) -> float:
    """
    Calculate weighted average from dimension scores.
    
    Args:
        scores: Dict with dimension names as keys, 0.0-1.0 scores as values
        weights: Optional custom weights (defaults to NOE standard weights)
    
    Returns:
        Weighted score between 0.0 and 1.0
    
    Note:
        hallucination_risk is INVERTED - lower risk = higher contribution
    """
    if weights is None:
        weights = WEIGHTS
    
    total = 0.0
    weight_sum = 0.0
    
    for dimension, weight in weights.items():
        if dimension in scores:
            value = scores[dimension]
            
            # Invert hallucination_risk (0.2 risk = 0.8 contribution)
            if dimension == "hallucination_risk":
                value = 1.0 - value
            
            total += value * weight
            weight_sum += weight
    
    # Normalize in case not all dimensions present
    if weight_sum > 0:
        return total / weight_sum
    
    return 0.0


def score_breakdown(scores: dict, weights: dict = None) -> dict:
    """
    Get detailed breakdown of score contributions.
    
    Returns dict with each dimension's weighted contribution.
    """
    if weights is None:
        weights = WEIGHTS
    
    breakdown = {}
    
    for dimension, weight in weights.items():
        if dimension in scores:
            value = scores[dimension]
            
            if dimension == "hallucination_risk":
                effective = 1.0 - value
                breakdown[dimension] = {
                    "raw": value,
                    "effective": effective,
                    "weight": weight,
                    "contribution": effective * weight
                }
            else:
                breakdown[dimension] = {
                    "raw": value,
                    "effective": value,
                    "weight": weight,
                    "contribution": value * weight
                }
    
    breakdown["total"] = calculate_weighted_score(scores, weights)
    
    return breakdown


if __name__ == "__main__":
    # Test with sample scores
    test_scores = {
        "quality": 0.85,
        "clarity": 0.90,
        "structure": 0.80,
        "hallucination_risk": 0.15,
        "identity_alignment": 0.95
    }
    
    print("Test Scores:", test_scores)
    print(f"Weighted Score: {calculate_weighted_score(test_scores):.3f}")
    print("\nBreakdown:")
    for k, v in score_breakdown(test_scores).items():
        if k != "total":
            print(f"  {k}: {v['contribution']:.3f} ({v['raw']:.2f} × {v['weight']})")
        else:
            print(f"  TOTAL: {v:.3f}")
