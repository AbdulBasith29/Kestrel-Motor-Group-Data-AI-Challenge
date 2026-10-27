# Silver canonical feedback review

Silver answers the assignment's first two tasks: put differently structured feedback into comparable fields, apply explicit quality rules and retain evidence for exclusions. It reads masked Bronze comments and does not call Ollama.

## Results

7,116 Bronze rows = 14 non-response rows + 7,102 feedback records. Of those feedback records, 7,089 enter analysis and 13 are excluded (four test/junk entries and nine duplicates). All 7,101 CSV baseline records match by source file, sheet and row; their date, dealership, department, normalised rating, analysis inclusion and negative flag agree. The one extra audit record is Southport Feedback Tracker.xlsx / Feedback / row 192: an asdf test entry previously removed as a note. It remains excluded and does not change business totals.

Among accepted records, 7,079 have a valid rating and 1,579 have a normalised rating <= 2. Ten missing ratings are excluded from the rating denominator. Six reviewed Shepparton source rows receive year corrections; ten vague dates remain missing and are excluded from monthly trends. Unknown dealer and department counts are zero in this pack; new unknown dealers are excluded, while unknown departments are flagged and retained with a null department (the reporting layer must display Unknown).

## What changed and why

- Original date/rating/department values and source lineage remain alongside standardised fields. Explicit New/Used labels survive as sales_subtype; generic Sales has an unknown subtype.
- Source-row-based response IDs remain stable when the same rows are reordered. They identify file/sheet/row positions, not a permanent business response across edited source exports.
- Geelong 2025 reverses direction; Ringwood ten-point scores use the approved linear conversion; stars and text labels use the YAML mappings. Missing and invalid scores stay null, including the negative flag.
- Only the six configured Shepparton source rows can receive the reviewed year correction. Other future dates are quarantined.
- Duplicate comparison uses pre-mask comment identity so different names replaced by the same tag cannot create false duplicates. Only eligible records can suppress later duplicate candidates.
- Every Bronze row has a silver.row_decisions entry. The canonical table and rule counts are replaced transactionally after the transformation checks pass.
- A new test caught a defect in the draft: a comment with a vague date and no score could be removed as a note. Codex fixed the classification to retain useful comments; explicit source notes/totals remain excluded. Non-finite, unreadable and non-integer source scores are handled as invalid rather than crashing or inventing ratings.

## Reproduce

Install requirements-bronze.txt and build Bronze as described in docs/bronze_checkpoint.md. Then, from the project root:

```powershell
python -m unittest discover -s tests -p test_silver.py -v
python scripts/verify_silver.py
```

The verifier needs the local first-draft data/feedback_validated.csv from commit 2's commands. It runs Silver twice against data/bronze_review.duckdb, compares actual row content, reconciles every Bronze row, checks source hashes and saves outputs/silver_verification.json. outputs/dq_results.csv contains aggregate rule counts; counts can overlap. Direct execution is python src/silver.py --database data/bronze_review.duckdb. Without the option it targets kestrel.duckdb and expects the current masked Bronze schema.

## Review in Antigravity

A compatible local snapshot is available as data/silver_viewer.duckdb, using storage version 64. Attach that file once with the chuckjonas DuckDB extension. Open scripts/review_silver.sql and execute its queries in the SQL editor. These show counts, exclusions, corrections, scales and rating denominators without comment text. The snapshot does not automatically refresh after a later pipeline run.

Focus the manual review on the six year corrections, Geelong/Ringwood scale changes, missing ratings/dates and the excluded test/duplicate counts. Neither this verification nor the inherited masks certifies complete anonymisation; keep the database restricted. Ollama enrichment and residual-name review remain pending.

## AI usage and ownership

The applicant manually inspected the source pack, approved the mappings and business rules, and requested reviewable milestones. The applicant wrote the initial Silver implementation. Codex reviewed and refactored it, added the exact correction allowlist, subtype/source-key preservation, transactional writes, synthetic tests and baseline/repeat-load verifier, and found/fixed the vague-date plus missing-rating classification defect. Seven Silver tests passed. This checkpoint documents those tasks and verification; the applicant authorised committing and pushing this Silver checkpoint after correcting its ownership attribution.
