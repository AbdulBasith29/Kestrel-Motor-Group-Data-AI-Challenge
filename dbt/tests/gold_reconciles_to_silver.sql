-- Fails if gold lost or gained rows compared with silver's in-analysis count
select gold_rows, silver_rows
from (select count(*) as gold_rows from {{ ref('fct_feedback') }}),
     (select count(*) as silver_rows from {{ source('silver', 'feedback') }} where in_analysis)
where gold_rows <> silver_rows
