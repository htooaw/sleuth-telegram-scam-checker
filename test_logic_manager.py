# Tests for the risk score rules, using hardcoded sample AI answers
# No API calls, so these run anywhere, including inside Docker and CI
# Run with: pytest

import ai_manager
import logic_manager

def make_ai_output(**changes):
    """A clean AI answer with no warning signs. Pass fields to change, e.g. advance_fee_detected=True."""
    ai_output = {
        "transaction_summary": "Buyer wants to buy a used phone.",
        "advance_fee_detected": False,
        "payment_plausibility": "High",
        "payment_diversion_detected": False,
        "social_engineering_tactics": [],
        "inconsistencies": [],
        "missing_information": [],
        "other_risk_indicators": [],
        "evidence": [],
    }
    ai_output.update(changes)
    return ai_output

def test_clean_deal_scores_zero():
    result = logic_manager.evaluate_risk(make_ai_output())
    assert result["score"] == 0
    assert result["risk_level"] == "Low Risk"
    assert result["risk_factors"] == []

def test_advance_fee_adds_two_points():
    result = logic_manager.evaluate_risk(make_ai_output(advance_fee_detected=True))
    assert result["score"] == 2
    assert result["risk_level"] == "Medium Risk"

def test_each_other_warning_sign_adds_one_point():
    assert logic_manager.evaluate_risk(make_ai_output(payment_plausibility="Low"))["score"] == 1
    assert logic_manager.evaluate_risk(make_ai_output(payment_diversion_detected=True))["score"] == 1
    assert logic_manager.evaluate_risk(make_ai_output(inconsistencies=["name differs"]))["score"] == 1
    assert logic_manager.evaluate_risk(make_ai_output(social_engineering_tactics=["urgency"]))["score"] == 1

def test_one_missing_detail_adds_nothing():
    result = logic_manager.evaluate_risk(make_ai_output(missing_information=["meetup place"]))
    assert result["score"] == 0

def test_two_missing_details_add_one_point():
    result = logic_manager.evaluate_risk(make_ai_output(missing_information=["meetup place", "condition"]))
    assert result["score"] == 1

def test_classic_scam_pattern_is_high_risk():
    result = logic_manager.evaluate_risk(make_ai_output(
        advance_fee_detected=True,
        payment_plausibility="Low",
        inconsistencies=["seller name differs from PayNow name"],
    ))
    assert result["score"] == 4
    assert result["risk_level"] == "High Risk"

def test_score_never_goes_above_five():
    result = logic_manager.evaluate_risk(make_ai_output(
        advance_fee_detected=True,
        payment_plausibility="Low",
        payment_diversion_detected=True,
        inconsistencies=["x"],
        social_engineering_tactics=["urgency"],
        missing_information=["a", "b"],
    ))
    assert result["score"] == 5
    assert result["max_score"] == 5

def test_score_to_level_boundaries():
    assert logic_manager.score_to_level(0) == "Low Risk"
    assert logic_manager.score_to_level(1) == "Low Risk"
    assert logic_manager.score_to_level(2) == "Medium Risk"
    assert logic_manager.score_to_level(3) == "Medium Risk"
    assert logic_manager.score_to_level(4) == "High Risk"
    assert logic_manager.score_to_level(5) == "High Risk"

def test_missing_fields_do_not_crash():
    result = logic_manager.evaluate_risk({})
    assert result["score"] == 0
    assert result["missing_information"] == []
    assert result["evidence"] == []

def test_result_passes_evidence_through():
    result = logic_manager.evaluate_risk(make_ai_output(evidence=['"pay deposit first"']))
    assert result["evidence"] == ['"pay deposit first"']

def test_malformed_ai_answer_is_rejected():
    data, problems = ai_manager.parse_ai_text("this is not JSON")
    assert data is None
    assert problems == ["AI answer is not valid JSON"]

def test_ai_answer_with_missing_field_is_rejected():
    data, problems = ai_manager.parse_ai_text('{"transaction_summary": "x"}')
    assert data is None
    assert "missing field: advance_fee_detected" in problems

def test_feedback_answer_is_checked():
    assert ai_manager.validate_feedback({"feedback": "Risky deal.", "next_steps": ["Meet in person"]}) == []
    assert ai_manager.validate_feedback({"feedback": "", "next_steps": []}) != []

def test_other_risk_indicators_add_one_point():
    result = logic_manager.evaluate_risk(
        make_ai_output(
            other_risk_indicators=["Unusual payment instructions"]
        )
    )

    assert result["score"] == 1
    assert result["risk_level"] == "Low Risk"
    assert any(
        "Unusual payment instructions" in factor
        for factor in result["risk_factors"]
    )


def test_malformed_list_fields_do_not_crash():
    result = logic_manager.evaluate_risk(
        {
            "missing_information": None,
            "evidence": None,
            "inconsistencies": "not a list",
            "social_engineering_tactics": None,
            "other_risk_indicators": None,
        }
    )

    assert result["score"] == 0
    assert result["missing_information"] == []
    assert result["evidence"] == []
    assert result["risk_factors"] == []