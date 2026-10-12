def display_history(records):
    print()
    if not records:
        print("No matching past checks.")
        return

    print("Past checks:")
    number = 1
    for record in records:
        deal = record["input"]
        print(str(number) + ". " + record["time"] + " | " + deal["chat"] + " | "
              + deal["item"] + " | SGD " + format(deal["price"], ".2f") + " | "
              + record["result"]["risk_level"])
        number += 1