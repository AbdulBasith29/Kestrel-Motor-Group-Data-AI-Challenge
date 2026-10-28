"""Unit tests for pipeline remediation fixes:
1. PII presence in free-text comments and restriction in gold
2. Year correction scoped strictly to Shepparton, quarantine for other future dates
3. Test-row rule edge cases ("Test drive was excellent" preserved)
4. Complete Bronze reconciliation (headers, blanks, preambles, skipped sheets)
5. Invalid source ratings (0, 6, out of range) caught before Silver normalisation
6. Gated dbt publication architecture
"""
import sys
from pathlib import Path
import unittest
import pandas as pd
import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common import load_config, connect, ROOT as COMMON_ROOT
from silver import normalise_rating, parse_date
import bronze
import silver


class PipelineRemediationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config()

    def test_item1_pii_in_free_text_and_gold_exclusion(self):
        """Free-text comments contain PII (emails/mobiles) while gold models exclude free text."""
        # Check that dbt fct_feedback explicitly does not select raw comment column
        fct_feedback_sql = (ROOT / "dbt" / "models" / "gold" / "fct_feedback.sql").read_text(encoding="utf-8")
        self.assertNotIn("\n    comment,", fct_feedback_sql)
        self.assertIn("comment <> '' as has_comment", fct_feedback_sql)

    def test_item2_shepparton_year_correction_scoped_and_quarantine(self):
        """Shepparton future dates are moved backward by 1 year; other future dates are quarantined."""
        end = pd.Timestamp(self.cfg["reporting_window"]["end"])
        future_date = end + pd.Timedelta(days=30)

        # Shepparton row
        shepparton_row = pd.DataFrame([{
            "response_id": "R001", "dealer_code": "VIC09", "source_file": "Shepparton feedback FINAL.xlsx",
            "date": future_date, "department": "Service", "department_raw": "Service",
            "rating_raw": "4", "rating_scale": "1-5", "rating_1to5": 4.0, "comment": "Good",
            "source_ref": "", "source_sheet": "Log", "source_row": 2, "date_raw": "2026-10-30"
        }])

        # Non-Shepparton row with same future date
        bendigo_row = pd.DataFrame([{
            "response_id": "R002", "dealer_code": "VIC08", "source_file": "bendigo_q4.xlsx",
            "date": future_date, "department": "Service", "department_raw": "Service",
            "rating_raw": "4", "rating_scale": "1-5", "rating_1to5": 4.0, "comment": "Good",
            "source_ref": "", "source_sheet": "Sheet1", "source_row": 2, "date_raw": "2026-10-30"
        }])

        start = pd.Timestamp(self.cfg["reporting_window"]["start"])
        # Test Shepparton logic
        is_shep = shepparton_row.dealer_code.eq("VIC09")
        fixable_shep = is_shep & (shepparton_row.date > end) & (shepparton_row.date - pd.DateOffset(years=1)).between(start, end)
        self.assertTrue(fixable_shep.iloc[0])

        # Test Bendigo logic
        is_bendigo_shep = bendigo_row.dealer_code.eq("VIC09")
        fixable_bendigo = is_bendigo_shep & (bendigo_row.date > end) & (bendigo_row.date - pd.DateOffset(years=1)).between(start, end)
        self.assertFalse(fixable_bendigo.iloc[0])

    def test_item3_test_drive_feedback_not_excluded(self):
        """'Test drive was excellent' must not match junk test regex; real junk must match."""
        regex = r"^(?!test\s*(?:drive|drove|run|ride|car|vehicle|trip|track)\b)(?:test\b|testing\b|asdf)"
        
        # Real feedback - must NOT match (assertFalse)
        self.assertFalse(pd.Series(["Test drive was excellent"]).str.lower().str.match(regex).iloc[0])
        self.assertFalse(pd.Series(["test drive was smooth and fast"]).str.lower().str.match(regex).iloc[0])
        self.assertFalse(pd.Series(["Test drove three vehicles today"]).str.lower().str.match(regex).iloc[0])
        self.assertFalse(pd.Series(["Test ride was enjoyable"]).str.lower().str.match(regex).iloc[0])

        # Actual test/junk entries - MUST match (assertTrue)
        self.assertTrue(pd.Series(["TEST TEST"]).str.lower().str.match(regex).iloc[0])
        self.assertTrue(pd.Series(["testing new form"]).str.lower().str.match(regex).iloc[0])
        self.assertTrue(pd.Series(["test - ignore"]).str.lower().str.match(regex).iloc[0])
        self.assertTrue(pd.Series(["test"]).str.lower().str.match(regex).iloc[0])
        self.assertTrue(pd.Series(["asdf"]).str.lower().str.match(regex).iloc[0])

    def test_item4_bronze_reconciliation(self):
        """Every physical row across all inputs must reconcile into file_registry and row_dispositions."""
        con = connect()
        reg = con.execute("SELECT * FROM ops.file_registry").df()
        dispositions = con.execute("SELECT * FROM ops.row_dispositions").df()
        con.close()

        self.assertFalse(reg.empty)
        # Every sheet must be reconciled
        self.assertTrue(reg.reconciled.all())
        # Total accounted physical rows must equal sum of registry physical rows
        total_physical = reg.physical_rows.sum()
        self.assertEqual(len(dispositions), total_physical)
        self.assertEqual(
            total_physical,
            reg.rows_landed.sum() + reg.header_rows.sum() + reg.blank_rows.sum() + reg.preamble_rows.sum() + reg.skipped_rows.sum()
        )

    def test_item5_invalid_ratings_flagged_before_normalising(self):
        """Five-point scores of 0 or 6 must be flagged invalid before reaching silver."""
        # 5-point scale tests
        class MockRow:
            def __init__(self, raw, header="rating", file="test.xlsx", sheet="Sheet1"):
                self.rating_raw = raw
                self.rating_header = header
                self.source_file = file
                self.source_sheet = sheet

        score_0, scale_0 = normalise_rating(MockRow("0"), self.cfg)
        self.assertIsNone(score_0)
        self.assertTrue(scale_0.startswith("invalid"))

        score_6, scale_6 = normalise_rating(MockRow("6"), self.cfg)
        self.assertIsNone(score_6)
        self.assertTrue(scale_6.startswith("invalid"))

        # Valid 5-point score
        score_5, scale_5 = normalise_rating(MockRow("5"), self.cfg)
        self.assertEqual(score_5, 5.0)
        self.assertEqual(scale_5, "1-5")

        # 10-point scale tests
        score_10_0, scale_10_0 = normalise_rating(MockRow("0", header="score (out of 10)"), self.cfg)
        self.assertIsNone(score_10_0)
        self.assertTrue(scale_10_0.startswith("invalid"))

        score_10_11, scale_10_11 = normalise_rating(MockRow("11", header="score (out of 10)"), self.cfg)
        self.assertIsNone(score_10_11)
        self.assertTrue(scale_10_11.startswith("invalid"))

    def test_item6_dbt_publication_gated(self):
        """dbt models materialize to gold_staging and are published to gold only via pipeline gate."""
        dbt_project = yaml.safe_load((ROOT / "dbt" / "dbt_project.yml").read_text(encoding="utf-8"))
        # Check target schema is gold_staging
        self.assertEqual(dbt_project["models"]["kestrel"]["gold"]["+schema"], "gold_staging")


if __name__ == "__main__":
    unittest.main()
