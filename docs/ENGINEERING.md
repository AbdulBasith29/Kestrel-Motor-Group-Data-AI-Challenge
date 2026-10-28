# Engineering notes

Detail behind the pipeline that the main [README](../README.md) leaves out. None of this is needed to read the analysis.

## Gold build and publication gate

`python src/gold.py` runs `dbt build` (13 models, 49 tests) in a staging schema, blocks restricted columns (comments, names, contacts), and publishes only if every model and test passes. It then replaces `data/gold_reporting.duckdb`, a separate reporting-only file with the `gold` schema and no Bronze or Silver tables. If a build or test fails, the previous Gold stays in place. Aggregate evidence is in `outputs/gold_verification.json`.

To browse it, attach `data/gold_reporting.duckdb` in a DuckDB viewer and run the queries in `scripts/review_gold.sql` (catalog `gold_reporting`, schema `gold`).

## Tableau refresh

Rebuild Gold, rerun `python scripts/run_business_answers.py`, copy the refreshed Q3 result to `outputs/business_answers/q3_value_at_risk.csv`, then run `python scripts/prepare_tableau.py` and `python scripts/build_tableau_workbook.py <extracts dir> --extracts <extract-backed .twb>` (see `tableau/BUILD_GUIDE.md`). Refresh/reconnect the workbook data sources in Tableau and republish. A packaged workbook carries its own copy of the data: regenerating local CSVs or running Prefect does not update the public story automatically.

The generated `tableau/kestrel_cx.twb` points at an absolute extracts path on my machine. On another machine, rerun `scripts/build_tableau_workbook.py` with your own extracts folder, or re-point the data sources in Tableau.

## Local orchestration limits

Run history is kept locally under ignored `data/prefect/` unless an existing Prefect server configuration overrides it. No cloud setup is required. Each step invokes the same CLI listed in the README. The Gold CLI owns the dbt test/publication gate. A Silver failure prevents Gold and answers; an exhausted AI retry also stops publication. Gemini has at most three attempts and its dollar ceiling is **per attempt**, so a USD 5 setting can allow up to USD 15 across retries; cached successes are reused. The flow does not log comment text or subprocess output. This is batch orchestration, not the guide's incremental file watcher, hash-skip/archive lifecycle or row-level run registry.

To view local run history in the Prefect UI, start the server from the project root in one terminal:

```powershell
$env:PREFECT_HOME = Join-Path (Get-Location) 'data/prefect'
prefect server start --host 127.0.0.1
```

Open `http://127.0.0.1:4200`. In a second terminal using the same Python environment, run:

```powershell
$env:PREFECT_API_URL = 'http://127.0.0.1:4200/api'
python flows/pipeline.py
```

The temporary server used by a plain CLI run stops when that process exits; the local history remains. Do not launch concurrent flows against the same DuckDB files. Tests: `python -m unittest discover -s tests -p test_prefect_pipeline.py`.

## Dealer reference history (SCD2)

Each Gold build snapshots `reference/dealerships.csv` before building dependent models. Changes to dealership name, suburb, state, region, brands, status or closure date close the previous version and create a new version. Unchanged rows retain their version IDs. A removed dealer has its current version closed; reappearance creates a new version.

`gold.dim_dealer_history` exports the version ID, dealer attributes, `valid_from`, `valid_to` and `is_current`. Intervals are `[valid_from, valid_to)`; null `valid_to` means current. `gold.dim_dealer` stays one current row per dealer so existing report joins do not multiply feedback or revenue.

Dates record **when the pipeline observed a reference change**, not when it took effect in the business. The source has no attribute-change timestamp or earlier reference versions: the first run initialises history and does not reconstruct 2025/26 dealer attributes. Closure date remains a source attribute, distinct from snapshot validity. Historical feedback/revenue reports still use the current dealer view; an event-time SCD join would need trustworthy effective-dated reference history. Tests cover unchanged reloads, changes, deletions, reappearance, non-overlapping intervals and current/reference reconciliation. Run `python -m unittest discover -s tests -p test_dealer_history.py` for the isolated fixture test.

## Watch source arrivals

```powershell
python flows/watch.py          # stay running; Ctrl+C stops it; Gemini off
python flows/watch.py --once   # settle and process the current inputs once, or skip unchanged success
```

Watchdog observes `feedback/`, `reference/` and `config/`. A startup scan catches offline changes, temporary Excel lock files are ignored, and a three-second quiet window plus readable, repeated hashes avoids starting on a changing input. A periodic scan also catches missed events. This is a stability heuristic: a writer paused longer than the quiet window can still resume later.

Changed inputs run the existing Prefect batch sequentially. The watcher and manual Prefect runs share an OS-held writer lock; use these entry points rather than running standalone writers concurrently. Only the latest successful manifest is skipped. Failures are retried after 30 seconds (including unchanged failed inputs); interrupted attempts are marked failed on restart. Inputs changing during a run are marked superseded and rerun after settling, rather than marked successfully loaded. The current pipeline can already have published an intermediate report before that final change check: it is not an isolated immutable-input transaction.

Local `data/watcher/runs.sqlite` records batch run ID, manifest hash, state, times and safe failure category. Received source copies go to `data/watcher/archive/` after success or `data/watcher/quarantine/` after failure/supersession. Active input files are never moved. These archives contain raw source data and remain restricted and outside Git; retention cleanup is not implemented. Received copies are retained under `received/` as well, avoiding folder-renaming locks in synced directories; archive receipt failures remain retryable. The SQLite ledger is separate from DuckDB row lineage; this is **batch hash-skip**, not row-level incremental ingestion.

Gemini remains off unless `--enrich` is passed. Its existing task-level retries and per-attempt budget apply; a later whole-batch retry after exhausted AI failures repeats ingestion. No scheduled/public Tableau refresh is triggered. Existing mapping configuration must cover an arriving source; unknown layouts stop the pipeline and remain retryable after configuration is corrected.

Watcher state is bound to database destinations and enrichment mode. For a separate demo use `--state-dir data/watcher_demo --database data/demo.duckdb --reporting-database data/demo_reporting.duckdb`. A fresh state directory triggers one initial baseline run even if the sources were loaded manually before. Tests: `python -m unittest discover -s tests -p test_watcher.py`.

If Gold reports that Windows blocked reporting database replacement, close the DuckDB/viewer connection to `data/gold_reporting.duckdb` and check OneDrive file locks. The existing reporting file stays in place. The watcher records a failed attempt and retries; it does not mark that input successfully loaded.
