"""Meaningful publication-boundary tests; model SQL is tested by dbt build."""
import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import duckdb
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gold as g
from common import ROOT

class GoldPublicationTests(unittest.TestCase):
    def result(self,status='pass'):
        return {'results':[{'unique_id':'model.kestrel.'+m,'status':'success'} for m in g.MODELS]
                +[{'unique_id':'test.kestrel.revenue_reconciliation','status':status}]}
    def stage(self,c):
        c.execute('create schema gold_staging')
        for model in g.MODELS:c.execute(f'create table gold_staging.{model} as select 1 as value')
    def test_failed_test_preserves_existing_gold(self):
        with duckdb.connect() as c:
            c.execute('create schema gold');c.execute('create table gold.fct_feedback as select 7 as value')
            with self.assertRaises(RuntimeError):g.publish_verified(c,self.result('fail'))
            self.assertEqual(c.execute('select value from gold.fct_feedback').fetchone()[0],7)
    def test_raw_text_column_blocks_publication(self):
        with duckdb.connect() as c:
            self.stage(c);c.execute('alter table gold_staging.fct_feedback add column comment varchar')
            with self.assertRaises(RuntimeError):g.publish_verified(c,self.result())
            self.assertEqual(c.execute("select count(*) from information_schema.tables where table_schema='gold'").fetchone()[0],0)
    def test_export_contains_only_reporting_schema(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            root=Path(folder);(root/'data').mkdir();source=root/'data'/'private.duckdb';dest=root/'data'/'reporting.duckdb'
            with duckdb.connect(str(source)) as c:
                self.stage(c);g.publish_verified(c,self.result())
                c.execute('create schema bronze');c.execute("create table bronze.identifiers as select 'synthetic private value' as customer_name")
            with patch.object(g,'ROOT',root):g.export_reporting(source,dest)
            with duckdb.connect(str(dest),read_only=True) as c:
                self.assertEqual(c.execute('select distinct table_schema from information_schema.tables').fetchall(),[('gold',)])
                self.assertEqual(c.execute('select count(*) from information_schema.tables').fetchone()[0],len(g.MODELS))
    def test_locked_export_preserves_previous_file_and_explains_recovery(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            root=Path(folder);(root/'data').mkdir();source=root/'data/private.duckdb';dest=root/'data/reporting.duckdb'
            with duckdb.connect(str(source)) as c:
                self.stage(c);g.publish_verified(c,self.result())
            with duckdb.connect(str(dest)) as c:
                c.execute('create table previous_export as select 7 as value')
            with patch.object(g,'ROOT',root),patch.object(g.os,'replace',side_effect=PermissionError('synthetic Windows lock')):
                with self.assertRaisesRegex(RuntimeError,'REPORTING_EXPORT_LOCKED'):
                    g.export_reporting(source,dest)
            with duckdb.connect(str(dest),read_only=True) as c:
                self.assertEqual(c.execute('select value from previous_export').fetchone()[0],7)
            self.assertEqual(list((root/'data').glob('*.tmp.duckdb')),[])

    def test_missing_optional_ai_creates_empty_contract_without_inference(self):
        with duckdb.connect() as c,patch('gemini_enrichment.call',side_effect=AssertionError('No external calls allowed')):
            self.assertTrue(g.ensure_ai_contract(c))
            self.assertEqual(c.execute('select count(*) from silver.ai_enrichment_gemini').fetchone()[0],0)
            self.assertFalse(g.ensure_ai_contract(c))
    def test_incomplete_or_testless_build_is_blocked(self):
        for result in [{'results':[]},{'results':self.result()['results'][:-1]}]:
            with self.assertRaises(RuntimeError):g.validate_build(result)

if __name__=='__main__':unittest.main()
