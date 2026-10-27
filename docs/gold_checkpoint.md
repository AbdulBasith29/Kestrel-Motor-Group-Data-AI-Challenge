# Gold reporting models — review checkpoint

This milestone prepares the assignment's business questions: negative feedback drivers, changes over the year, dealership/department priorities and a transparent financial sensitivity. It performs no new AI inference. The evaluation/AI-log checkpoint was committed and pushed as db5bc09 before this separate reporting work.

## Verified output

12 dbt table models and 43 data tests passed. Five Python tests also passed, proving that failed/incomplete builds and restricted columns block publication, existing Gold survives a failed gate, and the export contains only reporting tables. The first export attempt inherited read-only mode from its source connection; Codex corrected it to attach the source read-only from a separate writable in-memory connection, then reran the tests and build.

The reporting file is data/gold_reporting.duckdb (storage version 64 for the Antigravity viewer). It contains only the gold schema and 12 tables: no Bronze/Silver tables, source comments, customer/staff/contact columns, name proposals, caches or spend ledgers. It is a freshly constructed file, not a private database with tables merely dropped. Do not point Tableau at data/bronze_review.duckdb, which remains the restricted working database.

Counts: 7,089 accepted feedback records; 7,079 valid ratings; 1,579 ratings <=2; 7,768 response/theme links; 864 monthly revenue records and 864 dealer/department/month reporting rows; 72 annual dealer/department summaries. Quality reporting has 73 groups because excluded source rows can have Unknown department. Revenue reconciles to AUD 838,685,990.00 in the fact, monthly mart and annual mart. The ten missing dates and ten missing ratings remain explicit. Source/reference hashes and Silver feedback content were unchanged.

AI statuses: 5,358 successful structured results, two provider errors, one not-enriched holdout and 1,728 responses without comments. All AI labels remain provisional; sample evaluation is not per-row approval. Known review flags and model/prompt versions remain available as reporting metadata.

## Reproduce

With the existing Bronze/Silver/enrichment database and original reference/ CSVs present:

```powershell
python -m pip install -r requirements-gold.txt
python -m unittest discover -s tests -p test_gold_publication.py -v
python src/gold.py
```

The tested isolated environment is .venv-gold with dbt-core 1.12.6, dbt-duckdb 1.11.1 and DuckDB 2.0.0. Exact packages are recorded in reproducibility/gold-environment-lock.txt. A different input/output can be selected with --database and --output; the export must be a separate file inside data/. Close its viewer connection before replacing an existing export on Windows.

The runner executes dbt build in gold_staging, checks current run_results.json for every reviewed model and passing tests, blocks restricted columns, publishes known models transactionally to the working database's gold schema, then atomically replaces the separate reporting file. Old Gold/export survives dbt or validation failure. Exports are local under data/reporting_exports/ (one CSV per model); safe aggregate evidence is in outputs/gold_verification.json, gold_monthly_summary.csv, gold_theme_summary.csv and gold_dealer_summary.csv. No comments are exported.

The existing uncommitted flows/pipeline.py is a separate draft and is not integrated with this reporting runner. Use src/gold.py for this checkpoint; orchestration comes after model review.

## Grains and safe joins

- dim_dealer: one official dealer; dim_month: one reporting month; dim_department: Sales/Service/Parts/Unknown; dim_theme: one controlled theme.
- fct_feedback: one accepted source response, with typed rating/date and AI metadata, no comment or identifier columns. AI results must match the current masked-comment hash; stale results are flagged rather than used.
- bridge_feedback_theme: one response/theme with per-theme polarity. A response can have up to three themes; their counts are not additive unique-response totals.
- fct_monthly_revenue: one dealer/month/department, unpivoted from the 288 source dealer-month rows. Financial amounts are DECIMAL(18,2).
- mart_dealer_dept_month: independently aggregated feedback joined to revenue once. A full join preserves feedback-only keys. Zero feedback does not establish zero dissatisfaction.
- mart_theme_drivers: dealer/department/month/theme counts, including an undated bucket. Revenue is deliberately absent; never join revenue directly to this bridge/mart and sum it.
- mart_dealer_dept_summary: annual feedback (including undated responses) joined to separately aggregated annual revenue once.
- mart_feedback_quality: accepted/excluded records, missing dates/ratings and AI failure/coverage flags.
- mart_opportunity_scenarios: dealer/department/scenario sensitivity proxy. Filter one scenario; never add different scenarios together.

## KPI definitions and assumptions to review

Rating-negative means rating_1to5 <=2. The denominator is valid customer ratings, never all responses. Missing scores remain null, including the negative flag. Negative share is a fraction in [0,1], displayed as a percentage in the dashboard. Mean rating is calculated only from valid values. The approved source-scale conversions are retained as analytical harmonisation assumptions, not proof of identical survey constructs.

A rating-negative driver mention requires a negative customer rating AND a theme polarity of negative or mixed. A positive staff-service theme in a negative repair complaint is therefore not automatically a negative driver. A stricter negative-only polarity count and separate text-negative/mixed counts are available. Driver share uses rating-negative responses with successful AI as its denominator; multi-label shares can sum over 100%. Review-flagged versus unflagged driver counts remain separate. AI coverage means successful structured enrichment/nonblank comments; it is not calibrated semantic accuracy and includes unclear results.

Unknown dates contribute to annual/overall feedback but not monthly trends or revenue-month joins. No dates are imputed. feedback_count_per_1000_units is descriptive feedback count divided by source transaction volume; it is not a distinct-customer survey response rate. The reference lists zero activity after Shepparton's March closure; tests enforce this. Newcastle's Hunter alias remains an applicant-approved, unconfirmed mapping and is flagged through assumed_dealer_responses.

Minimum 30 valid ratings is a proposed stability flag for comparison/scenario display, not a confidence guarantee or a business-approved threshold; low-count rows remain in the data. Change minimum_rated_responses in dbt_project.yml if needed. Comparisons remain subject to uneven collection, coverage and source-template changes.

The financial sensitivity first computes annual revenue * negative feedback share, labelled negative_share_associated_revenue_proxy_aud. Multiplying that proxy by 1%, 2.5% or 5% gives scenario_value_proxy_aud. This assumes the survey share can stand in for revenue exposure and a stated portion could be influenced: neither is established by this pack. The result is not measured lost revenue, recoverable profit, churn, causation or a forecast. It must not be presented as a valuation or used as the only priority measure.

## First observations to verify

Provisional rating-negative driver mentions are led by communication/follow-up (559) and waiting/scheduling (492), followed by pricing/value (253). These are model-derived multi-label counts and retain review flags. Among dated responses, negative-rating share is 668/3,381 (19.76%) in Oct–Mar and 908/3,688 (24.62%) in Apr–Sep. This describes the collected feedback, not a population trend or causal effect.

The largest negative-rating counts with at least 30 valid ratings are Parramatta Service (113/311), Dandenong Service (110/319) and Chermside Service (87/314). These are candidates for business investigation, not final recommendations. Review counts, source coverage, operational context and AI limitations before interpreting priorities or scenarios.

## Applicant review

Attach data/gold_reporting.duckdb once with the chuckjonas DuckDB extension. The Attach input takes the file path, not SQL. Open scripts/review_gold.sql and execute its queries from the SQL editor. The catalog is gold_reporting and the schema is gold (for example SELECT * FROM gold_reporting.gold.mart_dealer_dept_summary;).

Check the response/rating denominators, three identical revenue totals, the top driver counts/polarities, missing-date handling and provisional AI coverage. Confirm the proposed minimum sample/scenario assumptions before using them in a final dashboard. Gold code and aggregate outputs are saved locally for review and are not committed or pushed yet.

Applicant contributions: the implementation guide and overall architecture, the idea/design of reporting marts, original business-answer SQL, source investigation, initial Silver implementation, mapping/KPI decisions, manual AI labels and discovery of the redaction defect. Codex contributions here: implementation and expansion of Gold SQL against that design, schema adaptations and corrections, grain/revenue/privacy/publication tests, reporting export and verification. The marts concept and original business queries must not be attributed to Codex.


Optional-AI baseline: if no Gemini result table exists, the Gold runner creates its empty typed contract without looking up a key or calling any model. Rating/revenue reporting remains available; nonblank comments are shown as not enriched, and no themes/sentiments are invented. A publication test verifies this path and rejects any attempted provider call. This does not recreate excluded AI caches or claim an AI step has run.
