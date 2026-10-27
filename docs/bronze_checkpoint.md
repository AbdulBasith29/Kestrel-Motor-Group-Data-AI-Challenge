# Bronze ingestion review

This milestone turns the inspected source pack into traceable DuckDB rows for the assignment's consolidation and trust requirements. YAML holds the source-specific rules. Bronze keeps mapped raw dates, departments and ratings as text; Silver will validate and normalise them later. Comments are masked before storage. Bronze is a minimised landing table, not a complete copy of every source cell: original files remain the restricted evidence, while every physical row receives a disposition.

## Run it

From the project root, with the original feedback/ directory present:

```powershell
python -m pip install -r requirements-bronze.txt
python -m unittest discover -s tests -p test_comment_masking.py -v
python -m unittest discover -s tests -p test_bronze_ingestion.py -v
python scripts/verify_bronze.py
```

The verifier builds data/bronze_review.duckdb twice and writes outputs/bronze_verification.json. It checks unchanged source hashes, repeat-load equality except timestamps, unique source-row dispositions and absence of structured identity columns. The review database is separate from the existing kestrel.duckdb. To target a chosen database directly: python src/bronze.py --database data/bronze_review.duckdb. Direct execution without --database replaces Bronze in kestrel.duckdb and does not refresh existing Silver/Gold tables.

## Results to evaluate

52 files, 82 file/sheet sources and 7,432 physical rows reconcile as 7,116 landed rows, 79 headers, 14 blanks, 46 preamble rows and 177 rows in four excluded sheets. Notes and totals may still be landed; Silver separates them from responses. Thus 7,116 Bronze rows differ from the CSV baseline's 7,101 responses by design.

Known staff names were replaced in 190 comments, emails in 58, phones in 156 and registration patterns in 486. Categories overlap. No row-local customer names matched comments; this is a matching result, not proof that customer names are absent. Unlisted names and unsupported patterns can remain. All comment text remains restricted pending local-model audit and human evaluation. Original comments and name dictionaries are not persisted by this loader. Existing first-draft CSVs and the older pipeline database have not been sanitised by this milestone.

## Inspect in DuckDB

```sql
SELECT disposition, count(*) AS rows
FROM ops.row_dispositions GROUP BY disposition ORDER BY disposition;

SELECT source_file, source_sheet, physical_rows, rows_landed,
       header_rows, blank_rows, preamble_rows, skipped_rows, reconciled
FROM ops.file_registry ORDER BY source_file, source_sheet;

SELECT source_file, source_sheet, header_row, rating_header, count(*) AS rows
FROM bronze.raw_responses WHERE source_file LIKE 'Ringwood%'
GROUP BY ALL ORDER BY source_file, header_row;

SELECT * FROM ops.comment_masking_audit;
```

Review config/sources.yml for approved aliases and exclusions; src/bronze.py for header segments, lineage and reconciliation; src/privacy.py for role tags and matching limitations. The source file/sheet/row key joins raw_responses to row_dispositions, and file_registry supplies the original file hash. Loaded timestamps are stored on raw rows; this checkpoint replaces current tables rather than retaining historical runs. Unmapped layouts or failed reconciliation block table replacement. The integration test verifies preservation of the prior Bronze tables on an unmapped layout.

## Attribution and next step

The applicant manually investigated the pack, approved mapping/exclusion decisions and requested role-specific pre-storage masking. Claude supplied the initial YAML/DuckDB loader; Codex implemented the masking, review database option, validation-before-write checks, tests and reproducible verification evidence. The applicant inspected the file registry in the Antigravity DuckDB viewer, checked the Wollongong example (139 physical rows = 138 landed + 1 header), accepted this checkpoint and authorised its commit. This spot-check complements the automated checks; it does not certify all residual comment identifiers are removed.

Next: validate and deduplicate into Silver using original-comment equality identifiers so name masking cannot collapse genuinely different comments. Ollama enrichment remains separate and has not processed this dataset.

## Viewer compatibility finding

The installed Python DuckDB is 2.0.0. The Antigravity viewer rejected its storage version 999 because it supports versions 64–68. Codex created a separate local data/bronze_viewer.duckdb copy with STORAGE_VERSION 'v1.0.0' (storage version 64) and verified all four table counts against the original. This copy is a snapshot, not automatically refreshed by the verifier. The original remains unchanged. In chuckjonas's extension, attach the database path once, then execute SELECT queries from a .sql editor using DuckDB: Execute Query; the attachment input accepts paths, not queries.

To recreate a fresh viewer copy using DuckDB 2.0, run these statements in a Python DuckDB connection or matching DuckDB CLI from the project root (use a new destination filename if the copy already exists):

```sql
ATTACH 'data/bronze_review.duckdb' AS original (READ_ONLY);
ATTACH 'data/bronze_viewer.duckdb' AS viewer (STORAGE_VERSION 'v1.0.0');
COPY FROM DATABASE original TO viewer;
DETACH viewer;
DETACH original;
```

The viewer attaches the resulting file as bronze_viewer. Example query: SELECT * FROM bronze_viewer.ops.file_registry;.
