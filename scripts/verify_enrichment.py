"""Verify the stored local pilot/cache without rerunning a changed prompt or inference."""
import hashlib
import json
import sys
from pathlib import Path
import duckdb
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT

def main():
    with duckdb.connect(str(ROOT/'data'/'bronze_review.duckdb'),read_only=True) as c:
        rows=c.execute("""select a.response_id,a.content_sha256,a.status,a.prompt_version,c.result_json,f.comment
          from silver.ai_enrichment a join ops.ai_cache c using(request_key)
          join silver.feedback f using(response_id)""").fetchall()
        assert len(rows)==20 and len({r[0] for r in rows})==20
        for rid,digest,status,version,raw,comment in rows:
            cached=json.loads(raw)
            assert status=='success' and cached['status']=='success'
            assert digest==hashlib.sha256(comment.encode()).hexdigest()
    summary={'status':'stored_pilot_and_cache_verified','cached_pilot_rows':len(rows),
             'prompt_versions':sorted({r[3] for r in rows}),'new_inference_calls':0,
             'scope':'Read-only verification of stored results; current prompt may differ from the historical pilot',
             'human_evaluation':'pending'}
    (ROOT/'outputs'/'enrichment_verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
