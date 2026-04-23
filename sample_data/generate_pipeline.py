"""
Generate a demo sales pipeline CSV.
Mix of new prospects and expansion deals on existing customers.
"""
import csv
import random
from datetime import date, timedelta

random.seed(7)

EXISTING_CUSTOMERS = [
    "Hull Flow", "Bolt Ops", "Shade Solutions", "Zone Analytics",
    "Tide Systems", "Hull Logic", "Crest ML", "Shore Security",
    "Dune Intelligence", "Lens Pro", "Peak Logic", "Spring Hub",
    "Pixel Logic", "Prism Tech", "Atlas Dynamics", "Clay Labs",
]

NEW_PROSPECTS = [
    "Vertex Labs", "Nimbus Data", "Orbit Systems", "Quartz Analytics",
    "Rivet Cloud", "Summit AI", "Tidal Works", "Umbra Security",
    "Vector Health", "Willow Software", "Xenon Platform", "Yield Tech",
    "Zephyr IO", "Anchor Insights", "Beacon Metrics", "Cobalt Networks",
    "Delta Forge", "Ember Robotics", "Forge Pay", "Granite Ledger",
]

STAGES = [
    ("Discovery",         10, (600, 2500)),
    ("Demo",               9, (800, 3500)),
    ("Proposal",           7, (1000, 5000)),
    ("Negotiation",        5, (1500, 6500)),
    ("Verbal Agreement",   4, (2000, 8000)),
]

START = date(2025, 5, 1)

rows = []
opp_counter = 1
for stage, count, (lo, hi) in STAGES:
    for _ in range(count):
        is_expansion = random.random() < 0.35
        if is_expansion and EXISTING_CUSTOMERS:
            company = random.choice(EXISTING_CUSTOMERS)
            opp_name = f"{company} - Expansion #{opp_counter}"
        else:
            company = random.choice(NEW_PROSPECTS)
            opp_name = f"{company} - New Logo #{opp_counter}"
        mrr = random.randint(lo // 100, hi // 100) * 100
        # Close date: earlier stages further out
        stage_idx = [s[0] for s in STAGES].index(stage)
        days_out = random.randint(60 - stage_idx * 12, 120 - stage_idx * 15)
        close_date = START + timedelta(days=max(7, days_out))
        rows.append({
            "opportunity_name":    opp_name,
            "company_name":        company,
            "stage":               stage,
            "amount_usd":          mrr,
            "expected_close_date": close_date.isoformat(),
        })
        opp_counter += 1

random.shuffle(rows)

out = "sample_data/demo_pipeline.csv"
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"Wrote {len(rows)} opportunities to {out}")
