"""Retry only failed rows from a completed run, preserving successful checkpoints."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import sys
import time
import duckdb
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT
import gemini_enrichment as g

def main():
    cfg=g.settings();key=g.api_key();started=time.perf_counter()
    with duckdb.connect(str(ROOT/'data'/'bronze_review.duckdb')) as c:
        rows=c.execute("""select f.response_id,f.comment from silver.feedback f
            join silver.ai_enrichment_gemini a using(response_id)
            where a.status='error' and f.in_analysis order by f.response_id""").df()
        for row in rows.itertuples():
            cachekey=g.fingerprint(row.comment,cfg);reserve=g.reservation(row.comment,cfg)
            spend=c.execute('select coalesce(sum(accounted_usd),0) from ops.gemini_spend').fetchone()[0]
            if spend+reserve>5:raise RuntimeError('Budget reached before retry')
            stamp=datetime.now(timezone.utc).isoformat();attempt=hashlib.sha256((cachekey+stamp).encode()).hexdigest()
            c.execute('insert into ops.gemini_spend values (?,?,?,?,?)',[attempt,cachekey,reserve,'reserved',stamp])
            result=g.infer(row.comment,cfg,key)
            c.execute('BEGIN TRANSACTION')
            c.execute('update ops.gemini_spend set accounted_usd=?,status=? where attempt_id=?',[result['cost_usd_accounted'],result['status'],attempt])
            if result['status']=='success':c.execute('insert or replace into ops.gemini_cache values (?,?,?)',[cachekey,json.dumps(result),stamp])
            g.persist_result(c,row,cachekey,result,cfg);c.execute('COMMIT')
            print('Retried failed response:',result['status'],flush=True)
        count,success,errors,names,review=c.execute("""select count(*),count(*) filter(where status='success'),
            count(*) filter(where status='error'),count(*) filter(where has_unmasked_name),
            count(*) filter(where needs_review) from silver.ai_enrichment_gemini""").fetchone()
        spend=c.execute('select sum(accounted_usd) from ops.gemini_spend').fetchone()[0]
    p=ROOT/'outputs'/'gemini_run.json';report=json.loads(p.read_text(encoding='utf-8'))
    report.update(successful=success,errors=errors,new_name_flags=names,needs_review=review,
                  cumulative_cost_usd_accounted=round(spend,6),retried_failed_comments=len(rows),
                  retry_elapsed_seconds=round(time.perf_counter()-started,2),
                  status='run_complete' if errors==0 else 'run_complete_with_errors')
    p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
