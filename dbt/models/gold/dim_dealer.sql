-- Official reference grain: one row per dealership.
select dealer_code, dealership_name, state, region, brands, status,
       cast(closed_date as date) as closed_date
from read_csv('{{ var("reference_dir") }}/dealerships.csv', header=true)
