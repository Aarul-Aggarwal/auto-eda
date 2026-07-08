"""Generates examples/messy.csv — a deliberately dirty demo dataset."""

import random

random.seed(7)

header = "customer_id,name,city,signup_date,age,income,plan,churn,notes\n"
cities = ["New York", "new york", "NEW YORK", "Boston", "boston", "Chicago", "Seattle"]
plans = ["basic", "Basic", "premium", "PREMIUM", "enterprise"]
nulls = ["", "N/A", "-", "?", "null"]

rows = []
for i in range(1, 501):
    name = f"Customer {i}"
    city = random.choice(cities)
    date = f"{random.randint(2019, 2024)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    age = str(random.randint(18, 75)) if random.random() > 0.08 else random.choice(nulls)
    income = f"{random.randint(20, 180) * 1000}"
    if random.random() < 0.02:
        income = f"{random.randint(2, 9) * 1_000_000}"  # unit-error outliers
    if random.random() < 0.12:
        income = random.choice(nulls)
    plan = random.choice(plans)
    if random.random() < 0.05:
        plan = " " + plan + " "  # stray whitespace
    churn = "yes" if random.random() < 0.08 else "no"  # imbalanced target
    notes = random.choice(nulls) if random.random() < 0.85 else "vip"
    rows.append(f"{i},{name},{city},{date},{age},{income},{plan},{churn},{notes}")

# exact duplicates
for _ in range(15):
    rows.append(random.choice(rows[:200]))

with open("examples/messy.csv", "w", newline="\n") as f:
    f.write(header)
    f.write("\n".join(rows) + "\n")

print(f"wrote examples/messy.csv with {len(rows)} rows")
