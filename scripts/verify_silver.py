"""Verify Silver against the CSV baseline without printing comment text."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys
import duckdb
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT
import silver

def verify():
    database=ROOT/'data'/'bronze_review.duckdb'
    def read():
        with duckdb.connect(str(database),read_only=True) as c:
            return c.execute('select * from silver.feedback order by response_id').df()
    silver.main(str(database)); first=read()
    silver.main(str(database)); second=read()
    pd.testing.assert_frame_equal(first,second)
    baseline=pd.read_csv(ROOT/'data'/'feedback_validated.csv',parse_dates=['date'])
    keys=['source_file','source_sheet','source_row']
    merged=second.merge(baseline,on=keys,how='outer',suffixes=('_silver','_baseline'),indicator=True,validate='one_to_one')
    assert not merged['_merge'].eq('right_only').any(), 'Baseline responses missing from Silver'
    both=merged.loc[merged['_merge'].eq('both')]
    fields=['date','department','dealer_code','rating_1to5','in_analysis','negative']
    for field in fields:
        a,b=both[field+'_silver'],both[field+'_baseline']
        assert (a.eq(b)|(a.isna()&b.isna())).all(), f'Baseline disagreement: {field}'
    extra=merged.loc[merged['_merge'].eq('left_only')]
    assert not extra.in_analysis_silver.any(), 'Additional analysis responses require review'
    assert not second.loc[second.rating_1to5.isna(),'negative'].notna().any()
    with duckdb.connect(str(database),read_only=True) as c:
        bronze_rows=c.execute('select count(*) from bronze.raw_responses').fetchone()[0]
        decisions=c.execute('select * from silver.row_decisions').df()
        assert len(decisions)==bronze_rows
        assert not decisions.duplicated(keys).any()
        assert int(decisions.in_analysis.sum())==int(second.in_analysis.sum())
        for file,digest in c.execute('select distinct source_file,sha256 from ops.file_registry').fetchall():
            assert hashlib.sha256((ROOT/'feedback'/file).read_bytes()).hexdigest()==digest
    report={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'status':'passed',
            'bronze_rows':bronze_rows,'non_response_rows':int(decisions.record_type.eq('non_response').sum()),
            'silver_feedback_rows':len(second),'analysis_rows':int(second.in_analysis.sum()),
            'excluded_feedback_rows':int((~second.in_analysis).sum()),
            'baseline_rows_matched':len(both),'baseline_fields_compared':fields,
            'additional_excluded_rows':[{'source_file':r.source_file,'source_sheet':r.source_sheet,'source_row':int(r.source_row),
                                        'reason':'test_or_junk_row'} for r in extra.itertuples()],
            'repeat_load_identical':True,'source_hashes_unchanged':True,'missing_rating_negative_is_null':True,
            'ollama_enrichment':'not_run'}
    (ROOT/'outputs'/'silver_verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':verify()
