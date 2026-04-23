"""
Generates sample_data/demo_transactions.csv
Run from the project root: python sample_data/generate_transactions.py
"""
import csv
import os
import random

random.seed(42)

MONTHS = [f"2024-{m:02d}" for m in range(1, 13)] + [f"2025-{m:02d}" for m in range(1, 5)]

# Slow then fast — accelerates sharply at month 9 (Sep 2024)
NEW_PER_MONTH = [8, 8, 9, 9, 10, 10, 11, 12, 18, 22, 25, 28, 30, 32, 35, 33]
assert sum(NEW_PER_MONTH) == 300

INDUSTRIES = (["SaaS"] * 35 + ["Fintech"] * 25 + ["Enterprise"] * 20
              + ["Healthcare"] * 12 + ["Logistics"] * 8) * 4
COUNTRIES = (["United States"] * 50 + ["United Kingdom"] * 15
             + ["Canada"] * 10 + ["Germany"] * 10
             + ["Australia"] * 8 + ["France"] * 7) * 4

MRR_POOL = [
    500, 600, 700, 800, 900,
    1000, 1200, 1400, 1500, 1800,
    2000, 2200, 2500, 2800, 3000,
    3500, 4000, 4500, 5000, 6000, 7000, 8000,
]
# Right-skew: smaller MRRs are more common
MRR_WEIGHTS = [12, 11, 10, 10, 9, 8, 7, 7, 6, 6, 5, 5, 4, 4, 3, 3, 2, 2, 2, 1, 1, 1]

WORDS_A = [
    "Acorn","Apex","Arc","Arrow","Atlas","Beacon","Birch","Bolt","Bridge","Cedar",
    "Cipher","Clay","Coast","Cobalt","Coda","Core","Crest","Crown","Dart","Dawn",
    "Depth","Drift","Dune","Echo","Edge","Ember","Epoch","Facet","Field","Flint",
    "Flux","Forge","Frame","Frost","Gate","Gem","Glint","Glow","Graph","Grove",
    "Haven","Helix","Helm","Hive","Hull","Icon","Index","Inlet","Iris","Jade",
    "Keel","Kelp","Keystone","Layer","Ledge","Lens","Level","Lime","Link","Lumen",
    "Lynx","Maple","Mast","Mesa","Mesh","Mint","Mist","Mode","Nexus","Node",
    "North","Nova","Opal","Orbit","Pace","Palm","Path","Peak","Pilot","Pine",
    "Pixel","Plume","Point","Port","Prism","Pulse","Quartz","Rail","Range","Ray",
    "Reed","Ridge","Rise","River","Root","Route","Rush","Sail","Scale","Seam",
    "Seed","Shade","Shell","Shift","Shore","Signal","Silo","Slate","Slope","Spark",
    "Sphere","Spin","Spring","Stack","Stage","Stem","Stone","Stream","Summit","Tide",
    "Timber","Token","Trace","Track","Trail","Vale","Vault","Vine","Vista","Volt",
    "Wave","Wedge","West","Wind","Wing","Wire","Yard","Zenith","Zone","Zinc",
]
WORDS_B = [
    "AI","Analytics","Cloud","Code","Data","Dynamics","Finance","Flow","HQ","Hub",
    "Intelligence","IO","Labs","Link","Logic","ML","Networks","Ops","Pay","Platform",
    "Pro","Security","Software","Solutions","Systems","Tech","Works","X","Yield","Zero",
]

all_names = list({f"{a} {b}" for a in WORDS_A for b in WORDS_B})
random.shuffle(all_names)
names = all_names[:300]


def to_domain(name: str) -> str:
    return name.lower().replace(" ", "") + ".io"


# ── Build customer records ───────────────────────────────────────────────────

customers = []
idx = 0
for mi, month in enumerate(MONTHS):
    for _ in range(NEW_PER_MONTH[mi]):
        mrr = random.choices(MRR_POOL, weights=MRR_WEIGHTS)[0]
        customers.append({
            "name":        names[idx],
            "domain":      to_domain(names[idx]),
            "start_month": mi,
            "mrr":         mrr,
            "industry":    random.choice(INDUSTRIES),
            "country":     random.choice(COUNTRIES),
            "channel":     random.choices(["inbound", "outbound"], weights=[60, 40])[0],
            "churn_month": None,
            "expansion":   None,
        })
        idx += 1

# Churn: each customer has a 5% chance of churning each month after their first
for c in customers:
    for m in range(c["start_month"] + 1, len(MONTHS)):
        if random.random() < 0.05:
            c["churn_month"] = m
            break

# Expansion: ~12% of customers upgrade once, 2–6 months after joining
for c in customers:
    if random.random() < 0.12:
        max_offset = len(MONTHS) - 1 - c["start_month"]
        if max_offset < 2:
            continue
        offset = random.randint(2, min(6, max_offset))
        upgrade_month = c["start_month"] + offset
        if c["churn_month"] is None or upgrade_month < c["churn_month"]:
            new_mrr = round(c["mrr"] * random.uniform(1.25, 1.65) / 100) * 100
            c["expansion"] = (upgrade_month, new_mrr)

# ── Write transactions ───────────────────────────────────────────────────────

rows = []
for c in customers:
    end_month = c["churn_month"] if c["churn_month"] is not None else len(MONTHS)
    for m in range(c["start_month"], end_month):
        amount = c["mrr"]
        if c["expansion"] and m >= c["expansion"][0]:
            amount = c["expansion"][1]
        month_str = MONTHS[m]
        day = random.randint(1, 28)
        rows.append({
            "transaction_date": f"{month_str}-{day:02d}",
            "customer_name":    c["name"],
            "customer_domain":  c["domain"],
            "amount_usd":       amount,
            "acquisition_channel": c["channel"],
            "country":          c["country"],
            "industry":         c["industry"],
        })

rows.sort(key=lambda r: (r["transaction_date"], r["customer_name"]))

out_path = os.path.join(os.path.dirname(__file__), "demo_transactions.csv")
fieldnames = [
    "transaction_date", "customer_name", "customer_domain",
    "amount_usd", "acquisition_channel", "country", "industry",
]
with open(out_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

total_customers = len(customers)
active_final = sum(
    1 for c in customers
    if c["churn_month"] is None or c["churn_month"] >= len(MONTHS)
)
churned = sum(1 for c in customers if c["churn_month"] is not None)
expanded = sum(1 for c in customers if c["expansion"] is not None)

print(f"Generated {len(rows):,} transaction rows")
print(f"  {total_customers} customers total")
print(f"  {active_final} active at end of period")
print(f"  {churned} churned at some point")
print(f"  {expanded} expanded at some point")
print(f"  Saved to {out_path}")
