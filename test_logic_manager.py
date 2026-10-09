import logic_manager


test_cases = [
    {
        "name": "High Risk - all major conditions present",
        "ai_output": {
            "advance_fee_detected": True,
            "payment_plausibility": "Low",
            "inconsistencies": [
                "Seller changed the delivery arrangement"
            ]
        },
        "expected": "High Risk"
    },
    {
        "name": "Medium Risk - advance fee only",
        "ai_output": {
            "advance_fee_detected": True,
            "payment_plausibility": "High",
            "inconsistencies": []
        },
        "expected": "Medium Risk"
    },
    {
        "name": "Medium Risk - low plausibility only",
        "ai_output": {
            "advance_fee_detected": False,
            "payment_plausibility": "Low",
            "inconsistencies": []
        },
        "expected": "Medium Risk"
    },
    {
        "name": "Medium Risk - medium plausibility only",
        "ai_output": {
            "advance_fee_detected": False,
            "payment_plausibility": "Medium",
            "inconsistencies": []
        },
        "expected": "Medium Risk"
    },
    {
        "name": "Medium Risk - inconsistency only",
        "ai_output": {
            "advance_fee_detected": False,
            "payment_plausibility": "High",
            "inconsistencies": [
                "Seller provided conflicting payment instructions"
            ]
        },
        "expected": "Medium Risk"
    },
    {
        "name": "Medium Risk - advance fee and low plausibility",
        "ai_output": {
            "advance_fee_detected": True,
            "payment_plausibility": "Low",
            "inconsistencies": []
        },
        "expected": "Medium Risk"
    },
    {
        "name": "Medium Risk - advance fee and inconsistency",
        "ai_output": {
            "advance_fee_detected": True,
            "payment_plausibility": "High",
            "inconsistencies": [
                "Seller changed the delivery arrangement"
            ]
        },
        "expected": "Medium Risk"
    },
    {
        "name": "Medium Risk - low plausibility and inconsistency",
        "ai_output": {
            "advance_fee_detected": False,
            "payment_plausibility": "Low",
            "inconsistencies": [
                "Seller changed the payment instructions"
            ]
        },
        "expected": "Medium Risk"
    },
    {
        "name": "Medium Risk - missing plausibility",
        "ai_output": {
            "advance_fee_detected": False,
            "inconsistencies": []
        },
        "expected": "Medium Risk"
    },
    {
        "name": "Low Risk - no indicators",
        "ai_output": {
            "advance_fee_detected": False,
            "payment_plausibility": "High",
            "inconsistencies": []
        },
        "expected": "Low Risk"
    }
]


passed = 0

for test in test_cases:
    result = logic_manager.evaluate_risk({}, test["ai_output"])

    print(f"\n{test['name']}")
    print(f"Expected: {test['expected']}")
    print(f"Actual:   {result['risk_level']}")

    if result["risk_level"] == test["expected"]:
        print("PASS")
        passed += 1
    else:
        print("FAIL")

    print(f"Reason:   {result['reason']}")
    print(f"Action:   {result['action']}")


print("\n==============================")
print(f"Tests passed: {passed}/{len(test_cases)}")
print("==============================")