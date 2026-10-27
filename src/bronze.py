"""Bronze: land every source row as text, with complete row-level lineage and reconciliation.

Reads feedback/*.xlsx|csv using config/sources.yml to identify header rows and required columns.
Writes bronze.raw_responses (one row per data row, all values as text)
       ops.file_registry     (file hash, sheet, physical rows, landed, headers, blanks, preambles, skipped, reconciled status)
       ops.row_dispositions  (source-level row-by-row disposition for every physical row across all inputs)

Privacy: source identity columns are read only in memory to mask comments before storage.
Stored comments have source-known customer/staff names and recognised contact/rego patterns
replaced with tags. Unlisted or ambiguous identities can remain: local model audit is pending.
Name vocabularies and original comments are not written to the database or audit reports.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import sys

import pandas as pd

from common import ROOT, connect, load_config
from privacy import build_name_context, dealer_key, CUSTOMER_COLUMNS, norm

sys.path.insert(0, str(ROOT / "scripts"))
from investigation_support import load_feedback_csv  # CSV loader from the investigation notebook


def read_sources():
    for path in sorted((ROOT / "feedback").iterdir()):
        if path.name.startswith("~$"):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.suffix.lower() == ".csv":
            yield path.name, "csv", load_feedback_csv(path)[0], digest
        elif path.suffix.lower() == ".xlsx":
            for sheet, grid in pd.read_excel(path, sheet_name=None, header=None, dtype=object).items():
                yield path.name, sheet, grid.fillna(""), digest


def header_rows(grid, cfg):
    """Rows holding both a date label and a rating label. A sheet can have several (Ringwood, Frankston)."""
    dates, ratings = set(cfg["columns"]["date"]), set(cfg["columns"]["rating"])
    return [i for i in range(len(grid))
            if {str(v).strip().lower() for v in grid.iloc[i]} & dates
            and {str(v).strip().lower() for v in grid.iloc[i]} & ratings]


def as_text(value):
    return "" if value is None else str(value).strip()


def land_sheet(filename, sheet, grid, cfg, privacy_context=None):
    if privacy_context is None:
        privacy_context = build_name_context([(filename, sheet, grid, "")], cfg, header_rows)
    rows = []
    dispositions = []
    starts = header_rows(grid, cfg)
    if not starts:
        disp = "empty sheet" if grid.empty else "unmapped: no header found"
        for i in range(len(grid)):
            dispositions.append({
                "source_file": filename, "source_sheet": sheet, "source_row": i + 1,
                "disposition": disp, "details": ""
            })
        return rows, 0, dispositions, {"header_rows": 0, "blank_rows": 0, "preamble_rows": 0, "rows_landed": 0}

    preamble_count = starts[0]
    for i in range(preamble_count):
        dispositions.append({
            "source_file": filename, "source_sheet": sheet, "source_row": i + 1,
            "disposition": "preamble", "details": "content withheld"
        })

    header_count = len(starts)
    blank_count = 0

    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(grid)
        header = [as_text(v).lower() for v in grid.iloc[start]]
        col = {std: header.index(h) for std, aliases in cfg["columns"].items() for h in header if h in aliases}
        dispositions.append({
            "source_file": filename, "source_sheet": sheet, "source_row": start + 1,
            "disposition": "header", "details": "mapped header"
        })
        for i in range(start + 1, end):
            cells = grid.iloc[i]
            if not any(as_text(v) for v in cells):
                blank_count += 1
                dispositions.append({
                    "source_file": filename, "source_sheet": sheet, "source_row": i + 1,
                    "disposition": "blank", "details": ""
                })
                continue
            get = lambda k: as_text(cells.iloc[col[k]]) if k in col else ""
            dept = get("department")
            if not dept and any(filename.startswith(p) for p in cfg["department_from_sheet"]):
                dept = sheet
            customer_values = [as_text(cells.iloc[j]) for j, label in enumerate(header) if norm(label) in CUSTOMER_COLUMNS]
            original_comment = get("comment")
            masked_comment, privacy_meta = privacy_context.mask(
                original_comment, dealer_key(filename, get("site"), cfg), customer_values)
            comment_identity = privacy_context.identity(original_comment)
            rows.append({
                **privacy_meta, "comment_identity": comment_identity, "comment_original_length": len(original_comment),
                "source_file": filename, "source_sheet": sheet, "source_row": i + 1, "header_row": start + 1,
                "date_raw": ("Total" if get("date").lower().startswith("total") else "[SOURCE NOTE]" if get("date").lower().startswith(("site closed", "***")) else get("date")), "department_raw": dept, "rating_raw": get("rating"),
                "rating_header": header[col["rating"]], "comment": masked_comment,
                "site_raw": get("site"), "source_ref": get("source_ref"),
            })
            dispositions.append({
                "source_file": filename, "source_sheet": sheet, "source_row": i + 1,
                "disposition": "landed", "details": ""
            })

    counts = {
        "header_rows": header_count,
        "blank_rows": blank_count,
        "preamble_rows": preamble_count,
        "rows_landed": len(rows),
    }
    return rows, header_count, dispositions, counts


def main(database=None):
    cfg = load_config()
    skip = {(s["file"], s["sheet"]): s["reason"] for s in cfg["skip"]}
    landed, registry, all_dispositions = [], [], []
    sources = list(read_sources())
    privacy_context = build_name_context(sources, cfg, header_rows)
    for filename, sheet, grid, digest in sources:
        entry = {"source_file": filename, "source_sheet": sheet, "sha256": digest, "physical_rows": len(grid)}
        if (filename, sheet) in skip:
            skip_reason = skip[(filename, sheet)]
            for i in range(len(grid)):
                all_dispositions.append({
                    "source_file": filename, "source_sheet": sheet, "source_row": i + 1,
                    "disposition": "skipped_sheet", "details": skip_reason
                })
            registry.append({
                **entry,
                "rows_landed": 0,
                "header_rows": 0,
                "blank_rows": 0,
                "preamble_rows": 0,
                "skipped_rows": len(grid),
                "header_segments": 0,
                "reconciled": True,
                "status": "skipped: " + skip_reason
            })
            continue

        rows, segments, disp, counts = land_sheet(filename, sheet, grid, cfg, privacy_context)
        status = "landed" if segments else ("empty sheet" if grid.empty else "NO HEADER FOUND - check mapping")
        total_accounted = counts["rows_landed"] + counts["header_rows"] + counts["blank_rows"] + counts["preamble_rows"]
        reconciled = (total_accounted == len(grid))
        registry.append({
            **entry,
            "rows_landed": counts["rows_landed"],
            "header_rows": counts["header_rows"],
            "blank_rows": counts["blank_rows"],
            "preamble_rows": counts["preamble_rows"],
            "skipped_rows": 0,
            "header_segments": segments,
            "reconciled": reconciled,
            "status": status
        })
        landed += rows
        all_dispositions += disp

    raw = pd.DataFrame(landed)
    raw["loaded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    reg = pd.DataFrame(registry)
    disp_df = pd.DataFrame(all_dispositions)

    audit_fields = [c for c in raw.columns if c.startswith("masked_") and c.endswith("_count")]
    audit_records = [{"rule": c, "comments_affected": int(raw[c].gt(0).sum()), "replacement_count": int(raw[c].sum())} for c in audit_fields]
    audit_records.append({"rule": "ollama_residual_name_audit", "comments_affected": None, "replacement_count": None})
    privacy_audit = pd.DataFrame(audit_records)
    # Validate before replacing any persisted Bronze tables.
    if not reg.reconciled.all() or reg.status.str.startswith("NO HEADER").any():
        raise ValueError("Bronze validation failed: unreconciled or unmapped source; database unchanged")
    if disp_df.duplicated(["source_file", "source_sheet", "source_row"]).any():
        raise ValueError("Duplicate source-row dispositions; database unchanged")
    if len(disp_df) != int(reg.physical_rows.sum()):
        raise ValueError("Physical row reconciliation failed; database unchanged")
    con = connect(database)
    con.execute("BEGIN TRANSACTION")
    con.execute("CREATE OR REPLACE TABLE bronze.raw_responses AS SELECT * FROM raw")
    con.execute("CREATE OR REPLACE TABLE ops.file_registry AS SELECT * FROM reg")
    con.execute("CREATE OR REPLACE TABLE ops.row_dispositions AS SELECT * FROM disp_df")
    con.execute("CREATE OR REPLACE TABLE ops.comment_masking_audit AS SELECT * FROM privacy_audit")
    con.execute("COMMIT")
    con.close()

    unreconciled = reg[~reg.reconciled]
    if not unreconciled.empty:
        raise SystemExit(f"Unreconciled sheets detected: {unreconciled[['source_file', 'source_sheet', 'physical_rows']].values.tolist()}")

    names_changed = raw[["masked_customer_count", "masked_staff_count", "masked_person_count"]].sum(axis=1).gt(0)
    print(f"Comment masking: {int(names_changed.sum())} comments had source-known names masked; "
          "Ollama residual audit not run; residual risk unmeasured.")
    print(f"bronze: {len(raw)} rows landed from {len(reg)} file/sheet sources "
          f"({(reg.status.str.startswith('skipped')).sum()} skipped by decision). "
          f"All {len(disp_df)} physical rows reconciled.")
    unmatched = reg[reg.status.str.startswith("NO HEADER")]
    if not unmatched.empty:
        raise SystemExit(f"Unmapped sources: {unmatched[['source_file', 'source_sheet']].values.tolist()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load masked feedback into Bronze with source-row reconciliation")
    parser.add_argument("--database", type=str, help="DuckDB output path; defaults to kestrel.duckdb")
    args = parser.parse_args()
    main(args.database)
