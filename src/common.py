"""Shared paths and config for the pipeline."""
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "kestrel.duckdb"


def load_config():
    return yaml.safe_load((ROOT / "config" / "sources.yml").read_text(encoding="utf-8"))


def connect(database=None):
    con = duckdb.connect(str(database or DB_PATH))
    for schema in ("bronze", "silver", "gold_staging", "gold", "ops"):
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    return con


def by_prefix(table, filename):
    """Look up a value keyed by file-name prefix."""
    return next((v for k, v in table.items() if filename.startswith(k)), None)
