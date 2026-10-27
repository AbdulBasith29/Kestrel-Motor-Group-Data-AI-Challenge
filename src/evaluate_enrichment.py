"""Compare local model outputs against applicant-authored labels; never invent gold labels."""
import argparse
import hashlib
import json
from pathlib import Path
import duckdb
import pandas as pd
from common import ROOT
from enrichment import load_settings, SENTIMENTS


def evaluate(database,labels_path,provider="ollama"):
    if provider not in {"ollama","gemini"}:raise ValueError("Unknown provider")
    table = "silver.ai_enrichment_gemini" if provider == "gemini" else "silver.ai_enrichment"
    labels=pd.read_csv(labels_path,keep_default_na=False,dtype=str)
    required={'response_id','masked_comment','human_sentiment','human_themes','human_has_unmasked_name'}
    if not required.issubset(labels.columns):raise ValueError('Missing human-label columns')
    if labels.response_id.duplicated().any():raise ValueError('Duplicate review response IDs')
    complete=labels[['human_sentiment','human_themes','human_has_unmasked_name']].apply(lambda c:c.str.strip().ne('')).all(axis=1)
    gold=labels.loc[complete].copy()
    result={'provider':provider,'status':'awaiting_human_labels','sample_rows':len(labels),'completed_human_labels':len(gold),
            'human_label_completion':len(gold)/len(labels) if len(labels) else 0,
            'all_reviewed_fields_exact_count':None,'all_reviewed_fields_exact_match_rate':None,
            'reviewed_fields':['overall_sentiment','theme_membership','remaining_name_flag'],
            'sentiment_accuracy':None,'theme_micro_precision':None,'theme_micro_recall':None,
            'theme_micro_f1':None,'theme_exact_match':None,'residual_name_false_negatives':None,
            'note':'Pilot is deliberately stratified; these metrics do not estimate population accuracy.'}
    if not gold.empty:
        allowed=set(load_settings()['themes'])
        def themes(value):
            if value.strip().lower()=='none':return set()
            found={t.strip() for t in value.split('|') if t.strip()}
            if not found or not found<=allowed:raise ValueError('Invalid human theme label; use theme IDs separated by |, or none')
            return found
        gold['gold_themes']=gold.human_themes.map(themes)
        if not gold.human_sentiment.isin(SENTIMENTS).all():raise ValueError('Invalid human sentiment label')
        flags=gold.human_has_unmasked_name.str.strip().str.lower()
        if not flags.isin(['true','false']).all():raise ValueError('Human name flag must be true or false')
        gold['gold_name_flag']=flags.eq('true')
        with duckdb.connect(str(database),read_only=True) as c:
            predictions=c.execute('select response_id,content_sha256,sentiment,themes_json,has_unmasked_name,status from '+table).df()
        merged=gold.merge(predictions,on='response_id',how='left',validate='one_to_one')
        if merged.status.isna().any():raise ValueError('Reviewed response has no model result')
        expected_hash=merged.masked_comment.map(lambda text:hashlib.sha256(text.encode()).hexdigest())
        if not expected_hash.eq(merged.content_sha256).all():raise ValueError('Review text changed; regenerate the sample before evaluating')
        valid=merged.status.eq('success')
        right=merged.sentiment.eq(merged.human_sentiment)&valid
        tp=fp=fn=exact=0
        whole_match=0
        for row in merged.itertuples():
            pred={t['theme'] for t in json.loads(row.themes_json)} if row.status=='success' else set()
            tp+=len(pred&row.gold_themes);fp+=len(pred-row.gold_themes);fn+=len(row.gold_themes-pred)
            theme_match=row.status=='success' and pred==row.gold_themes
            exact+=int(theme_match)
            name_match=pd.notna(row.has_unmasked_name) and bool(row.has_unmasked_name)==row.gold_name_flag
            whole_match+=int(theme_match and row.sentiment==row.human_sentiment and name_match)
        precision=tp/(tp+fp) if tp+fp else None
        recall=tp/(tp+fn) if tp+fn else None
        f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None
        name_valid=valid&merged.has_unmasked_name.notna()
        false_negative=int((name_valid&merged.gold_name_flag&merged.has_unmasked_name.eq(False)).sum())
        false_positive=int((name_valid&~merged.gold_name_flag&merged.has_unmasked_name.eq(True)).sum())
        result.update(status='evaluated' if complete.all() else 'partially_evaluated',
                      successful_model_results=int(valid.sum()),classification_coverage=float(valid.mean()),
                      all_reviewed_fields_exact_count=whole_match,all_reviewed_fields_exact_match_rate=whole_match/len(merged),
                      sentiment_accuracy=float(right.mean()),theme_micro_precision=precision,
                      theme_micro_recall=recall,theme_micro_f1=f1,theme_exact_match=exact/len(merged),
                      residual_name_false_negatives=false_negative,residual_name_false_positives=false_positive,
                      residual_name_unassessed=int((~name_valid).sum()),
                      sentiment_confusion=merged.groupby(['human_sentiment','sentiment'],dropna=False).size().reset_index(name='count').fillna('error').to_dict(orient='records'))
    (ROOT/'outputs'/('gemini_evaluation.json' if provider == 'gemini' else 'enrichment_evaluation.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',default=str(ROOT/'data'/'bronze_review.duckdb'))
    p.add_argument('--labels')
    p.add_argument('--provider',choices=['ollama','gemini'],default='ollama')
    a=p.parse_args()
    label_path=a.labels or str(ROOT/'data'/('gemini_review_sample.csv' if a.provider=='gemini' else 'ai_review_sample.csv'))
    evaluate(a.database,label_path,a.provider)
