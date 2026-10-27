"""Sequential Prefect orchestration of the existing pipeline CLIs.

python flows/pipeline.py [--enrich] [--database data/bronze_review.duckdb]
Gemini is opt-in. Only its task retries; there is no whole-flow retry.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
# Keep local run history in the ignored data directory, with no cloud/telemetry.
os.environ.setdefault("PREFECT_HOME", str(ROOT / "data" / "prefect"))
os.environ.setdefault("PREFECT_SERVER_ANALYTICS_ENABLED", "false")
from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE


def run_command(arguments):
    """Use the active Python and project root; never log source text or secrets."""
    result = subprocess.run([sys.executable, *map(str, arguments)], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        # Underlying steps can echo data in errors; keep their output out of Prefect logs.
        raise RuntimeError(f"{arguments[0]} failed (exit {result.returncode}); rerun that CLI locally for details")
    get_run_logger().info("Completed %s", arguments[0])


@task(name="Bronze ingestion", retries=0, cache_policy=NO_CACHE, persist_result=False)
def bronze(database):
    run_command(["src/bronze.py", "--database", database])


@task(name="Silver validation", retries=0, cache_policy=NO_CACHE, persist_result=False)
def silver(database):
    run_command(["src/silver.py", "--database", database])


@task(name="Optional Gemini enrichment", retries=2, retry_delay_seconds=15,
      cache_policy=NO_CACHE, persist_result=False)
def enrich(database, budget_usd):
    # The runner checkpoints successful responses; retries reuse its cache.
    run_command(["src/gemini_enrichment.py", "--database", database, "--all",
                 "--budget-usd", budget_usd])


@task(name="Gold build tests publication and export", retries=0,
      cache_policy=NO_CACHE, persist_result=False)
def gold(database, reporting_database):
    run_command(["src/gold.py", "--database", database, "--output", reporting_database])


@task(name="Business answers", retries=0, cache_policy=NO_CACHE, persist_result=False)
def business_answers(reporting_database):
    run_command(["scripts/run_business_answers.py", "--database", reporting_database])


@flow(name="kestrel-feedback-pipeline", retries=0, persist_result=False)
def pipeline(database=str(ROOT / "data/bronze_review.duckdb"),
             reporting_database=str(ROOT / "data/gold_reporting.duckdb"),
             enable_enrichment=False, budget_usd=5.0):
    if budget_usd <= 0:
        raise ValueError("budget_usd must be positive")
    bronze(database)
    silver(database)
    if enable_enrichment:
        get_run_logger().info("Gemini enabled: per-attempt budget ceiling USD %s; up to three attempts", budget_usd)
        enrich(database, budget_usd)
    else:
        get_run_logger().info("Gemini disabled; matching existing results may be reused by Gold")
    gold(database, reporting_database)
    business_answers(reporting_database)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database", default=str(ROOT / "data/bronze_review.duckdb"))
    p.add_argument("--reporting-database", default=str(ROOT / "data/gold_reporting.duckdb"))
    p.add_argument("--enrich", action="store_true", help="Opt in to paid Gemini inference")
    p.add_argument("--budget-usd", type=float, default=5.0, help="Gemini ceiling per attempt, not per flow")
    a = p.parse_args()
    pipeline(a.database, a.reporting_database, a.enrich, a.budget_usd)


if __name__ == "__main__":
    main()
