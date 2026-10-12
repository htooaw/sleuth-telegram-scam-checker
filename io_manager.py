def ask_history_filter():
    print()
    print("Show which checks?")
    print("1. All")
    print("2. High Risk only")
    print("3. Medium Risk only")
    print("4. Low Risk only")
    while True:
        choice = input("Choose 1-4: ").strip()
        if choice == "1":
            return None              # None means "show everything"
        if choice == "2":
            return "High Risk"
        if choice == "3":
            return "Medium Risk"
        if choice == "4":
            return "Low Risk"
        show_error("Please type 1, 2, 3 or 4.")