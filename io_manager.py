def display_result(record):
    """Print the result of one check."""
    result = record["result"]
    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)
    print("Risk level: " + result["risk_level"])
    print("Reason:     " + result["reason"])
    if record["from_saved"]:
        print("(Same chat and details as before - reused the saved AI answer.)")

    if result["risk_factors"]:
        print()
        print("Warning signs:")
        for factor in result["risk_factors"]:
            print(" - " + factor)

    if result["missing_information"]:
        print()
        print("Missing information:")
        for item in result["missing_information"]:
            print(" - " + item)

    if result["evidence"]:
        print()
        print("Evidence from the chat:")
        for quote in result["evidence"]:
            print(" - " + quote)

    print()
    print("What to do: " + result["action"])
    print("Note: this is advice to help you decide, not proof that someone is a scammer.")
    print("=" * 60)
