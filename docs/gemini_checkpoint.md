# Gemini enrichment checkpoint

The applicant chose Gemini after comparing the local Qwen3 pilot's runtime with the estimated API cost. Qwen3 remains available; its results are retained separately. This step addresses the brief's requirement to use AI for feedback text and document how its output is checked.

## Measured pilot and full-run policy

The synthetic connection test classified a made-up complaint as negative in 1.91 seconds with reported usage costing approximately US$0.000367. The real pilot processed 19 locally screened masked comments in 7.89 seconds using four workers, costing US$0.006232 in the runner's ledger. All 19 returned valid structured results. The twentieth local pilot comment had a remaining-name flag and was not sent to Gemini.

The applicant then authorised the full run. It selects 5,360 accepted, nonblank, deterministically masked Silver comments and holds one known name flag out. Only 19 of these 5,360 had the extra local name-clear result; the remaining comments have not been certified clear by Ollama or a human. The full run uses the existing deterministic masking and residual contact/registration-pattern checks, blocks current known name flags, and asks Gemini to flag any remaining names. This deliberately expands beyond the locally screened pilot; model-clear is not a privacy guarantee, and any newly flagged name may already have reached Google. No claim of universal anonymisation is made.

Results are separate in silver.ai_enrichment_gemini. Customer ratings and silver.feedback are not changed. Sentiment, up to three themes with individual polarity, name flags and proposed further masks are derived fields, not customer-supplied ratings. Outputs remain pending human review and are not published to dashboard tables.

## Keys, billing and spend

The key is read from GEMINI_API_KEY in the environment or the project's .env file. Single/double quotes are supported. .env and related secret files are ignored by Git; .env.example contains no key. Keys are sent in the request header, never the URL or logs. Requests use the fixed Google HTTPS endpoint, reject redirects and bypass environment proxies. No raw provider error body is logged.

The applicant said they believe the associated project is billing-enabled; this is user-reported and not independently verified by the API call. Confirm this in Google AI Studio/Cloud Billing: Google's unpaid and paid services have different data-use terms. The application does not claim that a working key proves a paid project.

Configured model: gemini-3.5-flash-lite; minimum thinking, 600 maximum output tokens. Standard rates checked on 27 October 2026: US$0.30/million input tokens and US$2.50/million output tokens, including thinking. The code refuses an unreviewed model change. The cumulative US$5 application ledger cap includes failed/unknown-usage reservations; synthetic connection tests are outside that ledger. This is a safeguard for this runner, not a Google account-wide billing cap. Actual provider billing remains authoritative.

A reservation covers the configured maximum of two attempts. The runner schedules only a bounded number of outstanding requests, releases reservations to reported token costs when responses arrive, and stops scheduling when the remaining cap is insufficient. Rate-limit/server errors have bounded backoff. Configuration/auth errors and repeated failures stop further scheduling. Usage, retries, blocked/truncated responses and failed JSON contracts are not silently treated as successful classifications.

## Reproduce or resume

Use requirements-bronze.txt and the current masked Bronze/Silver database. Add the key locally, then run from the project root:

```powershell
python -m unittest discover -s tests -p test_gemini.py -v
python src/gemini_enrichment.py --check-key
python src/gemini_enrichment.py --synthetic
python src/gemini_enrichment.py --database data/bronze_review.duckdb --limit 20 --budget-usd 5 --workers 4
python src/gemini_enrichment.py --database data/bronze_review.duckdb --all --budget-usd 5 --workers 4
```

Do not start a second writer while a run is active. Rerun the same full command after interruption to reuse successful cache entries. Each completed request and its attached results are checkpointed transactionally. Identical masked texts share one request; prompt/schema/model/options changes invalidate the request key. Gemini reports its model version with results, but a cloud model alias can change without changing the request key; revise the prompt/cache version when intentionally benchmarking a new deployed revision.

ops.gemini_spend records conservative accounted costs; ops.gemini_cache holds successful controlled outputs; ops.gemini_holdouts records response IDs and reasons, without comment text. Names/spans and arbitrary model prose are not retained in public logs. Proposed further redaction remains local in the restricted database. Failed results can be retried by rerunning; successful requests are cached. An interrupted request whose usage is unknown keeps its reservation in the ledger.

## Review and evaluation

Label data/gemini_review_sample.csv independently before inspecting predictions. It has 19 blank human-label rows. Use the same label instructions and proposed taxonomy in docs/enrichment_checkpoint.md. The evaluator compares overall sentiment, theme membership and remaining-name flags; per-theme polarity still needs manual evaluation. Do not report execution success as accuracy. Run after the writer has finished:

```powershell
python src/evaluate_enrichment.py --provider gemini --database data/bronze_review.duckdb --labels data/gemini_review_sample.csv
```

The Gemini evaluator writes outputs/gemini_evaluation.json, leaving the Ollama evaluation separate. Expand independent held-out review beyond the pilot before claiming performance across all dealerships. Full-run aggregate evidence is written to outputs/gemini_run.json when the run ends; a held-out comment means full_dataset_processed remains false even if every eligible comment completes.

## Ownership and verification

The applicant chose Gemini, supplied the key locally, authorised the masked pilot and full run, and owns the business decisions and human evaluation. The applicant wrote the initial Silver implementation. Codex added the Gemini REST adapter, isolated results/cache/spend ledger, secret handling, structured validation reuse, bounded concurrent scheduler, holdout rules and tests. Eleven Gemini tests pass, including cache resumption, duplicate-request collapse, and stopping before any API request when the budget is insufficient. Human evaluation and final full-run verification remain pending. Nothing is committed or pushed for this milestone yet.

Sources: https://ai.google.dev/gemini-api/docs/pricing ; https://ai.google.dev/api/generate-content ; https://ai.google.dev/gemini-api/docs/generate-content/thinking ; https://ai.google.dev/gemini-api/terms .


## Completed full-run outcome

The full inference run finished in 2,393.89 seconds (about 40 minutes). After retrying only the three initial failures, 5,358 comments have valid structured outputs, two remain explicitly quarantined with null analytical labels, and one known-name case was held back before external transmission. The runner's cumulative accounted cost is US$1.828531, excluding the small synthetic connection test.

Coverage reconciles: 5,361 accepted nonblank comments = 5,358 valid outputs + 2 quarantined AI errors + 1 pre-transmission holdout. Verification passed with explicit quarantined-error status; it did not declare every AI response valid. Source hashes, Silver comments, scores and baseline analysis membership remained unchanged. A compatible snapshot is available at data/gemini_viewer.duckdb.

Gemini flagged 663 processed comments for possible remaining names; these are model flags, not confirmed privacy incidents or proof that all other text is clear. Those comments had already been transmitted in deterministically masked form. This is evidence that the earlier masks did not establish safe universal release. There are 690 results requiring review, including the quarantined cases. Independent sentiment/theme/name evaluation remains pending, so classification accuracy is unknown. These findings and corrective review work must remain in the honest AI usage record. No enrichment changes have been committed or pushed.


## Superseding correction: offset-based proposals invalidated

The applicant's manual review found proposals replacing unrelated substrings rather than names. All offset-v1 name proposals in the primary database are invalidated. Earlier execution/coverage checks did not establish semantic masking accuracy. Do not use the old proposed_comment field or an already-open viewer snapshot as a clean text export.

The v2 contract copies exact source name strings; Python locates complete literal occurrences and replaces them. It rejects partial words, missing literals, existing tags and overlaps. The first ten applicant examples passed exact local comparisons after rebuilding. The remaining flagged proposals are being rebuilt independently of sentiment/theme labels in silver.name_redaction_review. Names, roles and completeness still need human evaluation; no automatic overwrite of source comments or release approval occurs.

Use the fresh data/gemini_review_fixed.duckdb snapshot and scripts/review_name_repairs.sql once rebuilding finishes. Attach that new path as gemini_review_fixed; detach the old gemini_viewer connection to avoid confusing cached/stale proposals with current results. Role and name decisions remain proposals pending review.


The literal repair command is python src/name_repair.py --limit 0; it reuses completed repair checkpoints and processes bounded batches under the same US$5 ledger. Do not rerun the entire sentiment/theme pipeline just to repair names. The mechanical repair verification is python scripts/verify_name_repairs.py; its status explicitly leaves semantic name/role/completeness accuracy unestablished. Source comments are not overwritten. The old invalidated proposed text remains in the restricted audit table for accountability.


Literal repair completed: 663 flagged records were revisited; 661 have exact-source-match proposals and two have no name identified on the second pass and remain unresolved for human review. Mechanical verification found zero name tags inserted inside words. All ten applicant-supplied examples matched the expected name-only replacements. Source hashes, Silver comments/ratings and baseline analysis membership remained unchanged. Cumulative accounted API cost is US$1.939276. The fresh review snapshot is data/gemini_review_fixed.duckdb, with queries in scripts/review_name_repairs.sql. The old open viewer snapshots remain stale and must be detached.

A final-report aggregation bug in Codex's repair runner surfaced after all request checkpoints had been saved: run() did not return its summary. Codex fixed the return and verified all 663 cached repairs with inference replaced by a failing test stub; zero additional paid requests were needed. Three evaluator regression tests also passed. These checks establish execution and mechanical replacement behavior, not complete/accurate person identification. All proposals are still pending applicant review. No corrective changes are committed or pushed.


## Applicant review acceptance — 28 October 2026

The applicant stated that they completed the requested spot-check and were satisfied with the corrected proposals and sample review. Record this as applicant-reported qualitative acceptance, not exhaustive verification of every comment or a numerical accuracy result. At the time of checking, data/gemini_review_sample.csv still had zero completed human-label rows out of 19. The evaluator therefore retains awaiting_human_labels and null accuracy metrics. No human labels were generated or filled by the agent. Two no-name-found repair cases and two failed enrichment records remain explicitly identified; this acceptance does not silently resolve or reclassify them. No new commit or push is authorised by this review acknowledgement alone.
