"""Score my human labels by component without filling missing labels or inventing gold."""
import argparse
from collections import Counter
import hashlib
import json
import duckdb
import pandas as pd
from common import ROOT
from enrichment import load_settings,SENTIMENTS


def evaluate(database,labels_path,provider='ollama',export_disagreements=False):
    if provider not in {'ollama','gemini'}:raise ValueError('Unknown provider')
    table='silver.ai_enrichment_gemini' if provider=='gemini' else 'silver.ai_enrichment'
    labels=pd.read_csv(labels_path,keep_default_na=False,dtype=str,encoding='utf-8-sig')
    fields=['human_sentiment','human_themes','human_has_unmasked_name']
    if not {'response_id','masked_comment',*fields}<=set(labels.columns):raise ValueError('Missing human-label columns')
    if labels.response_id.duplicated().any():raise ValueError('Duplicate review response IDs')
    present=labels[fields].apply(lambda c:c.str.strip().ne(''))
    complete=present.all(axis=1);any_label=present.any(axis=1)
    gold=labels.loc[any_label].copy()
    sent_n=int(present.human_sentiment.sum());theme_n=int(present.human_themes.sum());name_n=int(present.human_has_unmasked_name.sum())
    result={'provider':provider,'status':'awaiting_human_labels','sample_rows':len(labels),
        'rows_with_any_human_label':len(gold),'completed_human_labels':int(complete.sum()),
        'human_sentiment_labelled_rows':sent_n,'human_theme_labelled_rows':theme_n,'human_name_labelled_rows':name_n,
        'human_label_completion':float(complete.mean()) if len(labels) else 0,
        'all_reviewed_fields_exact_count':None,'all_reviewed_fields_exact_match_rate':None,
        'reviewed_fields':['overall_sentiment','theme_membership','remaining_name_flag'],
        'sentiment_accuracy':None,'theme_micro_precision':None,'theme_micro_recall':None,'theme_micro_f1':None,
        'theme_any_match_count':None,'theme_gold_themed_comments':None,'theme_any_match_rate_on_themed_comments':None,
        'per_theme':None,'theme_exact_match':None,'residual_name_false_negatives':None,
        'note':'Diagnostic sample with deliberate strata/known failures; unweighted metrics do not estimate population accuracy.'}
    if not gold.empty:
        allowed=set(load_settings()['themes'])
        def themes(raw):
            if not raw.strip():return None
            if raw.strip().lower()=='none':return set()
            found={t.strip() for t in raw.split('|') if t.strip()}
            if not found or not found<=allowed or len(found)>3:raise ValueError('Invalid human theme IDs (up to three, or none)')
            return found
        gold['gold_themes']=gold.human_themes.map(themes)
        if not gold.loc[gold.human_sentiment.ne(''),'human_sentiment'].isin(SENTIMENTS).all():raise ValueError('Invalid human sentiment label')
        flags=gold.human_has_unmasked_name.str.strip().str.lower()
        if not flags.isin(['','true','false']).all():raise ValueError('Human name flag must be true or false')
        gold['gold_name_flag']=flags.map({'true':True,'false':False})
        with duckdb.connect(str(database),read_only=True) as c:
            predicted=c.execute('select response_id,content_sha256,sentiment,themes_json,has_unmasked_name,status from '+table).df()
        merged=gold.merge(predicted,on='response_id',how='left',validate='one_to_one')
        if merged.status.isna().any():raise ValueError('Reviewed response has no model result')
        if not merged.masked_comment.map(lambda s:hashlib.sha256(s.encode()).hexdigest()).eq(merged.content_sha256).all():
            raise ValueError('Review text changed; restore the unchanged source comment')
        sent_right=name_right=tp=fp=fn=exact=whole=themed=overlap=0
        name_false_negative=name_false_positive=name_unassessed=0
        confusion=Counter();disagreements=[]
        per_theme={t:{'hits':0,'extra_predictions':0,'misses':0} for t in sorted(allowed)}
        for row in merged.itertuples():
            valid=row.status=='success';has_sent=bool(row.human_sentiment.strip())
            has_theme=row.gold_themes is not None;has_name=bool(row.human_has_unmasked_name.strip())
            sent_ok=valid and row.sentiment==row.human_sentiment
            name_assessed=valid and pd.notna(row.has_unmasked_name)
            name_ok=name_assessed and bool(row.has_unmasked_name)==bool(row.gold_name_flag)
            theme_ok=False
            pred={t['theme'] for t in json.loads(row.themes_json)} if valid else set()
            reasons=[]
            if has_sent:
                sent_right+=int(sent_ok);confusion[(row.human_sentiment,row.sentiment if valid else 'error')]+=1
                if not sent_ok:reasons.append('sentiment')
            if has_name:
                name_right+=int(name_ok)
                if not name_assessed:name_unassessed+=1
                else:
                    name_false_negative+=int(bool(row.gold_name_flag) and not bool(row.has_unmasked_name))
                    name_false_positive+=int(not bool(row.gold_name_flag) and bool(row.has_unmasked_name))
                if not name_ok:reasons.append('name_flag')
            if has_theme:
                actual=row.gold_themes
                tp+=len(pred&actual);fp+=len(pred-actual);fn+=len(actual-pred)
                theme_ok=valid and pred==actual;exact+=int(theme_ok)
                if actual:themed+=1;overlap+=int(bool(pred&actual))
                for theme in allowed:
                    if theme in pred and theme in actual:per_theme[theme]['hits']+=1
                    elif theme in pred:per_theme[theme]['extra_predictions']+=1
                    elif theme in actual:per_theme[theme]['misses']+=1
                if not theme_ok:reasons.append('themes')
            if has_sent and has_theme and has_name:whole+=int(sent_ok and theme_ok and name_ok)
            if reasons:
                disagreements.append({'response_id':row.response_id,'masked_comment':row.masked_comment,
                    'disagreement_fields':'|'.join(reasons),'human_sentiment':row.human_sentiment,'model_sentiment':row.sentiment,
                    'human_themes':('|'.join(sorted(row.gold_themes)) or 'none') if has_theme else 'mapping_pending',
                    'model_themes':'|'.join(sorted(pred)) or 'none',
                    'missed_themes':'|'.join(sorted(row.gold_themes-pred)) if has_theme else '',
                    'extra_themes':'|'.join(sorted(pred-row.gold_themes)) if has_theme else '',
                    'human_has_unmasked_name':row.human_has_unmasked_name,'model_has_unmasked_name':row.has_unmasked_name,
                    'model_status':row.status})
        for counts in per_theme.values():
            hit,extra,miss=counts['hits'],counts['extra_predictions'],counts['misses']
            counts.update(support=hit+miss,precision=hit/(hit+extra) if hit+extra else None,
                          recall=hit/(hit+miss) if hit+miss else None,
                          f1=2*hit/(2*hit+extra+miss) if 2*hit+extra+miss else None)
        if complete.all() or export_disagreements:
            destination=ROOT/'data';destination.mkdir(exist_ok=True)
            columns=['response_id','masked_comment','disagreement_fields','human_sentiment','model_sentiment','human_themes',
                     'model_themes','missed_themes','extra_themes','human_has_unmasked_name','model_has_unmasked_name','model_status']
            pd.DataFrame(disagreements,columns=columns).to_csv(destination/(provider+'_disagreements.csv'),index=False,encoding='utf-8')
        mapping_assisted=('theme_mapping_status' in gold.columns and gold.theme_mapping_status.str.contains('AI-assisted',regex=False).any())
        result.update(status='evaluated' if complete.all() else 'partially_evaluated',
            successful_model_results=int(merged.status.eq('success').sum()),classification_coverage=float(merged.status.eq('success').mean()),
            sentiment_correct_count=sent_right,sentiment_accuracy=sent_right/sent_n if sent_n else None,
            theme_micro_precision=tp/(tp+fp) if tp+fp else None,theme_micro_recall=tp/(tp+fn) if tp+fn else None,
            theme_micro_f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            theme_any_match_count=overlap,theme_gold_themed_comments=themed,
            theme_any_match_rate_on_themed_comments=overlap/themed if themed else None,
            theme_exact_match=exact/theme_n if theme_n else None,per_theme=per_theme,
            theme_mapping_status='provisional_AI_assisted_crosswalk' if mapping_assisted else 'human_canonical_labels',
            all_reviewed_fields_exact_count=whole,
            all_reviewed_fields_exact_match_rate=whole/int(complete.sum()) if complete.sum() else None,
            name_flag_correct_count=name_right,name_flag_accuracy=name_right/name_n if name_n else None,
            residual_name_false_negatives=name_false_negative,residual_name_false_positives=name_false_positive,
            residual_name_unassessed=name_unassessed,
            sentiment_confusion=[{'human_sentiment':a,'sentiment':b,'count':n} for (a,b),n in sorted(confusion.items())])
    output='gemini_evaluation.json' if provider=='gemini' else 'enrichment_evaluation.json'
    (ROOT/'outputs'/output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',default=str(ROOT/'data'/'bronze_review.duckdb'))
    p.add_argument('--labels');p.add_argument('--provider',choices=['ollama','gemini'],default='ollama')
    p.add_argument('--export-disagreements',action='store_true')
    a=p.parse_args();path=a.labels or str(ROOT/'data'/('gemini_review_sample.csv' if a.provider=='gemini' else 'ai_review_sample.csv'))
    evaluate(a.database,path,a.provider,a.export_disagreements)
