"""Verify rebuilt literal proposals and export a fresh compatible review snapshot."""
import hashlib
import json
import re
from pathlib import Path
import duckdb
ROOT=Path(__file__).resolve().parents[1]

def verify():
    database=ROOT/'data'/'bronze_review.duckdb'
    with duckdb.connect(str(database),read_only=True) as c:
        expected=c.execute('select count(*) from silver.ai_enrichment_gemini where has_unmasked_name').fetchone()[0]
        rows=c.execute("""select f.comment,n.* from silver.feedback f
             join silver.name_redaction_review n using(response_id)""").df()
        assert len(rows)==expected and rows.response_id.is_unique
        assert rows.content_sha256.eq(rows.comment.map(lambda t:hashlib.sha256(t.encode()).hexdigest())).all()
        assert rows.prompt_version.eq('name-literal-repair-v2').all()
        valid=rows.proposal_status.eq('literal_match_pending_review')
        assert rows.loc[valid,'proposed_comment'].notna().all()
        assert rows.loc[~valid,'proposed_comment'].isna().all()
        broken=re.compile(r'\w\[(?:STAFF|CUSTOMER|PERSON)\]|\[(?:STAFF|CUSTOMER|PERSON)\]\w')
        assert not any(broken.search(t) for t in rows.loc[valid,'proposed_comment'])
        assert c.execute('select count(*) from silver.ai_enrichment_gemini where proposed_comment is not null').fetchone()[0]==0
        assert c.execute('select count(*) from silver.ai_enrichment where proposed_comment is not null').fetchone()[0]==0
        assert c.execute("""select count(*) from silver.feedback s join bronze.raw_responses b
            using(source_file,source_sheet,source_row) where s.comment is distinct from b.comment""").fetchone()[0]==0
        stats=rows.proposal_status.value_counts().to_dict()
        spend=c.execute('select sum(accounted_usd) from ops.gemini_spend').fetchone()[0]
        assert spend<=5
        result={'status':'passed_mechanical_checks_human_review_pending','rebuilt_rows':len(rows),
                'proposal_status_counts':{k:int(v) for k,v in stats.items()},'model_offsets_accepted':False,
                'inserted_name_tags_inside_words':0,'old_primary_proposals_invalidated':True,
                'source_comments_unchanged':True,'cumulative_accounted_usd':round(spend,6),
                'semantic_name_role_and_completeness_accuracy':'not_established'}
    target=ROOT/'data'/'gemini_review_fixed.duckdb'
    if target.exists():
        with duckdb.connect(str(target),read_only=True) as snapshot:
            assert snapshot.execute('select count(*) from silver.name_redaction_review').fetchone()[0]==expected
    else:
        with duckdb.connect() as c:
            c.execute('ATTACH ? AS original (READ_ONLY)',[str(database)])
            c.execute("ATTACH ? AS viewer (STORAGE_VERSION 'v1.0.0')",[str(target)])
            c.execute('COPY FROM DATABASE original TO viewer')
            assert c.execute('select count(*) from viewer.silver.name_redaction_review').fetchone()[0]==expected
    (ROOT/'outputs'/'name_repair_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':verify()
