"""Execute Gold business queries from any working directory; no shell redirection required."""
import argparse
import csv
import json
from pathlib import Path
import re
import duckdb
ROOT=Path(__file__).resolve().parents[1]

def run(database=None):
    path=Path(database or ROOT/'data'/'gold_reporting.duckdb').resolve()
    sql=(ROOT/'analysis'/'business_answers.sql').read_text(encoding='utf-8')
    destination=ROOT/'data'/'business_answers';destination.mkdir(exist_ok=True)
    results={}
    with duckdb.connect() as con:
        con.execute('ATTACH ? AS gold_reporting (READ_ONLY)',[str(path)])
        for statement in con.extract_statements(sql):
            cursor=con.execute(statement.query)
            if statement.type.name!='SELECT':continue
            label=re.search(r'/\*\s*(Q[0-9][a-z]?)\s*\*/',statement.query)
            if label is None:raise ValueError('Each SELECT needs its explicit query marker')
            name=label.group(1)
            columns=[d[0] for d in cursor.description];rows=cursor.fetchall()
            with (destination/(name+'.csv')).open('w',newline='',encoding='utf-8') as handle:
                writer=csv.writer(handle);writer.writerow(columns);writer.writerows(rows)
            results[name]={'rows':len(rows),'columns':columns}
        assert len(results)==8
        assert 'rated' in results['Q1a']['columns'] and 'n_h1' in results['Q2a']['columns']
        # Catch the exact regression in the supplied CASE expression.
        assert con.execute("select count(*) from accepted where response_date is null and half is not null").fetchone()[0]==0
        assert con.execute('select count(*) from worsening_four').fetchone()[0]<=4
        assert con.execute('select count(*) from fb').fetchone()[0]==con.execute('select count(rating_1to5) from gold.fct_feedback').fetchone()[0]
    report={'status':'passed','query_results':results,'undated_not_assigned_to_half':True,
            'input_tables_modified':False,'output_directory':'data/business_answers',
            'financial_outputs':'hypothetical_H2_cohort_sensitivity_not_measured_loss',
            'AI_theme_outputs':'provisional_multi_label_counts'}
    (ROOT/'outputs'/'business_answers_verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database')
    run(p.parse_args().database)
