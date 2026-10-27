"""Gemini enrichment with isolated results, bounded spend and secret-free logs.

First test: python src/gemini_enrichment.py --synthetic
Pilot: python src/gemini_enrichment.py --limit 20
Requires GEMINI_API_KEY in the environment or project .env (never printed).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request,build_opener,ProxyHandler
import duckdb
import pandas as pd
import yaml
from common import ROOT
import enrichment as shared
from privacy import EMAIL, PHONE, LABELLED_PLATE, BARE_PLATE

class ProviderError(Exception):
    def __init__(self,code):self.code=code;super().__init__(code)

def settings():
    cfg=shared.load_settings()
    cfg.update(yaml.safe_load((ROOT/'config'/'gemini.yml').read_text(encoding='utf-8')))
    if cfg['model']!='gemini-3.5-flash-lite':
        raise ValueError('Update and review pricing before changing the Gemini model')
    return cfg

def api_key():
    value=os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not value:
        path=ROOT/'.env'
        if path.exists():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                name,sep,text=line.partition('=')
                if sep and name.strip()=='GEMINI_API_KEY':value=text.strip().strip('"').strip("'")
    if not value or value.startswith(('your_','REPLACE','<')):
        raise ProviderError('missing_api_key')
    return value

def request_body(comment,cfg):
    return {'systemInstruction':{'parts':[{'text':shared.system_prompt(cfg)}]},
            'contents':[{'role':'user','parts':[{'text':json.dumps({'feedback':comment},ensure_ascii=False)}]}],
            'generationConfig':{'temperature':0,'maxOutputTokens':cfg['max_output_tokens'],
                'thinkingConfig':{'thinkingLevel':cfg['thinking_level']},
                'responseFormat':{'text':{'mimeType':'APPLICATION_JSON','schema':shared.schema(cfg)}}}}

def call(body,cfg,key):
    url='https://generativelanguage.googleapis.com/v1beta/models/'+cfg['model']+':generateContent'
    req=Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','x-goog-api-key':key})
    try:
        # No key in URLs/logs, environment proxies or redirects.
        with build_opener(ProxyHandler({}),shared.NoRedirect()).open(req,timeout=120) as response:
            return json.load(response)
    except HTTPError as error:
        # Do not log Google's response body: it can echo content or credentials.
        raise ProviderError('http_'+str(error.code)) from None
    except (URLError,TimeoutError,OSError):
        raise ProviderError('connection_error') from None
    except ValueError:
        raise ProviderError('invalid_response_or_redirect') from None

def token_cost(prompt,output,cfg):
    return (prompt*cfg['input_usd_per_million']+output*cfg['output_usd_per_million'])/1_000_000

def reservation(comment,cfg):
    # UTF-8 bytes plus overhead deliberately overestimates ordinary English input tokens.
    input_upper=len(json.dumps(request_body(comment,cfg),ensure_ascii=False).encode())+1024
    return token_cost(input_upper,cfg['max_output_tokens'],cfg)*cfg['max_attempts']

def fingerprint(comment,cfg):
    return hashlib.sha256(json.dumps({'provider':'gemini','model':cfg['model'],
        'prompt_version':cfg['prompt_version'],'request':request_body(comment,cfg)},sort_keys=True).encode()).hexdigest()

def infer(comment,cfg,key):
    started=time.perf_counter();cost=0;tokens_in=tokens_out=0
    per_attempt=reservation(comment,cfg)/cfg['max_attempts']
    for attempt in range(1,cfg['max_attempts']+1):
        try:
            response=call(request_body(comment,cfg),cfg,key)
        except ProviderError as error:
            # Conservatively retain a reservation for requests whose usage is unknown.
            cost+=per_attempt
            if error.code not in {'http_429','http_500','http_502','http_503','http_504','connection_error'}:
                return {'status':'error','error_code':error.code,'attempts':attempt,'cost_usd_accounted':cost,
                        'latency_seconds':time.perf_counter()-started}
            if attempt<cfg['max_attempts']:time.sleep(min(2**attempt,8))
            continue
        usage=response.get('usageMetadata',{})
        billed_in=usage.get('promptTokenCount')
        billed_out=usage.get('candidatesTokenCount',0)+usage.get('thoughtsTokenCount',0)
        cost+=token_cost(billed_in,billed_out,cfg) if billed_in is not None else per_attempt
        tokens_in+=billed_in or 0;tokens_out+=billed_out
        try:
            candidates=response.get('candidates',[])
            if len(candidates)!=1 or candidates[0].get('finishReason')!='STOP':
                raise ValueError('Incomplete or blocked output')
            text=''.join(p.get('text','') for p in candidates[0]['content']['parts'] if not p.get('thought'))
            result=shared.validate_result(comment,json.loads(text),cfg)
            return {k:v for k,v in {**result,'status':'success','error_code':None,
                    'model_version':response.get('modelVersion',cfg['model']),
                    'input_tokens':tokens_in,'output_tokens_including_thinking':tokens_out,
                    'cost_usd_accounted':cost,'attempts':attempt,
                    'latency_seconds':time.perf_counter()-started}.items() if k not in {'name_spans','name_mentions'}}
        except (ValueError,KeyError,TypeError):
            continue
    return {'status':'error','error_code':'request_or_contract_error','attempts':cfg['max_attempts'],
            'input_tokens':tokens_in,'output_tokens_including_thinking':tokens_out,
            'cost_usd_accounted':cost,'latency_seconds':time.perf_counter()-started}

def initialise(con):
    con.execute('CREATE SCHEMA IF NOT EXISTS ops');con.execute('CREATE SCHEMA IF NOT EXISTS silver')
    con.execute("""CREATE TABLE IF NOT EXISTS ops.gemini_cache (
        request_key VARCHAR PRIMARY KEY, result_json VARCHAR, created_at VARCHAR)""")
    con.execute("""CREATE TABLE IF NOT EXISTS ops.gemini_spend (
        attempt_id VARCHAR PRIMARY KEY, request_key VARCHAR, accounted_usd DOUBLE, status VARCHAR, created_at VARCHAR)""")
    con.execute("""CREATE TABLE IF NOT EXISTS silver.ai_enrichment_gemini (
        response_id VARCHAR PRIMARY KEY, request_key VARCHAR, content_sha256 VARCHAR, model VARCHAR,
        prompt_version VARCHAR, sentiment VARCHAR, themes_json VARCHAR, has_unmasked_name BOOLEAN,
        proposed_comment VARCHAR, needs_review BOOLEAN, status VARCHAR, error_code VARCHAR,
        model_version VARCHAR, input_tokens BIGINT, output_tokens BIGINT, cost_usd_accounted DOUBLE,
        latency_seconds DOUBLE, created_at VARCHAR, human_review_status VARCHAR)""")

def privacy_checked_source(con,all_rows=False):
    df=con.execute("""SELECT f.response_id,f.dealer_code,f.department,f.rating_1to5,f.comment,
       a.content_sha256 AS local_sha,a.status AS local_status,a.has_unmasked_name AS local_name_flag,
       g.content_sha256 AS gemini_sha,g.has_unmasked_name AS gemini_name_flag
       FROM silver.feedback f LEFT JOIN silver.ai_enrichment a USING(response_id)
       LEFT JOIN silver.ai_enrichment_gemini g USING(response_id)
       WHERE f.in_analysis AND trim(f.comment)<>'' AND f.masking_version='source-name-roles-v1'
       ORDER BY f.response_id""").df()
    eligible=[];holdouts=[];screened=[]
    max_chars=settings()["max_comment_characters"]
    for row in df.itertuples():
        current=hashlib.sha256(row.comment.encode()).hexdigest()
        local_current=isinstance(row.local_sha,str) and current==row.local_sha
        gemini_current=isinstance(row.gemini_sha,str) and current==row.gemini_sha
        local_clear=local_current and row.local_status=='success' and row.local_name_flag is not None and not pd.isna(row.local_name_flag) and not bool(row.local_name_flag)
        reason=None
        if ((local_current and row.local_name_flag is not None and not pd.isna(row.local_name_flag) and bool(row.local_name_flag))
            or (gemini_current and row.gemini_name_flag is not None and not pd.isna(row.gemini_name_flag) and bool(row.gemini_name_flag))):
            reason='known_name_flag_pending_review'
        elif any(pattern.search(row.comment) for pattern in (EMAIL,PHONE,LABELLED_PLATE,BARE_PLATE)):
            reason='residual_contact_or_rego_pattern'
        elif len(row.comment)>max_chars:
            reason='comment_too_long'
        elif not all_rows and not local_clear:
            reason='not_in_local_clear_pilot'
        if reason:holdouts.append({'response_id':row.response_id,'reason':reason})
        else:eligible.append(row.response_id);screened.append(local_clear)
    source=df.loc[df.response_id.isin(eligible)].copy()
    source['local_name_screened']=screened
    return source,holdouts,len(df)


def persist_result(con,row,cachekey,result,cfg):
    values=[row.response_id,cachekey,hashlib.sha256(row.comment.encode()).hexdigest(),cfg['model'],cfg['prompt_version'],
            result.get('sentiment'),json.dumps(result.get('themes',[])),result.get('has_unmasked_name'),
            result.get('proposed_comment'),result.get('needs_review',True),result['status'],result.get('error_code'),
            result.get('model_version'),result.get('input_tokens',0),result.get('output_tokens_including_thinking',0),
            result.get('cost_usd_accounted',0),result['latency_seconds'],datetime.now(timezone.utc).isoformat(),'pending']
    con.execute('insert or replace into silver.ai_enrichment_gemini values ('+','.join(['?']*19)+')',values)


def run(database,limit=20,budget=5.0,workers=4,all_rows=False):
    cfg=settings();key=api_key();started=time.perf_counter()
    records=[];cache_hits=0;stopped=None
    with duckdb.connect(str(database)) as con:
        initialise(con)
        source,holdouts,source_total=privacy_checked_source(con,all_rows)
        if source.empty:raise ProviderError('no_eligible_masked_comments')
        sample=source if all_rows else shared.choose_sample(source,limit,cfg['sample_seed'])
        import pandas as pd
        held=pd.DataFrame(holdouts,columns=['response_id','reason'])
        con.execute('CREATE OR REPLACE TABLE ops.gemini_holdouts AS SELECT * FROM held')
        groups={}
        for row in sample.itertuples():groups.setdefault(fingerprint(row.comment,cfg),[]).append(row)
        queue=iter(groups.items());exhausted=False;pending={}
        spend=float(con.execute('select coalesce(sum(accounted_usd),0) from ops.gemini_spend').fetchone()[0])
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while pending or not exhausted:
                while len(pending)<workers and not exhausted and stopped is None:
                    try:cachekey,rows=next(queue)
                    except StopIteration:exhausted=True;break
                    cached=con.execute('select result_json from ops.gemini_cache where request_key=?',[cachekey]).fetchone()
                    if cached:
                        result=json.loads(cached[0])
                        for row in rows:
                            persist_result(con,row,cachekey,result,cfg)
                            records.append((row,cachekey,result,True));cache_hits+=1
                        continue
                    reserve=reservation(rows[0].comment,cfg)
                    if spend+reserve>budget:stopped='budget_limit_reached';exhausted=True;break
                    spend+=reserve;stamp=datetime.now(timezone.utc).isoformat()
                    attempt=hashlib.sha256((cachekey+stamp).encode()).hexdigest()
                    con.execute('insert into ops.gemini_spend values (?,?,?,?,?)',[attempt,cachekey,reserve,'reserved',stamp])
                    pending[pool.submit(infer,rows[0].comment,cfg,key)]=(cachekey,attempt,reserve,rows)
                if stopped is not None:exhausted=True
                if not pending:continue
                done,_=wait(pending,return_when=FIRST_COMPLETED)
                for future in done:
                    cachekey,attempt,reserve,rows=pending.pop(future)
                    try:result=future.result()
                    except Exception:
                        result={'status':'error','error_code':'unexpected_provider_error','cost_usd_accounted':reserve,
                                'latency_seconds':0,'attempts':cfg['max_attempts']}
                    spend+=result['cost_usd_accounted']-reserve
                    stamp=datetime.now(timezone.utc).isoformat()
                    con.execute('BEGIN TRANSACTION')
                    try:
                        con.execute('update ops.gemini_spend set accounted_usd=?,status=? where attempt_id=?',
                                    [result['cost_usd_accounted'],result['status'],attempt])
                        if result['status']=='success':
                            con.execute('insert or replace into ops.gemini_cache values (?,?,?)',[cachekey,json.dumps(result),stamp])
                        for row in rows:
                            persist_result(con,row,cachekey,result,cfg)
                            records.append((row,cachekey,result,False))
                        con.execute('COMMIT')
                    except Exception:con.execute('ROLLBACK');raise
                    if result.get('error_code') in {'http_400','http_401','http_403','http_404'}:
                        stopped='provider_configuration_error'
                    if sum(r['status']=='error' for _,_,r,_ in records)>=20:stopped='too_many_provider_errors'
                    if len(records)%25<workers or len(records)==len(sample) or result['status']=='error':
                        print(f"Gemini {len(records)}/{len(sample)} processed; accounted USD {spend:.4f}",flush=True)
        spend=float(con.execute('select coalesce(sum(accounted_usd),0) from ops.gemini_spend').fetchone()[0])
    review=ROOT/'data'/'gemini_review_sample.csv'
    if not all_rows and not review.exists():
        pd.DataFrame([{'response_id':row.response_id,'masked_comment':row.comment,
                       'human_sentiment':'','human_themes':'','human_has_unmasked_name':'','review_notes':''}
                       for row,_,_,_ in records]).to_csv(review,index=False)
    successful=sum(r['status']=='success' for _,_,r,_ in records)
    errors=sum(r['status']=='error' for _,_,r,_ in records)
    summary={'status':stopped or ('run_complete' if all_rows else 'pilot_complete'),
             'provider':'gemini','model':cfg['model'],'selected_comments':len(sample),'processed_comments':len(records),
             'accepted_nonblank_comments':source_total,'holdout_comments':len(holdouts),
             'eligible_comments':len(source),'extra_local_name_screened':int(sample.local_name_screened.sum()),
             'cache_hits':cache_hits,'successful':successful,'errors':errors,
             'new_name_flags':sum(r.get('has_unmasked_name') is True for _,_,r,_ in records),
             'needs_review':sum(r.get('needs_review',True) for _,_,r,_ in records),
             'elapsed_seconds':round(time.perf_counter()-started,2),'workers':workers,
             'cumulative_cost_usd_accounted':round(spend,6),'budget_usd':budget,
             'human_evaluation':'pending','all_eligible_processed':len(records)==len(sample),
             'full_dataset_processed':all_rows and not holdouts and successful==source_total,
             'silver_ratings_modified':False}
    filename='gemini_run.json' if all_rows else 'gemini_pilot.json'
    (ROOT/'outputs'/filename).write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2));return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',default=str(ROOT/'data'/'bronze_review.duckdb'))
    p.add_argument('--limit',type=int,default=20)
    p.add_argument('--budget-usd',type=float,default=5)
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--synthetic',action='store_true')
    p.add_argument('--check-key',action='store_true')
    p.add_argument('--all',action='store_true',dest='all_rows')
    args=p.parse_args()
    try:
        if args.check_key:api_key();print('API key configured (value withheld)');return
        if args.synthetic:
            cfg=settings();r=infer('The service was delayed and nobody called me back.',cfg,api_key())
            print(json.dumps({k:r.get(k) for k in ['status','error_code','sentiment','model_version','latency_seconds','input_tokens','output_tokens_including_thinking','cost_usd_accounted']},indent=2));return
        if args.limit<=0 or args.workers<1 or args.workers>8 or args.budget_usd<=0:p.error('Use a positive limit/budget and 1-8 workers')
        report=run(args.database,args.limit,args.budget_usd,args.workers,args.all_rows)
        if report['errors'] or not report['all_eligible_processed']:raise SystemExit(1)
    except ProviderError as error:
        raise SystemExit('Gemini setup/run stopped: '+error.code) from None

if __name__=='__main__':main()
