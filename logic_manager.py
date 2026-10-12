MAX_SCORE = 5
MISSING_INFO_LIMIT = 2


def calculate_score(ai_output):
    """Add points for every warning sign the AI found. Returns (score, risk_factors)."""
    score = 0
    risk_factors = []

    if ai_output.get("advance_fee_detected"):
        score += 2
        risk_factors.append("Asks for payment or a deposit before delivery")
    if ai_output.get("payment_plausibility") == "Low":
        score += 1
        risk_factors.append("Payment method looks unsafe or unusual")
    if ai_output.get("payment_diversion_detected"):
        score += 1
        risk_factors.append("Moves the deal to another app or payment account")
    if ai_output.get("inconsistencies"):
        score += 1
        risk_factors.append("Contradictions found: " + "; ".join(ai_output["inconsistencies"]))
    if ai_output.get("social_engineering_tactics"):
        score += 1
        risk_factors.append("Pressure tactics: " + "; ".join(ai_output["social_engineering_tactics"]))
    if len(ai_output.get("missing_information", [])) >= MISSING_INFO_LIMIT:
        score += 1
        risk_factors.append("Important deal details are missing")

    return min(score, MAX_SCORE), risk_factors


def score_to_level(score):
    """Turn a score from 0 to 5 into a risk level."""
    if score >= 4:
        return "High Risk"
    if score >= 2:
        return "Medium Risk"
    return "Low Risk"


def evaluate_risk(ai_output):
    """Main entry point. ai_output is the "data" part of ai_manager.analyze_chat()."""
    score, risk_factors = calculate_score(ai_output)
    return {
        "score": score,
        "max_score": MAX_SCORE,
        "risk_level": score_to_level(score),
        "risk_factors": risk_factors,
        "missing_information": ai_output.get("missing_information", []),
        "evidence": ai_output.get("evidence", []),
    }
