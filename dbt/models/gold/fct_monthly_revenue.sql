-- One row per dealer/month/department: revenue is never joined to individual responses.
with source as (
 select * from read_csv('{{ var("reference_dir") }}/monthly_revenue.csv',header=true)
), unpivoted as (
 select dealer_code,month,'Sales' as department,vehicles_sold as volume,sales_revenue_aud as revenue_aud from source
 union all
 select dealer_code,month,'Service',service_jobs,service_revenue_aud from source
 union all
 select dealer_code,month,'Parts',parts_transactions,parts_revenue_aud from source
)
select dealer_code,month,cast(month||'-01' as date) as month_start,department,
       cast(volume as bigint) as volume,cast(revenue_aud as decimal(18,2)) as revenue_aud
from unpivoted
