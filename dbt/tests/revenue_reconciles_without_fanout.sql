with expected as (
 select sum(sales_revenue_aud+service_revenue_aud+parts_revenue_aud) as revenue
 from read_csv('{{ var("reference_dir") }}/monthly_revenue.csv',header=true)
), actual as (
 select 'revenue fact' as model,sum(revenue_aud) as revenue from {{ ref('fct_monthly_revenue') }}
 union all select 'monthly mart',sum(revenue_aud) from {{ ref('mart_dealer_dept_month') }}
 union all select 'annual mart',sum(revenue_aud) from {{ ref('mart_dealer_dept_summary') }}
)
select a.model,a.revenue,e.revenue as expected from actual a cross join expected e where abs(a.revenue-e.revenue)>0.005
