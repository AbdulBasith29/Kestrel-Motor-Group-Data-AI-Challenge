select 'duplicate source month' as issue,dealer_code from read_csv('{{ var("reference_dir") }}/monthly_revenue.csv',header=true)
group by dealer_code,month having count(*)>1
union all select 'negative value',dealer_code from {{ ref('fct_monthly_revenue') }} where revenue_aud<0 or volume<0
union all select 'closed site activity',r.dealer_code from {{ ref('fct_monthly_revenue') }} r join {{ ref('dim_dealer') }} d using(dealer_code)
where d.closed_date is not null and r.month_start>d.closed_date and (r.revenue_aud<>0 or r.volume<>0)
union all select 'feedback after closure',f.dealer_code from {{ ref('fct_feedback') }} f join {{ ref('dim_dealer') }} d using(dealer_code)
where d.closed_date is not null and f.response_date>d.closed_date
