"""Bronze integration checks using synthetic sources and temporary databases."""
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import duckdb
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import bronze

class BronzeIngestionTests(unittest.TestCase):
    def test_repeat_load_and_failure_preserves_previous_bronze(self):
        grid = pd.DataFrame([['Date','Department','Rating','Comments'],
                             ['01/10/2025','Service',4,'Helpful team'],['','','','']])
        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / 'test.duckdb')
            sources = [('Parramatta_test.xlsx','Sheet1',grid,'synthetic-hash')]
            with patch.object(bronze,'read_sources',return_value=iter(sources)):
                bronze.main(db)
            with patch.object(bronze,'read_sources',return_value=iter(sources)):
                bronze.main(db)
            with duckdb.connect(db) as con:
                self.assertEqual(con.execute('select count(*) from bronze.raw_responses').fetchone()[0],1)
                self.assertEqual(con.execute('select count(*) from ops.row_dispositions').fetchone()[0],3)
            bad = [('Unknown.xlsx','Sheet1',pd.DataFrame([['unexpected layout']]),'bad-hash')]
            with patch.object(bronze,'read_sources',return_value=iter(bad)):
                with self.assertRaises(ValueError):
                    bronze.main(db)
            with duckdb.connect(db) as con:
                self.assertEqual(con.execute('select count(*) from bronze.raw_responses').fetchone()[0],1)
                self.assertEqual(con.execute('select source_file from ops.file_registry').fetchone()[0],'Parramatta_test.xlsx')

if __name__ == '__main__':
    unittest.main()
