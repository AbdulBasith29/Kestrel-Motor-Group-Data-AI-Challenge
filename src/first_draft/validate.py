"""Step 2: decide what we can trust. Apply data quality rules, flag or exclude, and report.

Run from the assignment folder:  python src/first_draft/validate.py   (after consolidate.py)
Reads   data/feedback_clean.csv, reference/dealerships.csv
Writes  data/feedback_validated.csv   every response with its flags and an in_analysis column
        outputs/validation_report.csv rule, rows failing, what we did (safe to commit)
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WINDOW = (pd.Timestamp("2025-10-01"), pd.Timestamp("2026-09-30"))


def main():
    df = pd.read_csv(ROOT / "data" / "feedback_clean.csv", parse_dates=["date"], keep_default_na=False,
                     na_values={"date": [""], "rating_1to5": [""]})
    dealers = pd.read_csv(ROOT / "reference" / "dealerships.csv", parse_dates=["closed_date"])
    closed = dealers.set_index("dealer_code")["closed_date"].dropna()
    report = []

    def rule(name, mask, action, excluded):
        df.loc[mask, "flags"] += name + ";"
        if excluded:
            df.loc[mask, "in_analysis"] = False
        report.append({"rule": name, "rows_failing": int(mask.sum()), "action": action})

    df["flags"] = ""
    df["in_analysis"] = True
    # Only rows that ARE tests: "test drive" / "battery test" comments are real customers
    test_comment = df["comment"].str.strip().str.lower().str.match(
        r"^(?!test\s*(?:drive|drove|run|ride|car|vehicle|trip|track)\b)(?:test\b|testing\b|asdf)"
    )
    junk = (test_comment
            | df["raw_date"].str.strip().str.lower().isin({"test", "asdf"}) | (df["date"] < "2000-01-01"))
    rule("test_or_junk_row", junk,
         "excluded: staff testing the form, not customers", True)

    # Shepparton: rows sit in date order between 2025 rows but say Oct-Dec 2026 -> year typo
    is_shepparton = df["dealer_code"].eq("VIC09") | df["source_file"].str.startswith("Shepparton")
    future = df["date"] > WINDOW[1]
    fixable = is_shepparton & future & (df["date"] - pd.DateOffset(years=1)).between(*WINDOW)
    df.loc[fixable, "date"] = df.loc[fixable, "date"] - pd.DateOffset(years=1)
    rule("year_typo_corrected", fixable, "kept: year moved back by one (reviewed Shepparton sequence)", False)

    unverified_future = future & ~fixable
    rule("quarantined_future_date", unverified_future, "excluded: unverified future date quarantined", True)

    outside = df["date"].notna() & ~df["date"].between(*WINDOW) & ~df["flags"].str.contains("test") & ~unverified_future
    rule("date_outside_reporting_year", outside, "excluded", True)

    after_close = df["dealer_code"].map(closed).notna() & (df["date"] > df["dealer_code"].map(closed))
    rule("dated_after_site_closure", after_close, "excluded", True)

    rule("date_missing_or_vague", df["date"].isna() & df["in_analysis"],
         "kept for themes and totals; left out of monthly trends", False)

    invalid_rating = df["rating_scale"].str.startswith("invalid")
    rule("invalid_source_rating", invalid_rating,
         "kept for comments; invalid rating set to null and excluded from rating KPIs", False)

    rule("rating_missing", df["rating_1to5"].isna() & ~invalid_rating,
         "kept; left out of rating KPIs (no imputing scores from comments)", False)

    rule("comment_blank", df["comment"].str.strip() == "",
         "kept for rating KPIs; nothing to theme", False)

    dup_cols = ["dealer_code", "date", "department", "rating_raw", "comment"]
    dupes = df.duplicated(dup_cols, keep="first") & (df["comment"].str.len() > 20)
    rule("exact_duplicate", dupes, "excluded: same dealer, date, department, rating and comment as an earlier row", True)

    ref_dupes = (df["source_ref"] != "") & df.duplicated(["dealer_code", "source_ref"], keep="first")
    rule("duplicate_reference_id", ref_dupes & ~dupes, "excluded: same response ID seen in another file", True)

    # agreed definition: 1-2 on the 1-5 scale; unknown when there is no rating
    df["negative"] = (df["rating_1to5"] <= 2).astype("boolean").mask(df["rating_1to5"].isna())

    df.to_csv(ROOT / "data" / "feedback_validated.csv", index=False, date_format="%Y-%m-%d")
    out = pd.DataFrame(report)
    out.loc[len(out)] = {"rule": "TOTAL in analysis", "rows_failing": int(df["in_analysis"].sum()),
                         "action": f"of {len(df)} responses consolidated"}
    out.to_csv(ROOT / "outputs" / "validation_report.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
