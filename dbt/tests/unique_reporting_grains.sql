select 'revenue' as model,count(*) as rows_in_key from {{ ref('fct_monthly_revenue') }} group by dealer_code,month,department having count(*)>1
union all select 'monthly',count(*) from {{ ref('mart_dealer_dept_month') }} group by dealer_code,month,department having count(*)>1
union all select 'annual',count(*) from {{ ref('mart_dealer_dept_summary') }} group by dealer_code,department having count(*)>1
union all select 'bridge',count(*) from {{ ref('bridge_feedback_theme') }} group by response_id,theme_id having count(*)>1
union all select 'drivers',count(*) from {{ ref('mart_theme_drivers') }} group by dealer_code,department,month,theme_id having count(*)>1
union all select 'scenarios',count(*) from {{ ref('mart_opportunity_scenarios') }} group by dealer_code,department,recovery_fraction having count(*)>1
