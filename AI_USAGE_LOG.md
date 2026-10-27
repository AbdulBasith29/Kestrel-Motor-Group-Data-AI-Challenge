# How I worked

I designed the solution and used AI to build it faster. I wrote the implementation guide and architecture (Bronze/Silver/Gold in DuckDB, YAML source config, dbt marts and separate AI enrichment), made or approved the business and data decisions, and reviewed the work before committing each milestone.

- **Codex:** generated or adapted much of the notebook, ingestion, masking, enrichment, evaluation and Gold implementation, and ran tests. I wrote the initial Silver implementation; Codex later reviewed, refactored and tested it.
- **Claude:** helped review the repo against the brief, challenge design choices and draft business-answer SQL from my questions. The business questions and marts design were mine; Codex later adapted the SQL to Gold.
- **Gemini:** processed 5,360 comments, producing 5,358 successful structured results and two errors. Only preprocessed comments were sent, but residual names remained. Accounted API cost, including name-repair work, was approximately US$1.94.

**My decisions:** the canonical schema; negative = a normalized rating of 2 or below; missing ratings stay null; source-specific handling (Ringwood's ten-point conversion, Hunter = Newcastle as a flagged assumption, Penrith's copied tab counted once, Chermside's overlapping versions counted once, Toowoomba's summary excluded from response facts, and Shepparton's closure/year corrections); role-specific name masking before storage; switching from Ollama to Gemini after the local pilot; evaluation approach; and review of sizing assumptions. Some implementation parameters and proposed mappings still require my confirmation.

## Key prompts (paraphrased)

1. “Inspect every file and every sheet, not just the first, and list anything that would break a simple concat.” I then checked the findings by hand against all 52 files.
2. “How do I know your masking actually worked? Show me what it missed.”
3. “Keep missing customer ratings null. Keep AI sentiment separate.”
4. “Return JSON only, use fixed theme IDs, and flag any person name still visible.”
5. “Leave the human label columns blank. I label first, then compare against the model.”
6. “Revenue joins at its own grain, never through the theme bridge, and Gold carries no comment text.”

## Most important discoveries

- **The sources disagree on scale and layout.** Geelong reverses scale direction between years, Ringwood changes template and scale mid-sheet, Penrith has a copied month tab, Chermside has overlapping FINAL versions, and Toowoomba includes a summary sheet alongside response data. These require explicit source rules rather than a simple concatenation.
- **Every physical row is accounted for.** All 7,432 physical rows reconcile; 7,116 rows land in Bronze. Silver retains 7,102 records, of which 7,089 are in analysis and 13 are excluded. The analysis responses agree with the pandas baseline; non-response rows are accounted for separately.
- **Service needs investigation.** The business queries compare negative feedback across departments, dealerships and half-years. Operational events and customer transfers are possible explanations to investigate, rather than evidence that those events caused the change.

## Where AI was wrong, and how I caught it

- **The masking leaked.** I challenged the preview helper. Checks found missed names in prose, landlines, unlabelled registrations and Noosa's Card given by column. I requested a rebuild and tests. Gemini subsequently flagged 663 comments for possible remaining names; some names reached the model, so I do not claim full anonymisation.
- **Name redaction hit the wrong words.** I checked ten Ballarat examples and found eight offset-based proposals damaged unrelated text while leaving names visible. All 663 Gemini offset proposals were invalidated and reprocessed using literal names and exact matching. The ten examples now pass; the wider replacement proposals still need semantic review.
- **The test-row filter could remove real feedback.** Legitimate test-drive language was caught by an overly broad rule. The rule was tightened and regression checks added.
- **The sizing formula needed a clearer time basis.** I challenged the extra ×2. The revised H2-cohort scenario removes it and shows assumed churn at 10%, 25% and 40%. These are illustrative scenarios, not measured lost revenue or forecasts.
- **Other corrections:** I identified the six pipeline defects recorded during review, corrected the claim that Dandenong only had October data, and corrected the attribution of my initial Silver implementation. A test also caught a Gold exporter connection bug, which Codex fixed.

## How I checked the AI output

I supplied 49 labels from a 50-comment review set before comparing model predictions. The set spans dealerships, departments and rating bands and includes known failures.

- **Sentiment:** 46/49 agree (93.9%).
- **Remaining-name flag:** 48/49 agree; one provider error was unassessed. This measures the flag, not correctness of name replacement.
- **Themes:** at least one theme matches on 42/46 scored rows (91.3%). My original theme descriptions were preserved; an AI-assisted crosswalk translated them into the model taxonomy. Three ambiguous mappings were excluded from theme scoring and the crosswalk remains subject to my confirmation.

The model sometimes interprets mention of the parts team as parts availability without a stock issue. I treat those themes with caution. This is a diagnostic sample, not a population accuracy estimate. Gold now passes 49 dbt data tests and excludes customer identifiers, staff identifiers and comment text.

## Local orchestration

I requested Prefect orchestration against my implementation guide. Codex replaced the earlier draft with a thin flow over the existing CLI commands, kept Gemini opt-in, and added stop-on-failure and AI-only retry tests. Six orchestration tests passed, including real Prefect failure/retry tests with stubbed commands. A full real-data run with Gemini disabled passed all 43 dbt tests and eight business queries; source files and the original working database stayed unchanged. The first run exposed a missing Excel-reader dependency in the isolated environment, which was installed before the successful rerun. This does not implement incremental arrival/archive handling or row-level run recovery.

## What I chose not to build

My guide also covers a file watcher and incremental run-state/retry lifecycle. These are not implemented in the current checkpoint. The Tableau story is now published; automatic refresh of the public copy and the full file-arrival demonstration remain outstanding.

Raw source data, review labels, databases and the API key are excluded from Git. Detailed implementation evidence remains in the checkpoint documents and verification outputs.

## Dealer history

My guide proposed SCD2 dealer history and I requested its implementation. Codex implemented the dbt snapshot, reporting history dimension and isolated lifecycle/integrity tests. The isolated lifecycle test, five publication tests, all eight business queries and 49 dbt data tests passed. Initial validity records observation time; no earlier dealer history or historical event-time attribution is invented.

## Published reporting

I supplied the published Tableau Public story. Codex opened the overview and priority pages, inspected local aggregate extract headers and the packaged workbook file list, and updated submission links/status. The monthly extract reconciles to 7,079 dated responses, 7,069 rated and 1,576 negative; full Gold totals include ten undated responses. This is a limited review, not certification of every published mark, interaction or embedded data value. No authorship of the Tableau build is inferred from this documentation update.
