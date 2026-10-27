"""Run Bronze twice and save aggregate verification evidence without comment text."""
from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone
import duckdb
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common import ROOT
import bronze

def verify():
    database = ROOT / 'data' / 'bronze_review.duckdb'
    database.parent.mkdir(exist_ok=True)
    paths = sorted(p for p in (ROOT / 'feedback').iterdir() if p.suffix.lower() in {'.xlsx','.csv'} and not p.name.startswith('~$'))
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    def snapshot():
        with duckdb.connect(str(database), read_only=True) as con:
            rows = con.execute('select * exclude (loaded_at) from bronze.raw_responses order by source_file, source_sheet, source_row').fetchall()
            registry = con.execute('select source_file, sha256, reconciled, physical_rows from ops.file_registry').fetchall()
            assert all(r[2] and before[r[0]] == r[1] for r in registry)
            assert con.execute('select count(*) from ops.row_dispositions').fetchone()[0] == sum(r[3] for r in registry)
            assert con.execute('select count(*) from (select source_file,source_sheet,source_row,count(*) n from ops.row_dispositions group by all having n <> 1)').fetchone()[0] == 0
            return rows
    bronze.main(str(database)); first = snapshot()
    bronze.main(str(database)); second = snapshot()
    assert first == second, 'Repeated load changed row content or duplicated rows'
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with duckdb.connect(str(database), read_only=True) as con:
        dispositions = dict(con.execute('select disposition, count(*) from ops.row_dispositions group by disposition').fetchall())
        audit = con.execute('select * from ops.comment_masking_audit').df().to_dict(orient='records')
        # Convert pandas missing count values to JSON null.
        for item in audit:
            for key in ('comments_affected','replacement_count'):
                value = item[key]
                item[key] = None if value != value else int(value)
        columns = [r[0] for r in con.execute('describe bronze.raw_responses').fetchall()]
        assert not set(columns) & {'customer','customer_name','staff','phone','email','rego','name'}
        report = {'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'status':'passed',
                  'source_files':len(paths), 'file_sheet_sources':con.execute('select count(*) from ops.file_registry').fetchone()[0],
                  'landed_rows':len(second), 'physical_rows':sum(dispositions.values()), 'row_dispositions':dispositions,
                  'repeat_load_identical_excluding_loaded_at':True, 'source_hashes_unchanged':True,
                  'structured_identity_columns_absent':True, 'masking_audit':audit,
                  'ollama_name_audit':'not_run', 'residual_privacy_risk':'unmeasured',
                  'database':'data/bronze_review.duckdb'}
    (ROOT / 'outputs' / 'bronze_verification.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    verify()
