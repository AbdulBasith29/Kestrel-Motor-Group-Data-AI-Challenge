"""Silver: standardise bronze rows and apply the data quality rules.

Reads  bronze.raw_responses, config/sources.yml, reference/dealerships.csv
Writes silver.feedback  one row per customer response: dealer, date, department, raw + 1-5 rating,
                        comment, lineage, quality flags, in_analysis, negative
       ops.dq_results   each rule, rows failing, action taken (also saved to outputs/dq_results.csv)

Rows are flagged with a reason, never silently dropped, so every number reconciles back to bronze.
Privacy: Silver carries the masked Bronze comments. Unrecognised identifiers can remain;
keep tables restricted pending local-model audit and human review.
"""
import argparse
import hashlib
import math
import re

import pandas as pd

from common import ROOT, by_prefix, connect, load_config


def parse_date(raw, filename, cfg):
    if raw is None or str(raw).strip() == "":
        return pd.NaT
    raw = str(raw).strip()
    if any(filename.startswith(p) for p in cfg["excel_serial_dates"]) and raw.isdigit():
        try:
            return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(raw))
        except (ValueError, OverflowError):
            return pd.NaT
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} 00:00:00", raw):  # a real Excel date cell
        return pd.Timestamp(raw)
    fmt = by_prefix(cfg["date_formats"], filename) or cfg["default_date_format"]
    return pd.to_datetime(raw, format=fmt, errors="coerce")


def normalise_rating(row, cfg):
    """Return (score on 1-5 where 5 is best, scale label)."""
    raw = row.rating_raw
    if raw == "":
        return None, None
    if "★" in raw:
        count = float(raw.count("★"))
        if not (1 <= count <= 5):
            return None, "invalid (out of range stars)"
        return count, "stars"
    if raw.lower() in cfg["text_ratings"]:
        return float(cfg["text_ratings"][raw.lower()]), "text"
    try:
        value = float(raw)
    except ValueError:
        return None, "invalid (unreadable)"
    if not math.isfinite(value):
        return None, "invalid (non-finite)"
    if value != int(value):
        return None, "invalid (non-integer)"
    if row.rating_header == cfg["ten_point_header"]:
        if not (1 <= value <= 10):
            return None, "invalid (out of range 1-10)"
        return round(1 + (value - 1) * 4 / 9, 2), "1-10 rescaled"
    if any(row.source_file.startswith(r["file"]) and row.source_sheet == r["sheet"] for r in cfg["reversed_scale"]):
        if not (1 <= value <= 5):
            return None, "invalid (out of range 1-5)"
        return 6 - value, "1-5 reversed"
    if not (1 <= value <= 5):
        return None, "invalid (out of range 1-5)"
    return value, "1-5"


def standardise(raw, cfg):
    dept_lookup = {alias: dept for dept, aliases in cfg["departments"].items() for alias in aliases}
    df = raw.copy()
    df["date"] = [parse_date(d, f, cfg) for d, f in zip(df.date_raw, df.source_file)]
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    scores = [normalise_rating(r, cfg) for r in df.itertuples()]
    df["rating_1to5"] = [s for s, _ in scores]
    df["rating_scale"] = [k for _, k in scores]
    df["department"] = df.department_raw.str.lower().map(dept_lookup)
    df["dealer_code"] = [
        cfg["site_column_dealers"].get(site.lower()) if site and not site.upper().startswith(("HUNTER", "KMG"))
        else by_prefix(cfg["dealers"], f)
        for site, f in zip(df.site_raw, df.source_file)]
    return df


def transform(raw, dealers, cfg):
    """Return feedback, rule counts and one decision per Bronze row, without writing."""
    df = standardise(raw, cfg)
    df["flags"], df["in_analysis"], report = "", True, []

    def rule(name, mask, action, exclude):
        mask = mask.fillna(False).astype(bool)
        df.loc[mask, "flags"] += name + ";"
        if exclude:
            df.loc[mask, "in_analysis"] = False
        report.append({"rule": name, "rows_failing": int(mask.sum()), "excluded": exclude, "action": action})

    # 1. Not a customer response at all: notes, template banners, monthly total rows
    note_row = (df.date_raw.str.lower().str.startswith("total") | df.date_raw.eq("[SOURCE NOTE]")
                | (df.date.isna() & df.rating_1to5.isna() & df.comment.eq("")))
    rule("not_a_response", note_row, "excluded: notes, template banners and monthly total rows", True)

    # 2. Staff testing the form ("test drive" / vehicle feedback comments are real customers)
    test_comment = df.comment.str.lower().str.match(
        r"^(?!test\s*(?:drive|drove|run|ride|car|vehicle|trip|track)\b)(?:test\b|testing\b|asdf)"
    )
    junk = test_comment | df.date_raw.str.lower().isin(["test", "asdf"]) | (df.date < "2000-01-01")
    rule("test_or_junk_row", junk & ~note_row, "excluded: staff testing the form", True)

    # 3. Year typo: Shepparton rows dated Oct-Dec 2026 sit in date order between 2025 rows
    start, end = (pd.Timestamp(cfg["reporting_window"][k]) for k in ("start", "end"))
    fixable = pd.Series(False, index=df.index)
    for correction in cfg.get("date_corrections", []):
        fixable |= (df.source_file.eq(correction["file"]) & df.source_sheet.eq(correction["sheet"])
                    & df.source_row.isin(correction["rows"]) & df.date.between("2026-10-01", "2026-12-31"))
    df.loc[fixable, "date"] = df.loc[fixable, "date"] - pd.DateOffset(years=1)
    rule("year_typo_corrected", fixable, "kept: year moved back by one (reviewed Shepparton sequence)", False)

    # Quarantine other unverified future dates
    unverified_future = (df.date > end) & ~fixable
    rule("quarantined_future_date", unverified_future, "excluded: unverified future date quarantined", True)

    live = df.in_analysis
    rule("date_outside_reporting_year", live & df.date.notna() & ~df.date.between(start, end), "excluded", True)
    closed = df.dealer_code.map(dealers.set_index("dealer_code").closed_date)
    rule("dated_after_site_closure", live & closed.notna() & (df.date > closed), "excluded", True)
    rule("unknown_dealer", live & df.dealer_code.isna(), "excluded: cannot attribute", True)
    rule("unknown_department", live & df.department.isna(), "kept; shown as Unknown department", False)
    rule("date_missing_or_vague", live & df.date.isna(), "kept; left out of monthly trends", False)

    invalid_rating = df.in_analysis & (df.rating_raw != "") & df.rating_scale.str.startswith("invalid")
    rule("invalid_source_rating", invalid_rating, "kept in analysis for comments; rating set to null (source score out of range)", False)
    rule("rating_missing", live & df.rating_1to5.isna() & ~invalid_rating, "kept; left out of rating KPIs (no imputing from comments)", False)
    rule("comment_blank", live & df.comment.eq(""), "kept for rating KPIs; nothing to theme", False)

    dupes = pd.Series(False, index=df.index)
    eligible = df.loc[df.in_analysis]
    dupes.loc[eligible.index] = eligible.duplicated(["dealer_code", "date", "department", "rating_raw", "comment_identity"]) & (eligible.comment_original_length > 20)
    rule("exact_duplicate", dupes, "excluded: same dealer, date, department, rating and comment as an earlier row", True)
    ref_dupes = pd.Series(False, index=df.index)
    eligible = df.loc[df.in_analysis & df.source_ref.ne("")]
    ref_dupes.loc[eligible.index] = eligible.duplicated(["dealer_code", "source_ref"])
    rule("duplicate_reference_id", ref_dupes, "excluded: response ID already seen", True)

    df["negative"] = (df.rating_1to5 <= cfg["negative_max_score"]).astype("boolean").mask(df.rating_1to5.isna())
    df["sales_subtype"] = df.department_raw.str.lower().map({"new cars":"New", "sales - new":"New", "used cars":"Used", "sales - used":"Used"})
    df.insert(0, "response_id", ["R" + hashlib.sha256(f"{f}\0{s}\0{r}".encode()).hexdigest()[:24]
                                for f, s, r in zip(df.source_file, df.source_sheet, df.source_row)])
    feedback = df[~note_row][["response_id", "dealer_code", "date", "date_raw", "department", "department_raw", "sales_subtype", "rating_raw",
                              "rating_scale", "rating_1to5", "negative", "comment", "source_ref", "flags",
                              "in_analysis", "source_file", "source_sheet", "source_row", "comment_identity",
                              "masking_version", "has_unmasked_name", "name_audit_status",
                              "had_staff_name_mention", "had_customer_name_mention"]]
    dq = pd.DataFrame(report)
    dq.loc[len(dq)] = {"rule": "TOTAL in analysis", "rows_failing": int(df.in_analysis.sum()), "excluded": False,
                       "action": f"of {len(df)} bronze rows"}
    decisions = df[["response_id", "source_file", "source_sheet", "source_row", "flags", "in_analysis"]].copy()
    decisions["record_type"] = note_row.map({True:"non_response", False:"feedback"})
    if len(decisions) != len(raw) or decisions.response_id.duplicated().any():
        raise ValueError("Silver row reconciliation or response-key uniqueness failed")
    if not feedback.rating_1to5.dropna().between(1, 5).all():
        raise ValueError("Silver contains invalid normalised scores")
    return feedback, dq, decisions


def main(database=None):
    cfg = load_config()
    con = connect(database)
    try:
        raw = con.execute("SELECT * FROM bronze.raw_responses ORDER BY source_file, source_sheet, source_row").df()
        dealers = pd.read_csv(ROOT / "reference" / "dealerships.csv", parse_dates=["closed_date"])
        feedback, dq, decisions = transform(raw, dealers, cfg)
        con.execute("BEGIN TRANSACTION")
        con.execute("CREATE OR REPLACE TABLE silver.feedback AS SELECT * FROM feedback")
        con.execute("CREATE OR REPLACE TABLE silver.row_decisions AS SELECT * FROM decisions")
        con.execute("CREATE OR REPLACE TABLE ops.dq_results AS SELECT * FROM dq")
        con.execute("COMMIT")
    finally:
        con.close()
    (ROOT / "outputs").mkdir(exist_ok=True)
    dq.to_csv(ROOT / "outputs" / "dq_results.csv", index=False)
    print(dq.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Bronze into canonical Silver feedback")
    parser.add_argument("--database", help="DuckDB path; defaults to kestrel.duckdb")
    main(parser.parse_args().database)
