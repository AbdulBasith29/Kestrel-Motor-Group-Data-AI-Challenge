"""Step 1: bring every feedback file into one table, one row per customer response.

Run from the assignment folder:  python src/first_draft/consolidate.py
Reads   feedback/*.xlsx|csv and reference/dealerships.csv (kept local, never committed)
Writes  data/feedback_clean.csv     one row per response, identifier columns dropped (local only; free-text comments contain PII and remain restricted)
        outputs/source_log.csv      rows read / kept / skipped per file and sheet (safe to commit)

Each source keeps its raw rating next to the normalised 1-5 score, plus file/sheet/row lineage,
so any number in the report can be traced back to a cell.
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from investigation_support import load_feedback_csv  # reuse the CSV loader from the investigation

# --- Which dealership each file belongs to -------------------------------------------------
# Hunter Motors -> Newcastle is an assumption (agreed 27 Oct): Newcastle is the only
# dealership with no other file and Hunter is the Newcastle region.
FILE_TO_DEALER = {
    "Ballarat": "VIC07", "bendigo": "VIC08", "boxhill": "VIC05", "chatswood": "NSW03",
    "Chermside": "QLD01", "Dandenong": "VIC01", "ESSENDON": "VIC03", "Frankston": "VIC04",
    "Geelong": "VIC06", "Hunter Motors": "NSW05", "IPS": "QLD03", "liverpool": "NSW04",
    "Noosa": "QLD05", "Parramatta": "NSW01", "Penrith": "NSW02", "Ringwood": "VIC02",
    "Shepparton": "VIC09", "Southport": "QLD04", "Springwood": "QLD02", "Tamworth": "NSW07",
    "Toowoomba": "QLD06", "Wollongong": "NSW06",
}
# North QLD workbook holds two sites in a "Site" column
SITE_TO_DEALER = {"rok": "QLD07", "rocky": "QLD07", "rockhampton": "QLD07",
                  "tsv": "QLD08", "townsville": "QLD08"}

# --- Sources we read but deliberately leave out of the response table (agreed 27 Oct) -----
SKIP_SOURCES = {
    ("Chermside Q1 2026 FINAL.xlsx", "Feedback"): "superseded by FINAL v2 (v2 contains all 112 rows + 6 new)",
    ("Penrith Feedback.xlsx", "Jun 26"): "copy of the Jul 26 tab (same rows, July dates); Penrith June is missing",
    ("Toowoomba Q4 2025 summary.xlsx", "Summary"): "aggregate counts only, no individual responses or comments",
    ("Southport Feedback Tracker.xlsx", "Google reviews (copied)"): "copied public reviews with relative dates only",
}

# --- Column header aliases -> standard column ------------------------------------------------
COLUMNS = {
    "date": {"date", "date received", "submitted_at"},
    "department": {"dept", "department", "area"},
    "rating": {"rating", "rating (1-5)", "score", "score (1-5)", "score (out of 10)", "csat",
               "stars", "how satisfied?", "how was it"},
    "comment": {"comments", "comment", "feedback", "verbatim", "what did they say?",
                "customer comments", "customer feedback", "customer said", "notes"},
    "site": {"site", "dealer"},
    "source_ref": {"ref", "response_id"},
}
# Structured identifier columns (customer, name, phone, mobile, email, rego, customer numbers, staff names,
# booking ref, vehicle, action taken) are dropped here, but note that free-text comments still contain
# personal information (58 emails, 156 mobile numbers). Keep clean tables restricted/local only.

DEPARTMENTS = {  # reviewed aliases (A001, agreed 27 Oct); anything else is flagged
    "service": "Service", "service dept": "Service", "svc": "Service", "workshop": "Service", "sv": "Service",
    "sales": "Sales", "new cars": "Sales", "used cars": "Sales", "sales - new": "Sales",
    "sales - used": "Sales", "s": "Sales",
    "parts": "Parts", "parts counter": "Parts", "p&a": "Parts", "parts & accessories": "Parts", "p": "Parts",
}
TEXT_SCALES = {  # text and star ratings -> 1-5
    "very dissatisfied": 1, "dissatisfied": 2, "neutral": 3, "satisfied": 4, "very satisfied": 5,
    "bad": 1, "ok": 3, "good": 5,  # Tamworth's three-point scale
}

# Date formats that differ by source; everything else is a real Excel date or day-first text
DATE_FORMATS = {
    "Wollongong": "%d-%b-%y", "bendigo": "%d %b %y", "Geelong": "%d/%m/%y",
    "liverpool_q3_2026": "%m/%d/%Y",  # this one export switched to US month-first
    "boxhill": "%Y-%m-%d %H:%M:%S",
}


def lookup(table, filename):
    return next((v for k, v in table.items() if filename.startswith(k)), None)


def parse_date(value, filename):
    if value is None or str(value).strip() == "":
        return pd.NaT
    if hasattr(value, "year"):
        return pd.Timestamp(value)
    if isinstance(value, (int, float)):  # Excel serial number (North QLD)
        return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(value))
    fmt = lookup(DATE_FORMATS, filename) or "%d/%m/%Y"
    return pd.to_datetime(str(value).strip(), format=fmt, errors="coerce")


def normalise_rating(raw, filename, sheet, header):
    """Return (score on 1-5 where 5 is best, scale label). None if not a usable rating."""
    text = str(raw).strip()
    if text == "":
        return None, None
    if "★" in text:
        count = text.count("★")
        return (float(count), "stars 1-5") if 1 <= count <= 5 else (None, "invalid stars 1-5")
    if text.lower() in TEXT_SCALES:
        return float(TEXT_SCALES[text.lower()]), "text"
    try:
        value = float(text)
    except ValueError:
        return None, "invalid numeric rating"
    if not pd.notna(value) or value in (float("inf"), float("-inf")):
        return None, "invalid numeric rating"
    if value != int(value):
        return None, "invalid non-integer rating"
    if "out of 10" in header:
        if not 1 <= value <= 10:
            return None, "invalid 1-10"
        return round(1 + (value - 1) * 4 / 9, 2), "1-10"  # linear rescale (agreed 27 Oct)
    if not 1 <= value <= 5:
        return None, "invalid 1-5"
    if filename.startswith("Geelong") and sheet == "2025":
        return 6 - value, "1-5 reversed (1 = Excellent)"  # sheet note says 1 = Excellent
    return value, "1-5"


def header_rows(grid):
    """Row positions that look like a header (a date label and a rating label in the same row)."""
    hits = []
    for i in range(len(grid)):
        labels = {str(v).strip().lower() for v in grid.iloc[i]}
        if labels & COLUMNS["date"] and labels & COLUMNS["rating"]:
            hits.append(i)
    return hits


def read_sources():
    for path in sorted((ROOT / "feedback").iterdir()):
        if path.suffix.lower() == ".csv":
            yield path.name, "csv", load_feedback_csv(path)[0]
        elif path.suffix.lower() == ".xlsx" and not path.name.startswith("~$"):
            for sheet, grid in pd.read_excel(path, sheet_name=None, header=None, dtype=object).items():
                yield path.name, sheet, grid.fillna("")


def extract(filename, sheet, grid):
    """Turn one sheet into standard rows. A sheet can hold several header segments (Ringwood, Frankston)."""
    rows, skipped = [], 0
    starts = header_rows(grid)
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(grid)
        header = [str(v).strip().lower() for v in grid.iloc[start]]
        col = {std: header.index(h) for std, aliases in COLUMNS.items() for h in header if h in aliases}
        for i in range(start + 1, end):
            cells = grid.iloc[i]
            get = lambda k: cells.iloc[col[k]] if k in col else ""
            raw_date, raw_rating, comment = get("date"), get("rating"), str(get("comment")).strip()
            date = parse_date(raw_date, filename)
            score, scale = normalise_rating(raw_rating, filename, sheet, header[col["rating"]])
            # Blank rows, notes ("*** NEW TEMPLATE ***", "Site closed ...") and monthly total rows
            is_total = str(raw_date).strip().lower().startswith("total")
            if is_total or (pd.isna(date) and score is None and (comment == "" or str(raw_date).strip() != "")):
                if any(str(v).strip() for v in cells):
                    skipped += 1
                continue
            dept_raw = str(get("department")).strip() or (sheet if filename.startswith("ESSENDON") else "")
            site_raw = str(get("site")).strip()
            dealer = SITE_TO_DEALER.get(site_raw.lower()) if filename.startswith("North QLD") else lookup(FILE_TO_DEALER, filename)
            rows.append({
                "dealer_code": dealer, "date": date, "raw_date": str(raw_date).strip(),
                "department": DEPARTMENTS.get(dept_raw.lower()), "department_raw": dept_raw,
                "rating_raw": str(raw_rating).strip(), "rating_scale": scale, "rating_1to5": score,
                "comment": comment, "source_ref": str(get("source_ref")).strip(),
                "source_file": filename, "source_sheet": sheet, "source_row": i + 1,
            })
    return rows, skipped, len(starts)


def main():
    dealers = pd.read_csv(ROOT / "reference" / "dealerships.csv")
    all_rows, log = [], []
    for filename, sheet, grid in read_sources():
        entry = {"source_file": filename, "source_sheet": sheet, "physical_rows": len(grid)}
        if (filename, sheet) in SKIP_SOURCES:
            log.append({**entry, "responses": 0, "non_response_rows": 0, "note": "excluded: " + SKIP_SOURCES[(filename, sheet)]})
            continue
        if grid.empty:
            log.append({**entry, "responses": 0, "non_response_rows": 0, "note": "empty sheet"})
            continue
        rows, skipped, segments = extract(filename, sheet, grid)
        note = f"{segments} header segments" if segments > 1 else ("no header found" if segments == 0 else "")
        log.append({**entry, "responses": len(rows), "non_response_rows": skipped, "note": note})
        all_rows += rows

    df = pd.DataFrame(all_rows)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()  # keep the day, drop survey timestamps
    df = df.merge(dealers[["dealer_code", "dealership_name", "state", "region"]], on="dealer_code", how="left")
    df.insert(0, "response_id", [f"R{i:05d}" for i in range(1, len(df) + 1)])

    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "outputs").mkdir(exist_ok=True)
    df.to_csv(ROOT / "data" / "feedback_clean.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame(log).to_csv(ROOT / "outputs" / "source_log.csv", index=False)

    print(f"Read {len(log)} file/sheet sources -> {len(df)} responses from {df.dealer_code.nunique()} dealerships")
    print(f"Unmapped departments: {df.department.isna().sum()}, unusable ratings: {df.rating_1to5.isna().sum()}, "
          f"undated: {df.date.isna().sum()}, unknown dealer: {df.dealer_code.isna().sum()}")
    print(df.groupby("dealership_name").size().sort_values().to_string())


if __name__ == "__main__":
    main()
