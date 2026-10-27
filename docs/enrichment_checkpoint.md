# Local Qwen3 enrichment pilot

This milestone addresses the brief's AI text-analysis task. Qwen3 4B runs locally through Ollama, adding sentiment, themes with per-theme polarity and a remaining-name flag to a separate silver.ai_enrichment table. It never fills missing customer ratings or modifies Silver feedback. This is inference, not model training.

## Measured results

20 deliberately selected masked comments completed in 145.41 seconds: 20 valid structured results, zero errors, median 6.94 seconds per comment. The local model flagged one comment for remaining-name review. A cached rerun took 0.64 seconds, used 20 cache hits with zero inference calls, and left Silver feedback unchanged. There are 5,361 eligible comments. A crude median-based fresh full-run estimate is about 10.3 hours, before accounting for cache reuse, comment lengths and machine load. No full run has been performed.

These counts establish execution, not classification accuracy. All 20 results remain pending human review. outputs/enrichment_evaluation.json deliberately reports accuracy as null until applicant labels are provided. The sample reserves four missing-rating cases and spreads low/mid/high ratings across dealers; it is not a representative accuracy estimate for all comments.

## Your review: label before reading model answers

Open data/ai_review_sample.csv locally. It is excluded from Git and contains masked comments, which can still contain identifiers missed by deterministic rules. Fill these columns without inspecting model predictions:

- human_sentiment: positive, negative, mixed, neutral or unclear.
- human_themes: supported theme IDs separated by |, or none. Use no more than three themes.
- human_has_unmasked_name: true or false. Existing [STAFF]/[CUSTOMER]/[PERSON] tags do not count as unmasked names. False does not establish removal of all personal information.
- review_notes: record uncertainty or why you disagree later. Do not paste personal identifiers into committed notes.

Proposed theme IDs in config/enrichment.yml:

- communication_follow_up: updates, explanations and callbacks.
- waiting_time_scheduling: delays, queues and appointment timing.
- workmanship_repair_quality: diagnosis, repair quality and repeat faults.
- staff_service: conduct, courtesy and helpfulness; a staff mention alone is insufficient.
- pricing_value: charges, pricing and perceived value.
- sales_process: purchasing, finance, handover and trade-in.
- parts_availability: stock, parts orders and availability.
- vehicle_product: features and vehicle condition.
- other: a supported theme outside this list.

The taxonomy is an AI-proposed first version for applicant review. Overall mixed sentiment can contain positive staff service and negative waiting time. Per-theme polarity is stored separately so praised topics need not be counted as negative drivers. The current human-label evaluator scores overall sentiment and theme membership, not per-theme polarity: review polarity separately before using it in driver reporting. Expand to a larger held-out set (around 50 comments, including rare themes, ambiguity and sarcasm) before claiming general performance.

## Reproduce

Use requirements-bronze.txt, installed local qwen3:4b and the current masked Silver database. No extra Python SDK or API key is required. From the project root:

```powershell
python -m unittest discover -s tests -p test_enrichment.py -v
python -m unittest discover -s tests -p test_name_audit.py -v
python -m unittest discover -s tests -p test_enrichment_evaluation.py -v
python src/enrichment.py --database data/bronze_review.duckdb --limit 20
python scripts/verify_enrichment.py
python src/evaluate_enrichment.py --database data/bronze_review.duckdb --labels data/ai_review_sample.csv
```

Twenty-one synthetic contract/evaluation tests passed. Tests caught the evaluator's CSV boolean-column inference mistake; Codex fixed it by reading human labels explicitly as strings. Another verification confirms cached reruns preserve the original feedback and avoid inference. Human evaluation reports completed-label coverage, sentiment accuracy (errors count as incorrect), theme precision/recall/F1/exact match, and missed/false remaining-name flags. The evaluator rejects changed review text. It does not certify privacy or calibrate model confidence. Pilot labels are applicant work, not supplied by an AI agent.

The runner supports --all for an explicit full run after evaluation. Oversized comments are flagged as errors instead of silently truncated. Failed requests/contracts receive at most two attempts and are not cached; successful requests are checkpointed individually. Identical requests reuse a cache keyed by comment, complete prompt/schema/options, model digest and Ollama version. Changed source content invalidates attached results. Queries must select the intended prompt/model version; partial runs must not be interpreted as full coverage. Review CSVs are not overwritten if they already exist.

## Locality and privacy

Requests go only to 127.0.0.1:11434. The runner ignores proxy settings, rejects redirects, requires the exact installed model and rejects remote/cloud model metadata. It sends only masked comment text, never customer rating, dealer or identifier columns. Qwen3 therefore sees names the deterministic mask misses; this limitation is explicit. Existing source files and legacy CSVs remain restricted.

Model-proposed name spans are bounds-checked, cannot overlap or replace existing tags, and create proposed_comment only. They never overwrite the source comment automatically. Model-clear is not human approval. Arbitrary model prose and extracted name spans are not persisted in public logs or the cache; controlled labels and the proposed redaction are stored locally. No cloud API was used in this pilot.

## Inspect results

After blind labelling, attach data/enrichment_viewer.duckdb in the chuckjonas extension and run scripts/review_enrichment.sql from the SQL editor. The file is a storage-version-64 snapshot, not a live connection to future runs. The review query exposes the single flagged comment and proposed mask locally. All database and review-text files remain ignored by Git. Aggregate evidence is in outputs/enrichment_pilot.json, enrichment_cache_check.json, enrichment_verification.json and enrichment_evaluation.json.

## Ownership and remaining work

Applicant decisions: use local Ollama to avoid API charges, preserve customer scores independently, role-specific name masks, and review each milestone. Codex contributions: proposed taxonomy/prompt, local runner, cache/error handling, residual-name contract integration, pilot selection, tests, evaluation scaffolding and aggregate verification. The applicant wrote the initial Silver implementation. Human labels, taxonomy approval, per-theme polarity review, broader held-out evaluation and full enrichment remain pending. Nothing in this milestone is committed or pushed yet.

Implementation references: https://ollama.com/blog/structured-outputs and https://ollama.com/blog/thinking (structured JSON responses and think=false).


Current-checkpoint note: the stored timing/cache evidence above is the historical v1 pilot. The prompt now uses exact name mentions (v2) after the applicant discovered offset corruption. scripts/verify_enrichment.py verifies the stored pilot/cache read-only; it does not rerun a changed prompt or incur inference. See docs/gemini_checkpoint.md for the completed Gemini run, invalidation and exact-name correction. Numerical human accuracy remains unmeasured.
