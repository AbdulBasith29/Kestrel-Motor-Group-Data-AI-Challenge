"""Verify a finished Gemini run; --wait waits for this finite run to finish first."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import duckdb
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT
from enrichment import SENTIMENTS,POLARITIES,load_settings

def verify(wait_for_run=False,allow_quarantined_errors=False):
    report_path=ROOT/'outputs'/'gemini_run.json'
    deadline=time.monotonic()+5400
    while not report_path.exists():
        if not wait_for_run or time.monotonic()>deadline:raise RuntimeError('Full-run report is not available yet')
        time.sleep(5)
    report=json.loads(report_path.read_text(encoding='utf-8'))
    database=ROOT/'data'/'bronze_review.duckdb'
    # A short lock overlap is possible while the writer exits after saving its report.
    for attempt in range(12):
        try:con=duckdb.connect(str(database),read_only=True);break
        except duckdb.IOException:
            if attempt==11:raise
            time.sleep(5)
    with con:
        feedback=con.execute('select * from silver.feedback').df()
        results=con.execute('select * from silver.ai_enrichment_gemini').df()
        holdouts=con.execute('select * from ops.gemini_holdouts').df()
        eligible=feedback.loc[feedback.in_analysis & feedback.comment.str.strip().ne('')]
        assert results.response_id.is_unique
        joined=results.merge(eligible[['response_id','comment']],on='response_id',validate='one_to_one')
        assert len(joined)==len(results)
        assert joined.content_sha256.eq(joined.comment.map(lambda t:hashlib.sha256(t.encode()).hexdigest())).all()
        assert set(results.response_id).isdisjoint(set(holdouts.response_id))
        assert set(results.response_id)|set(holdouts.response_id)==set(eligible.response_id)
        assert report['all_eligible_processed']
        assert results.status.isin(['success','error']).all()
        failed=results.loc[results.status.eq('error')]
        valid=results.loc[results.status.eq('success')]
        assert len(failed)==report['errors'] and len(valid)==report['successful']
        if not allow_quarantined_errors:assert failed.empty
        assert failed.sentiment.isna().all(), 'Failed responses must not supply analytical labels'
        assert results.human_review_status.eq('pending').all()
        assert valid.sentiment.isin(SENTIMENTS).all()
        allowed=set(load_settings()['themes'])
        for raw in valid.themes_json:
            themes=json.loads(raw)
            assert len(themes)<=3 and len({t['theme'] for t in themes})==len(themes)
            assert all(t['theme'] in allowed and t['polarity'] in POLARITIES for t in themes)
        # Model proposals do not replace the deterministic Silver comments.
        assert con.execute("""select count(*) from silver.feedback s join bronze.raw_responses b
            using(source_file,source_sheet,source_row) where s.comment is distinct from b.comment""").fetchone()[0]==0
        baseline=pd.read_csv(ROOT/'data'/'feedback_validated.csv',parse_dates=['date'])
        keys=['source_file','source_sheet','source_row']
        paired=feedback.merge(baseline,on=keys,suffixes=('_silver','_baseline'),validate='one_to_one')
        assert len(paired)==len(baseline)
        for field in ['date','department','dealer_code','rating_1to5','negative','in_analysis']:
            a,b=paired[field+'_silver'],paired[field+'_baseline']
            assert (a.eq(b)|(a.isna()&b.isna())).all()
        for file,digest in con.execute('select distinct source_file,sha256 from ops.file_registry').fetchall():
            assert hashlib.sha256((ROOT/'feedback'/file).read_bytes()).hexdigest()==digest
        spend=float(con.execute('select coalesce(sum(accounted_usd),0) from ops.gemini_spend').fetchone()[0])
        assert spend<=report['budget_usd']+1e-8
        assert con.execute("select count(*) from ops.gemini_spend where status='reserved'").fetchone()[0]==0
        outcome={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'status':'passed_with_quarantined_ai_errors' if len(failed) else 'passed',
                 'accepted_nonblank_comments':len(eligible),'successful_enrichments':len(valid),'quarantined_ai_errors':len(failed),
                 'held_out_comments':len(holdouts),'remaining_name_flags':int(results.has_unmasked_name.sum()),
                 'needs_review':int(results.needs_review.sum()),'accounted_usd':round(spend,6),
                 'source_hashes_unchanged':True,'silver_scores_and_analysis_membership_match_baseline':True,
                 'silver_comments_equal_bronze_masked_comments':True,'coverage_reconciled':True,
                 'human_evaluation':'pending'}
    viewer=ROOT/'data'/'gemini_viewer.duckdb'
    if not viewer.exists():
        with duckdb.connect() as copy:
            copy.execute('ATTACH ? AS original (READ_ONLY)',[str(database)])
            copy.execute("ATTACH ? AS viewer (STORAGE_VERSION 'v1.0.0')",[str(viewer)])
            copy.execute('COPY FROM DATABASE original TO viewer')
            assert copy.execute('select count(*) from viewer.silver.ai_enrichment_gemini').fetchone()[0]==len(results)
    (ROOT/'outputs'/'gemini_verification.json').write_text(json.dumps(outcome,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(outcome,indent=2),flush=True)
    return outcome

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wait',action='store_true')
    p.add_argument('--allow-quarantined-errors',action='store_true')
    args=p.parse_args();verify(args.wait,args.allow_quarantined_errors)
