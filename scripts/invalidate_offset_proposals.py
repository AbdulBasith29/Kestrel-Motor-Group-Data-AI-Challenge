"""Invalidate untrusted offset-v1 proposals; preserve labels, originals and a restricted audit."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import sys
import duckdb
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT


def invalidate(path):
    counts={}
    with duckdb.connect(str(path)) as c:
        c.execute('CREATE SCHEMA IF NOT EXISTS ops')
        c.execute("""CREATE TABLE IF NOT EXISTS ops.invalidated_name_proposals (
            provider VARCHAR,response_id VARCHAR,old_proposed_comment VARCHAR,
            content_sha256 VARCHAR,reason VARCHAR,invalidated_at VARCHAR)""")
        tables={r[0] for r in c.execute("select table_schema||'.'||table_name from information_schema.tables").fetchall()}
        for table,provider in [('silver.ai_enrichment_gemini','gemini'),('silver.ai_enrichment','ollama')]:
            if table not in tables:continue
            before=c.execute(f'SELECT response_id,sentiment,themes_json FROM {table} ORDER BY response_id').fetchall()
            n=c.execute(f'SELECT count(*) FROM {table} WHERE proposed_comment IS NOT NULL').fetchone()[0]
            c.execute('BEGIN TRANSACTION')
            c.execute(f"""INSERT INTO ops.invalidated_name_proposals SELECT ?,response_id,proposed_comment,
                content_sha256,'model_offset_v1_semantically_wrong',? FROM {table} WHERE proposed_comment IS NOT NULL""",
                [provider,datetime.now(timezone.utc).isoformat()])
            c.execute(f'UPDATE {table} SET proposed_comment=NULL,needs_review=true WHERE proposed_comment IS NOT NULL')
            c.execute('COMMIT')
            assert before==c.execute(f'SELECT response_id,sentiment,themes_json FROM {table} ORDER BY response_id').fetchall()
            counts[provider]=n
        for table in ['ops.gemini_cache','ops.ai_cache']:
            if table not in tables:continue
            for key,raw in c.execute(f'SELECT request_key,result_json FROM {table}').fetchall():
                result=json.loads(raw)
                if result.get('proposed_comment') is not None:
                    result.update(proposed_comment=None,needs_review=True,proposal_status='invalidated_offset_v1')
                    c.execute(f'UPDATE {table} SET result_json=? WHERE request_key=?',[json.dumps(result),key])
    return counts

if __name__=='__main__':
    evidence={}
    for filename in ['bronze_review.duckdb','gemini_viewer.duckdb','enrichment_viewer.duckdb','silver_viewer.duckdb','bronze_viewer.duckdb']:
        path=ROOT/'data'/filename
        if path.exists():
            try:evidence[filename]=invalidate(path)
            except duckdb.IOException:evidence[filename]={'status':'locked_old_snapshot_do_not_use'}
    report={'status':'invalidated','reason':'Bounds checks did not establish that model offsets selected the intended name',
            'databases':evidence,'sentiment_theme_labels_preserved':True,
            'source_comments_modified':False,'old_primary_proposals_retained_in_restricted_audit':True,
            'locked_legacy_snapshots_must_be_detached':[name for name,item in evidence.items() if item.get('status')=='locked_old_snapshot_do_not_use']}
    (ROOT/'outputs'/'name_proposal_invalidation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
