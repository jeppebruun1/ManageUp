import csv
import random
from datetime import date, timedelta

random.seed(42)

COMPANY_PREFIXES = [
    "Acme", "Apex", "Bright", "Cedar", "Cloud", "Core", "Crest", "Delta",
    "Edge", "Ember", "Flux", "Forge", "Frost", "Global", "Grant", "Grid",
    "Harbor", "Helix", "Horizon", "Inova", "Iris", "Kite", "Lark", "Leap",
    "Lens", "Lumen", "Maven", "Merit", "Mint", "Mosaic", "Nexus", "Nova",
    "Onyx", "Orbit", "Peak", "Pillar", "Pivot", "Prism", "Pulse", "Quest",
    "Ramp", "Relay", "Ridge", "Sage", "Scout", "Seraph", "Signal", "Slate",
    "Spark", "Sphere", "Sprint", "Stack", "Stratum", "Summit", "Swift",
    "Synth", "Titan", "Token", "Torque", "Trek", "Truss", "Vault", "Veil",
    "Velo", "Vertex", "Vibe", "Vista", "Volt", "Wave", "Waypoint", "Willow",
    "Xeno", "Yield", "Zenith", "Zephyr",
]
COMPANY_SUFFIXES = [
    "AI", "Analytics", "Cloud", "Data", "HQ", "IO", "Labs", "Link",
    "Logic", "Networks", "One", "Ops", "Platforms", "Pro", "Solutions",
    "Systems", "Tech", "Works",
]

CHANNELS = ["inbound", "outbound"]
COUNTRIES = [
    "United States", "United States", "United States",  # weighted heavier
    "United Kingdom", "United Kingdom",
    "Germany",
    "Canada",
    "Australia",
    "France",
]
INDUSTRIES = [
    "Fintech", "Fintech",
    "Healthcare",
    "E-commerce",
    "SaaS",
    "Logistics",
]

START_OF_WINDOW = date(2024, 1, 1)
END_OF_WINDOW   = date(2024, 12, 31)
REPORT_DATE     = date(2025, 1, 1)


def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def make_domain(name: str) -> str:
    slug = name.lower().replace(" ", "")
    tlds = [".com", ".io", ".ai", ".co"]
    return slug + random.choice(tlds)


def generate_rows(n: int = 150) -> list[dict]:
    used_names: set[str] = set()
    rows = []

    for _ in range(n):
        # unique company name
        for _ in range(100):
            prefix = random.choice(COMPANY_PREFIXES)
            suffix = random.choice(COMPANY_SUFFIXES)
            name = f"{prefix} {suffix}"
            if name not in used_names:
                used_names.add(name)
                break

        domain = make_domain(name)
        mrr = round(random.choice([
            random.randint(500, 999),
            random.randint(1000, 1999),
            random.randint(2000, 3499),
            random.randint(3500, 5000),
        ]) / 50) * 50  # round to nearest $50

        signup = random_date(START_OF_WINDOW, END_OF_WINDOW)
        channel = random.choice(CHANNELS)
        country = random.choice(COUNTRIES)
        industry = random.choice(INDUSTRIES)

        # ~22 % churn: end_date is between signup+60 days and report date
        churned = random.random() < 0.22
        if churned:
            earliest_end = signup + timedelta(days=60)
            if earliest_end < REPORT_DATE:
                end = random_date(earliest_end, REPORT_DATE - timedelta(days=1))
            else:
                end = ""
                churned = False
        else:
            end = ""

        rows.append({
            "customer_name": name,
            "customer_domain": domain,
            "mrr_usd": mrr,
            "signup_date": signup.isoformat(),
            "end_date": end.isoformat() if churned and end else "",
            "acquisition_channel": channel,
            "country": country,
            "industry": industry,
        })

    return rows


def main():
    rows = generate_rows(150)
    fieldnames = [
        "customer_name", "customer_domain", "mrr_usd",
        "signup_date", "end_date", "acquisition_channel",
        "country", "industry",
    ]
    out_path = "sample_data/demo.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
