"""Prepare 50 fresh comments for independent applicant labels; never populate gold labels."""
from pathlib import Path
import hashlib
import json
import duckdb
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
SEED='kestrel-human-holdout-v1'

def prepare():
    target=ROOT/'data'/'gemini_review_50.csv'
    if target.exists():raise RuntimeError('Review file already exists; refusing to overwrite applicant work')
    with duckdb.connect(str(ROOT/'data'/'bronze_review.duckdb'),read_only=True) as c:
        source=c.execute("""select f.response_id,f.dealer_code,f.department,f.rating_1to5,f.comment,
            f.source_file,f.source_row,a.status from silver.feedback f
            join silver.ai_enrichment_gemini a using(response_id)
            where f.in_analysis and trim(f.comment)<>''""").df()
    previously_seen=set()
    for name in ['ai_review_sample.csv','gemini_review_sample.csv']:
        path=ROOT/'data'/name
        if path.exists():previously_seen.update(pd.read_csv(path,usecols=['response_id']).response_id)
    examples=(source.source_file.eq('Ballarat - Customer Satisfaction.xlsx') & source.source_row.isin([4,14,16,17,18,26,31,42,43,51]))
    previously_seen.update(source.loc[examples,'response_id'])
    frame=source.loc[~source.response_id.isin(previously_seen)].copy()
    frame['band']=frame.rating_1to5.map(lambda n:'missing' if pd.isna(n) else 'low' if n<=2 else 'mid' if n<4 else 'high')
    frame['order']=frame.response_id.map(lambda r:hashlib.sha256((SEED+r).encode()).hexdigest())
    frame=frame.sort_values('order');chosen=[]
    def take(mask,number):
        available=frame.loc[mask & ~frame.response_id.isin(chosen)]
        chosen.extend(available.head(min(number,50-len(chosen))).response_id.tolist())
    take(frame.status.eq('error'),2)
    take(frame.band.eq('missing'),6)
    for dealer in sorted(frame.dealer_code.unique()):
        selected=frame.loc[frame.response_id.isin(chosen)]
        if dealer not in set(selected.dealer_code):take(frame.dealer_code.eq(dealer),1)
    for band,quota in [('low',14),('mid',10),('high',18)]:
        current=int(frame.loc[frame.response_id.isin(chosen),'band'].eq(band).sum())
        take(frame.band.eq(band),max(0,quota-current))
    take(pd.Series(True,index=frame.index),50-len(chosen))
    sample=frame.set_index('response_id').loc[chosen].reset_index().sort_values('order')
    assert len(sample)==50 and sample.response_id.is_unique
    assert not set(sample.response_id)&previously_seen
    review=sample[['response_id','comment']].rename(columns={'comment':'masked_comment'})
    for column in ['human_sentiment','human_themes','human_has_unmasked_name','review_notes']:review[column]=''
    review.to_csv(target,index=False)
    report={'status':'ready_for_independent_human_labels','sample_rows':50,'seed':SEED,
            'dealerships':int(sample.dealer_code.nunique()),'departments':sorted(sample.department.unique()),
            'rating_bands':{k:int(v) for k,v in sample.band.value_counts().items()},
            'previously_seen_sample_rows':0,'known_failed_model_cases_included':int(sample.status.eq('error').sum()),
            'predictions_hidden':True,'gold_labels_authored_by_ai':False,
            'sampling':'Deterministic diagnostic spread across dealers, departments and rating bands; includes known failures. Not a population accuracy estimate.'}
    (ROOT/'outputs'/'human_review_50_manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':prepare()
