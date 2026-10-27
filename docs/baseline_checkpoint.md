# CSV consolidation and validation checkpoint

This milestone addresses the brief's first two tasks: combine the feedback and explain which records and scores can be trusted. It provides a pandas reference baseline before DuckDB ingestion, AI enrichment and reporting.

## Reproduce

Obtain the original assignment feedback/ and reference/ directories separately. From the project root, install requirements-notebook.txt, then run:

```powershell
python src/first_draft/consolidate.py
python src/first_draft/validate.py
```

Review outputs/source_log.csv for each file/sheet and outputs/validation_report.csv for rule counts. Rule counts can overlap; they are not a row reconciliation. Local data/ CSVs retain original comments and must remain restricted. They are excluded from Git. Role masking belongs to the subsequent Bronze milestone; this baseline does not claim to anonymise comments.

## Applicant-approved decisions

The applicant approved these decisions on 27 October 2026 after manually reviewing all 52 feedback files:

- Use explicit dealer and department aliases; group new/used cars under Sales. Hunter to Newcastle is accepted for this assignment but remains an unconfirmed source-to-dealer assumption, not business-owner confirmation. The baseline retains department_raw; a dedicated sales subtype is not yet implemented.
- Exclude Chermside's superseded Q1 version, Penrith's copied June tab, Toowoomba's aggregate summary and Southport's copied reviews from individual-response analysis. Originals remain unchanged.
- Reverse Geelong 2025, map stars to their count, use Tamworth Bad/OK/Good = 1/3/5, and convert Ringwood's 1–10 scale with 1 + (score - 1) * 4 / 9, retaining two decimal places. These are analytical harmonisation choices, not proof that survey scales are equivalent.
- Parse Liverpool's month-first export explicitly, keep vague Ipswich dates missing, and correct only the six reviewed Shepparton year errors.
- Exclude repeat dealer/date/department/raw-rating/comment matches when comments exceed 20 characters; also exclude repeated nonblank dealer/reference pairs. This is an agreed heuristic and can remove coincidentally identical feedback; retain source lineage for review.
- Define rating-based negative feedback as a normalised score <= 2. Missing and invalid ratings stay null and are excluded from rating denominators; no scores are inferred from text.

## AI usage and verification

The applicant inspected sources, selected and approved the business rules, and will evaluate the outputs. Claude generated the original consolidation/validation draft. Codex reviewed this checkpoint, found that the draft could accept an out-of-range score and that its saved report was stale, added source-rating bounds, reran both scripts, and checked focused rating cases. No AI enrichment has been run on these comments. This document records this milestone separately from pending DuckDB/model changes.
