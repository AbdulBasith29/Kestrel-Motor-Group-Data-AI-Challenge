# Business-answer SQL correction

The applicant authored the original business-answer queries. As pasted, their title lacks a SQL comment marker and therefore does not parse. Commenting the title makes its eight SELECTs run against the private data/bronze_review.duckdb from the project directory, but it cannot run against the reporting-only data/gold_reporting.duckdb: that file intentionally has no Silver tables. Its relative reference CSV paths also depend on the current working directory. The shown input-redirection command is Unix-style and is not supported as written by PowerShell.

Codex adapted the applicant's business queries to the current Gold schema in analysis/business_answers.sql; this is an adaptation of the applicant's analysis, not an AI-originated set of business questions. It reads only Gold models, no raw reference CSVs or Silver comments. Attach the reporting file once in the viewer, then run the SQL in the editor. Alternatively, from the project directory:

```powershell
.\.venv-gold\Scripts\python.exe scripts/run_business_answers.py
```

The Python runner uses read-only input, executes all eight result sets and writes local CSVs to data/business_answers/. It works independently of the shell's input-redirection syntax and uses script-relative paths. Aggregate verification is in outputs/business_answers_verification.json. All eight queries executed successfully.

Result corrections:

- Unknown dates remain outside both halves instead of falling into H2. Dated-only trend denominators are explicit.
- The four-dealer cohort is computed from the largest positive H1-to-H2 rating-negative changes with at least 30 valid ratings in each half. It produces the same four source codes as the supplied list in this pack, without hard-coding the conclusion. This remains exploratory selection on observed outcomes, not a pre-registered/causal comparison.
- Department comparisons keep each department's denominator visible. The middle rating band includes fractional normalised scores; it is not labelled simply rated 3.
- Driver queries use the Gold bridge's validated, current-text-matched AI outputs, preserve review flags and show both all-negative and AI-enriched-negative denominators. Strict-negative and negative-or-mixed polarity counts are distinct. The trend uses the same rating-negative definition and excludes undated rows.
- The rating-versus-AI comparison includes unrated comments and error/holdout statuses. It is descriptive alignment, not the independent human-label accuracy evaluation.
- The H2-cohort financial sensitivity uses excess H2 job proxy * assumed churn fraction * two future jobs * revenue per job. The extra separate x2 from the pasted formula is removed. If annualising the flow of affected customers from six to twelve months were intended, that would be a different, explicitly justified scenario. Zero job volumes use NULLIF; missing baseline/half-year samples are not converted into zero exposure by greatest(NULL,0).

This Q3 remains a hypothetical job-based sensitivity. Service jobs are not distinct customers, the sample-to-population extrapolation and 10/25/40% churn/visit assumptions are unverified, and outputs are not measured losses, profits or forecasts. It is a separate scenario from Gold's simpler 1/2.5/5% revenue-exposure sensitivity; do not combine them or treat either as established value.

During development, DuckDB's extracted statement text caused leading comment-based query labels to shift to the following result. Codex replaced them with inline query markers and checked that all eight output names match their result schemas. Source data were unchanged. These analysis additions remain uncommitted.
