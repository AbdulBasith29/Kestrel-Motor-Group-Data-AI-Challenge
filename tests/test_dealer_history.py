"""Exercise real dbt SCD2 behavior in an isolated fixture project/database."""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import duckdb

ROOT = Path(__file__).resolve().parents[1]


class DealerHistoryTests(unittest.TestCase):
    def test_initial_repeat_change_delete_and_reappearance(self):
        with tempfile.TemporaryDirectory(prefix="dealer-history-", dir=ROOT / "data") as folder:
            base = Path(folder)
            project = base / "dbt"
            shutil.copytree(ROOT / "dbt", project, ignore=shutil.ignore_patterns("target", "logs"))
            refs = base / "reference"
            refs.mkdir()
            database = base / "history.duckdb"
            header = ["dealer_code", "dealership_name", "suburb", "state", "region", "brands", "status", "closed_date"]
            original = ["TEST01", "Fixture dealer", "Fixture suburb", "VIC", "Metro", "FixtureBrand", "Open", ""]
            other = ["TEST02", "Other fixture", "Other suburb", "VIC", "Regional", "FixtureBrand", "Closed", "2026-03-31"]
            def write(rows):
                with (refs / "dealerships.csv").open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.writer(handle); writer.writerow(header); writer.writerows(rows)
            def snapshot():
                exe = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
                env = {**os.environ, "KESTREL_DB_PATH": str(database), "DBT_SEND_ANONYMOUS_USAGE_STATS": "false", "DO_NOT_TRACK": "1"}
                result = subprocess.run([str(exe), "snapshot", "--select", "dealer_history_snapshot", "--project-dir", str(project), "--profiles-dir", str(project), "--vars", json.dumps({"reference_dir": refs.as_posix()})], cwd=base, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout[-3500:] + result.stderr[-1000:])
            def versions():
                with duckdb.connect(str(database), read_only=True) as con:
                    return con.execute("select dealership_name,dbt_scd_id,dbt_valid_from,dbt_valid_to from dealer_history.dealer_history_snapshot where dealer_code='TEST01' order by dbt_valid_from").fetchall()
            write([original, other]); snapshot()
            first = versions()
            self.assertEqual(len(first), 1); self.assertIsNone(first[0][3])
            snapshot()
            self.assertEqual(versions(), first, "Unchanged reload must not create a version")
            changed = original.copy(); changed[1] = "Renamed fixture"; changed[4] = "Regional"
            write([changed, other]); snapshot()
            second = versions()
            self.assertEqual(len(second), 2)
            self.assertEqual(second[0][1], first[0][1])
            self.assertEqual(second[0][3], second[1][2])
            self.assertIsNone(second[1][3])
            self.assertNotEqual(second[0][1], second[1][1])
            write([other]); snapshot()
            self.assertTrue(all(row[3] is not None for row in versions()))
            write([changed, other]); snapshot()
            final = versions()
            self.assertEqual(len(final), 3)
            self.assertEqual(sum(row[3] is None for row in final), 1)
            self.assertTrue(all(row[3] is None or row[2] < row[3] for row in final))


if __name__ == "__main__":
    unittest.main()
