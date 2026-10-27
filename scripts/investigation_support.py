"""Source inventory and parsing support for the findings-first notebook."""
from pathlib import Path
import csv
import io
import hashlib
import pandas as pd

def load_feedback_csv(filepath):
    filepath = Path(filepath)
    content = filepath.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"Unsupported encoding: {filepath.name}")
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    if not first_line:
        raise ValueError(f"Empty CSV: {filepath.name}")
    delimiter = csv.Sniffer().sniff(first_line, delimiters=",;\t").delimiter
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter, strict=True))
    widths = {len(row) for row in rows if row}
    if len(widths) != 1:
        raise ValueError(f"Ragged CSV records in {filepath.name}: widths={sorted(widths)}")
    grid = pd.DataFrame(rows).fillna("")
    return grid, {"encoding": encoding, "delimiter": repr(delimiter)}

DATE_LABELS = {"date", "date received", "submitted_at", "month", "when"}
CONTEXT_LABELS = {"dept", "department", "area", "comments", "comment", "feedback", "verbatim", "review"}
def header_candidates(grid):
    result = []
    for index, row in grid.iterrows():
        values = [str(v).strip().lower() for v in row]
        labels = set(values)
        if labels & DATE_LABELS and labels & CONTEXT_LABELS:
            exact = [str(v) for v in row if str(v).strip()]
            result.append({"source_row": int(index) + 1, "exact_headers": exact,
                           "normalized_headers": [v.strip().lower() for v in exact]})
    return result

def build_inventory(project_dir):
    PROJECT_DIR = Path(project_dir)
    FEEDBACK_DIR = PROJECT_DIR / "feedback"
    files = sorted(p for p in FEEDBACK_DIR.iterdir() if p.suffix.lower() in {".csv", ".xlsx"} and not p.name.startswith("~$"))
    file_inventory = pd.DataFrame([
        {"filename": p.name, "format": p.suffix.lower(), "bytes": p.stat().st_size,
         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in files
    ])
    assert not file_inventory.empty, "No supported files found."
    raw_grids = {}
    parser_settings = {}
    read_errors = []
    for path in files:
        try:
            if path.suffix.lower() == ".csv":
                grid, settings = load_feedback_csv(path)
                raw_grids[(path.name, "csv")] = grid
                parser_settings[path.name] = settings
            else:
                with pd.ExcelFile(path, engine="openpyxl") as book:
                    for sheet in book.sheet_names:
                        try:
                            raw_grids[(path.name, sheet)] = pd.read_excel(book, sheet_name=sheet, header=None, dtype=object, keep_default_na=False)
                        except Exception as exc:
                            read_errors.append({"filename": path.name, "sheet": sheet, "error": str(exc)})
        except Exception as exc:
            read_errors.append({"filename": path.name, "sheet": "", "error": str(exc)})

    sheet_overview = pd.DataFrame([
        {"filename": name, "sheet": sheet, "physical_rows": len(grid), "physical_columns": len(grid.columns)}
        for (name, sheet), grid in raw_grids.items()
    ])
    structure_records = []
    for (name, sheet), grid in raw_grids.items():
        headers = header_candidates(grid)
        structure_records.append({
            "filename": name, "sheet": sheet, "physical_rows": len(grid),
            "physical_columns": len(grid.columns), "header_candidates": headers,
            "candidate_rows": [h["source_row"] for h in headers],
            "header_status": "review: multiple headers" if len(headers) > 1 else "candidate found" if headers else "review: no header candidate"
        })
    audit_df = pd.DataFrame(structure_records)

    header_records = [
        {"filename": r["filename"], "sheet": r["sheet"], "source_row": h["source_row"],
         "signature": " | ".join(h["normalized_headers"])}
        for r in structure_records for h in r["header_candidates"]
    ]
    headers_df = pd.DataFrame(header_records)
    return {'files': files, 'file_inventory': file_inventory, 'raw_grids': raw_grids, 'parser_settings': parser_settings, 'read_errors': read_errors, 'sheet_overview': sheet_overview, 'structure_records': structure_records, 'audit_df': audit_df, 'headers_df': headers_df}
