{% snapshot dealer_history_snapshot %}
{{ config(target_schema='dealer_history', unique_key='dealer_code', strategy='check',
          check_cols=['dealership_name','suburb','state','region','brands','status','closed_date'],
          invalidate_hard_deletes=True) }}
-- Observation-time history: source has no trustworthy attribute effective timestamp.
select dealer_code, dealership_name, suburb, state, region, brands, status,
       cast(closed_date as date) as closed_date
from read_csv('{{ var("reference_dir") }}/dealerships.csv', header=true)
{% endsnapshot %}
