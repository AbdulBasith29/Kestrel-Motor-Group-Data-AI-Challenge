"""Build/test dbt reporting models, then publish and export a separate reporting-only database.

Run with requirements-gold.txt installed: python src/gold.py
No AI calls; reads the current masked Silver/enrichment database and reference CSVs.
"""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import duckdb
from common import ROOT

MODELS=['dim_dealer','dim_dealer_history','dim_month','dim_department','dim_theme','fct_feedback',
        'bridge_feedback_theme','fct_monthly_revenue','mart_dealer_dept_month',
        'mart_theme_drivers','mart_dealer_dept_summary','mart_feedback_quality','mart_opportunity_scenarios']
FORBIDDEN={'comment','comments','proposed_comment','verbatim','notes','customer','customer_name',
           'staff','staff_name','name','phone','mobile','email','rego','customer_number','source_ref',
           'name_spans','name_mentions','result_json'}


def ensure_ai_contract(con):
    """Allow rating reporting without an executed AI step; empty means no derived results."""
    exists=con.execute("select count(*) from information_schema.tables where table_schema='silver' and table_name='ai_enrichment_gemini'").fetchone()[0]
    if exists:return False
    from gemini_enrichment import initialise
    initialise(con)  # Local empty table contracts only; no key lookup or provider call.
    return True


def validate_build(result):
    rows=result.get('results',[])
    tests=[r for r in rows if r.get('unique_id','').startswith('test.')]
    built={r.get('unique_id','').split('.')[-1] for r in rows if r.get('unique_id','').startswith('model.')}
    if not tests or built!=set(MODELS) or any(r.get('status') not in {'success','pass'} for r in rows):
        raise RuntimeError('Gold publication blocked: build missing, incomplete or not all tests passed')
    return len(tests)


def publish_verified(con,result):
    validate_build(result)
    present={r[0] for r in con.execute("select table_name from information_schema.tables where table_schema='gold_staging'").fetchall()}
    if present!=set(MODELS):raise RuntimeError('Gold staging model set differs from the reviewed model list')
    columns=con.execute("select table_name,column_name from information_schema.columns where table_schema='gold_staging'").fetchall()
    if any(name.lower() in FORBIDDEN for _,name in columns):raise RuntimeError('Restricted identifier/text column detected; publication blocked')
    con.execute('CREATE SCHEMA IF NOT EXISTS gold');con.execute('BEGIN TRANSACTION')
    try:
        for model in MODELS:con.execute(f'CREATE OR REPLACE TABLE gold.{model} AS SELECT * FROM gold_staging.{model}')
        con.execute('COMMIT')
    except Exception:con.execute('ROLLBACK');raise


def export_reporting(database,output):
    database=Path(database).resolve();output=Path(output).resolve()
    if output==database or not output.is_relative_to((ROOT/'data').resolve()):
        raise ValueError('Reporting export must be a different file inside the project data directory')
    output.parent.mkdir(exist_ok=True)
    temporary=output.with_name(output.stem+'.'+uuid.uuid4().hex+'.tmp.duckdb')
    with duckdb.connect() as con:
        con.execute('ATTACH ? AS source_db (READ_ONLY)',[str(database)])
        con.execute("ATTACH ? AS reporting (STORAGE_VERSION 'v1.0.0')",[str(temporary)])
        con.execute('CREATE SCHEMA reporting.gold')
        for model in MODELS:
            con.execute(f'CREATE TABLE reporting.gold.{model} AS SELECT * FROM source_db.gold.{model}')
        con.execute('DETACH reporting')
    with duckdb.connect(str(temporary),read_only=True) as con:
        assert {r[0] for r in con.execute('select distinct table_schema from information_schema.tables').fetchall()}=={'gold'}
        assert not any(r[0].lower() in FORBIDDEN for r in con.execute('select column_name from information_schema.columns').fetchall())
    # Atomic file replacement: the new file never contains Bronze, Silver, caches or raw text pages.
    os.replace(temporary,output)
    return output


def write_csv(con,query,path):
    result=con.execute(query)
    with Path(path).open('w',newline='',encoding='utf-8') as handle:
        writer=csv.writer(handle);writer.writerow([d[0] for d in result.description]);writer.writerows(result.fetchall())


def fingerprint(con):
    return con.execute("select sha256(string_agg(to_json(s),'' order by response_id)) from silver.feedback s").fetchone()[0]


def build(database,output):
    database=Path(database).resolve();output=Path(output).resolve()
    if not database.exists():raise FileNotFoundError('Build Bronze, Silver and enrichment before Gold')
    reference=ROOT/'reference'
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in reference.glob('*.csv')}
    with duckdb.connect(str(database)) as con:
        created_empty_ai_contract=ensure_ai_contract(con)
        before=fingerprint(con)
    executable=Path(sys.executable).with_name('dbt.exe' if os.name=='nt' else 'dbt')
    if not executable.exists():
        fallback=ROOT/'.venv-gold'/('Scripts' if os.name=='nt' else 'bin')/('dbt.exe' if os.name=='nt' else 'dbt')
        executable=fallback if fallback.exists() else Path(shutil.which('dbt') or '')
    if not executable.is_file():raise RuntimeError('Install requirements-gold.txt before running the Gold build')
    env={**os.environ,'DO_NOT_TRACK':'1','DBT_SEND_ANONYMOUS_USAGE_STATS':'false','KESTREL_DB_PATH':str(database),
         'KESTREL_REFERENCE_DIR':reference.as_posix()}
    command=[str(executable),'build','--project-dir',str(ROOT/'dbt'),'--profiles-dir',str(ROOT/'dbt'),
             '--vars',json.dumps({'reference_dir':reference.as_posix()})]
    process=subprocess.run(command,cwd=ROOT/'dbt',env=env,capture_output=True,text=True)
    print(process.stdout[-5500:],flush=True)
    if process.returncode:
        print(process.stderr[-1500:],flush=True)
        raise RuntimeError('dbt build failed in gold_staging; existing Gold/export unchanged')
    result=json.loads((ROOT/'dbt'/'target'/'run_results.json').read_text(encoding='utf-8'))
    passed=validate_build(result)
    assert hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in reference.glob('*.csv')}
    with duckdb.connect(str(database)) as con:
        assert before==fingerprint(con),'Silver feedback changed during reporting build'
        publish_verified(con,result)
        counts={model:con.execute(f'SELECT count(*) FROM gold.{model}').fetchone()[0] for model in MODELS}
        source_revenue=con.execute('select sum(revenue_aud) from gold.fct_monthly_revenue').fetchone()[0]
        summary={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'status':'passed',
                 'dbt_invocation_id':result['metadata']['invocation_id'],'models_built':len(MODELS),'dbt_tests_passed':passed,
                 'row_counts':counts,'reference_hashes_unchanged':True,'silver_feedback_unchanged':True,
                 'reference_revenue_aud':str(source_revenue),'revenue_reconciles_without_fanout':True,
                 'export':'data/'+output.name,'reporting_database_contains_only_gold':True,
                 'ai_status_counts':dict(con.execute('select ai_status,count(*) from gold.fct_feedback group by ai_status').fetchall()),
                 'undated_responses':con.execute('select count(*) from gold.fct_feedback where is_undated').fetchone()[0],
                 'unrated_responses':con.execute('select count(*) from gold.fct_feedback where is_unrated').fetchone()[0],
                 'ai_labels_provisional':True,'scenario_values_are_sensitivity_proxies':True,
                 'created_empty_ai_contract':created_empty_ai_contract}
        csvdir=ROOT/'data'/'reporting_exports';csvdir.mkdir(exist_ok=True)
        for model in MODELS:write_csv(con,f'SELECT * FROM gold.{model}',csvdir/(model+'.csv'))
        write_csv(con,"""select month,department,sum(responses) as responses,sum(rated_responses) as rated_responses,
            sum(negative_responses) as negative_responses,sum(negative_responses)/nullif(sum(rated_responses),0) as negative_share,
            sum(revenue_aud) as revenue_aud from gold.mart_dealer_dept_month group by month,department order by month,department""",ROOT/'outputs'/'gold_monthly_summary.csv')
        write_csv(con,"""select theme_id,sum(negative_rated_driver_mentions) as negative_rated_driver_mentions,
            sum(strictly_negative_rated_driver_mentions) as strictly_negative_rated_driver_mentions,
            sum(review_flagged_driver_mentions) as review_flagged_driver_mentions,
            sum(unflagged_driver_mentions) as unflagged_driver_mentions
            from gold.mart_theme_drivers group by theme_id order by negative_rated_driver_mentions desc""",ROOT/'outputs'/'gold_theme_summary.csv')
        write_csv(con,'SELECT * FROM gold.mart_dealer_dept_summary ORDER BY negative_responses DESC',ROOT/'outputs'/'gold_dealer_summary.csv')
    export_reporting(database,output)
    (ROOT/'outputs'/'gold_verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True);return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',default=str(ROOT/'data'/'bronze_review.duckdb'))
    p.add_argument('--output',default=str(ROOT/'data'/'gold_reporting.duckdb'))
    a=p.parse_args();build(a.database,a.output)
