with counts as (
 select 'monthly responses' as rule,(select sum(responses) from {{ ref('mart_dealer_dept_month') }}) as actual,
        (select count(*) from {{ ref('fct_feedback') }} where month is not null) as expected
 union all select 'monthly ratings',(select sum(rated_responses) from {{ ref('mart_dealer_dept_month') }}),
        (select count(rating_1to5) from {{ ref('fct_feedback') }} where month is not null)
 union all select 'annual responses',(select sum(responses) from {{ ref('mart_dealer_dept_summary') }}),(select count(*) from {{ ref('fct_feedback') }})
 union all select 'annual negatives',(select sum(negative_responses) from {{ ref('mart_dealer_dept_summary') }}),(select count(*) from {{ ref('fct_feedback') }} where negative)
 union all select 'quality sources',(select sum(source_feedback_rows) from {{ ref('mart_feedback_quality') }}),(select count(*) from {{ source('silver','feedback') }})
) select * from counts where actual<>expected
