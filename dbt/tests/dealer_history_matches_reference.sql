with expected as (
 select dealer_code, dealership_name, suburb, state, region, brands, status,
        cast(closed_date as date) as closed_date
 from read_csv('{{ var("reference_dir") }}/dealerships.csv', header=true)
), actual as (
 select dealer_code, dealership_name, suburb, state, region, brands, status, closed_date
 from {{ ref('dim_dealer_history') }} where is_current
)
select * from (select * from expected except select * from actual)
union all
select * from (select * from actual except select * from expected)
