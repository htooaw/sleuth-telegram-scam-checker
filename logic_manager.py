def has_inconsistencies(inconsistencies: list[str]) -> bool:
    return isinstance(inconsistencies, list) and len(inconsistencies) > 0


def normalize_plausibility(plausibility: object) -> str:
    normalized = str(plausibility).strip().capitalize()

    if normalized in ["High", "Medium", "Low"]:
        return normalized

    return "Unknown"


def determine_risk_level(
    advance_fee: bool,
    plausibility: str,
    inconsistencies: list[str]
) -> str:
    conflicts_detected = has_inconsistencies(inconsistencies)

    # high risk:
    # all three major conditions must be present
    if advance_fee and plausibility == "Low" and conflicts_detected:
        return "High Risk"

    # medium risk:
    # one or more suspicious indicators are present, or the deal plausibility is uncertain
    if (
        advance_fee
        or plausibility in ["Medium", "Low", "Unknown"]
        or conflicts_detected
    ):
        return "Medium Risk"

    # low risk:
    # no current risk indicators detected and deal plausibility is high
    return "Low Risk"


def get_recommended_action(risk_level: str) -> str:
    if risk_level == "High Risk":
        return "Do not proceed until the transaction is independently verified."

    if risk_level == "Medium Risk":
        return "Verify the transaction details before proceeding."

    return "Proceed with standard platform safeguards."


def build_reason(
    advance_fee: bool,
    plausibility: str,
    inconsistencies: list[str]
) -> str:
    reasons = []

    if advance_fee:
        reasons.append("Potential advance fee or deposit request detected")

    if plausibility == "Low":
        reasons.append("Deal plausibility assessed as low")

    elif plausibility == "Medium":
        reasons.append("Deal plausibility assessed as medium")

    elif plausibility == "Unknown":
        reasons.append("Deal plausibility could not be determined")

    if has_inconsistencies(inconsistencies):
        reasons.extend(inconsistencies)

    if not reasons:
        return "No major risk factors detected."

    return " | ".join(reasons)


def evaluate_risk(input_record: dict, ai_output: dict) -> dict:
    # keeping input_record for compatibility with the application's
    # current interface and possible future transaction-based rules

    advance_fee = ai_output.get("advance_fee_detected", False)

    plausibility = normalize_plausibility(
        ai_output.get("payment_plausibility", "Unknown")
    )

    inconsistencies = ai_output.get("inconsistencies", [])

    risk_level = determine_risk_level(
        advance_fee,
        plausibility,
        inconsistencies
    )

    action = get_recommended_action(risk_level)

    reason = build_reason(
        advance_fee,
        plausibility,
        inconsistencies
    )

    return {
        "risk_level": risk_level,
        "action": action,
        "reason": reason
    }