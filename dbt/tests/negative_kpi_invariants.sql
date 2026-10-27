select response_id from {{ ref('fct_feedback') }}
where (rating_1to5 is null and negative is not null)
   or (rating_1to5 is not null and negative is distinct from (rating_1to5<=2))
union all
select dealer_code from {{ ref('mart_dealer_dept_month') }}
where negative_responses>rated_responses or rated_responses>responses or enriched_responses>commented_responses
   or negative_share not between 0 and 1 or ai_coverage not between 0 and 1
union all
select dealer_code from {{ ref('mart_dealer_dept_summary') }}
where negative_responses>rated_responses or rated_responses>responses or negative_share not between 0 and 1
