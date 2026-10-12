# Apply deterministic business rules to validated AI scam-risk findings

MAX_SCORE = 5
MISSING_INFO_LIMIT = 2

def _get_list(ai_output, field):
    """Return a field as a list, or an empty list if it is invalid."""
    value = ai_output.get(field, [])
    return value if isinstance(value, list) else []

def calculate_score(ai_output):
    """Calculate a capped risk score and return its warning factors."""
    if not isinstance(ai_output, dict):
        ai_output = {}

    score = 0
    risk_factors = []

    # An advance-fee request receives greater weight
    if ai_output.get("advance_fee_detected") is True:
        score += 2
        risk_factors.append(
            "Asks for payment or a deposit before delivery"
        )

    if ai_output.get("payment_plausibility") == "Low":
        score += 1
        risk_factors.append(
            "Payment method looks unsafe or unusual"
        )

    if ai_output.get("payment_diversion_detected") is True:
        score += 1
        risk_factors.append(
            "Moves the deal to another app or payment account"
        )

    inconsistencies = _get_list(ai_output, "inconsistencies")
    if inconsistencies:
        score += 1
        risk_factors.append(
            "Contradictions found: " + "; ".join(map(str, inconsistencies))
        )

    tactics = _get_list(ai_output, "social_engineering_tactics")
    if tactics:
        score += 1
        risk_factors.append(
            "Pressure tactics: " + "; ".join(map(str, tactics))
        )

    other_indicators = _get_list(ai_output, "other_risk_indicators")
    if other_indicators:
        score += 1
        risk_factors.append(
            "Other warning signs: " + "; ".join(map(str, other_indicators))
        )

    missing_information = _get_list(ai_output, "missing_information")
    if len(missing_information) >= MISSING_INFO_LIMIT:
        score += 1
        risk_factors.append("Important deal details are missing")

    return min(score, MAX_SCORE), risk_factors

def score_to_level(score):
    """Map a score from zero to MAX_SCORE to a risk category."""
    if score >= 4:
        return "High Risk"
    if score >= 2:
        return "Medium Risk"
    return "Low Risk"

def evaluate_risk(ai_output):
    """Return the risk assessment for the AI output dictionary."""
    if not isinstance(ai_output, dict):
        ai_output = {}

    score, risk_factors = calculate_score(ai_output)

    return {
        "score": score,
        "max_score": MAX_SCORE,
        "risk_level": score_to_level(score),
        "risk_factors": risk_factors,
        "missing_information": _get_list(
            ai_output, "missing_information"
        ),
        "evidence": _get_list(ai_output, "evidence"),
    }