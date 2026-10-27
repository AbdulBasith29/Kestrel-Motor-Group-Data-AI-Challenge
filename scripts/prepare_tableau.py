"""Shape the Gold reporting exports into small Tableau-ready CSVs (aggregates only, no names or comments).

Usage (from the project root, after `python src/gold.py`):  python scripts/prepare_tableau.py
Reads data/reporting_exports/, writes tableau/extracts/. Every file keeps counts, not rates,
so Tableau computes shares as SUM(negative) / SUM(rated) at any level of detail.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "reporting_exports"
OUT = ROOT / "tableau" / "extracts"
OUT.mkdir(parents=True, exist_ok=True)
WORSENING = {"NSW01", "VIC01", "VIC08", "NSW04"}  # Parramatta, Bendigo, Dandenong, Liverpool


def site_group(codes):
    return codes.map(lambda c: "Worsening four" if c in WORSENING else "Other 20 dealerships")


# 1. Monthly counts by dealer x department (CX overview + dealer investigation)
m = pd.read_csv(SRC / "mart_dealer_dept_month.csv")
m["site_group"] = site_group(m["dealer_code"])
m["month_start"] = pd.to_datetime(m["month"] + "-01")
cols = ["dealer_code", "dealership_name", "state", "region", "department", "month_start", "half_year",
        "site_group", "responses", "rated_responses", "negative_responses", "commented_responses",
        "enriched_responses", "assumed_dealer_responses", "volume", "revenue_aud"]
m[cols].to_csv(OUT / "feedback_monthly.csv", index=False)

# 2. Theme drivers: full dealer x department x half x theme grid (zeros included), each row carrying
#    its own denominator, so SUM(mentions) / SUM(negatives_with_ai) is correct at any level in Tableau
t = pd.read_csv(SRC / "mart_theme_drivers.csv")
half = m[["month", "half_year"]].drop_duplicates()
t = t.merge(half, on="month", how="left")
den = (t.groupby(["dealer_code", "department", "month", "half_year"], as_index=False)["negative_rated_with_ai"].max()
         .groupby(["dealer_code", "department", "half_year"], as_index=False)["negative_rated_with_ai"].sum())
num = t.groupby(["dealer_code", "department", "half_year", "theme_id"], as_index=False)[
    "strictly_negative_rated_driver_mentions"].sum()
themes = pd.read_csv(SRC / "dim_theme.csv")
grid = den.merge(themes, how="cross").merge(num, on=["dealer_code", "department", "half_year", "theme_id"], how="left")
grid["strictly_negative_rated_driver_mentions"] = grid["strictly_negative_rated_driver_mentions"].fillna(0).astype(int)
names = m[["dealer_code", "dealership_name"]].drop_duplicates()
grid = grid.merge(names, on="dealer_code")
grid["site_group"] = site_group(grid["dealer_code"])
grid.rename(columns={"strictly_negative_rated_driver_mentions": "negative_theme_mentions",
                     "negative_rated_with_ai": "negative_responses_with_ai"}).to_csv(OUT / "theme_drivers.csv", index=False)

# 3. Data quality by dealer x department
q = pd.read_csv(SRC / "mart_feedback_quality.csv")
q = q.merge(pd.read_csv(SRC / "dim_dealer.csv")[["dealer_code", "dealership_name", "status"]], on="dealer_code")
s = pd.read_csv(SRC / "mart_dealer_dept_summary.csv")[["dealer_code", "department", "commented_responses",
                                                        "enriched_responses", "assumed_dealer_responses"]]
q.merge(s, on=["dealer_code", "department"], how="left").to_csv(OUT / "data_quality.csv", index=False)

# 4. Value scenarios (already aggregate; labelled as assumptions in the dashboard)
v = ROOT / "outputs" / "business_answers" / "q3_value_at_risk.csv"
if v.exists():
    pd.read_csv(v).to_csv(OUT / "value_scenarios.csv", index=False)

# Reconciliation: monthly files hold dated responses only, so they sit 10 undated rows below Gold totals
assert m["responses"].sum() + q["accepted_undated_responses"].sum() == q["accepted_responses"].sum()
print("rated", m["rated_responses"].sum(), "negative", m["negative_responses"].sum(),
      "accepted", q["accepted_responses"].sum())
# Every site is "Kestrel <town>", so drop the prefix to keep dashboard labels readable
for f in OUT.glob("*.csv"):
    d = pd.read_csv(f)
    if "dealership_name" in d:
        d["dealership_name"] = d["dealership_name"].str.removeprefix("Kestrel ")
        d.to_csv(f, index=False)
short = {"Waiting time and scheduling": "Waiting/booking", "Communication and follow-up": "Communication",
         "Workmanship and repair quality": "Repair quality", "Pricing and value": "Price/value",
         "Vehicle or product": "Vehicle/product"}
t = pd.read_csv(OUT / "theme_drivers.csv")
t["theme_name"] = t["theme_name"].replace(short)
t.to_csv(OUT / "theme_drivers.csv", index=False)
print("written to", OUT)
