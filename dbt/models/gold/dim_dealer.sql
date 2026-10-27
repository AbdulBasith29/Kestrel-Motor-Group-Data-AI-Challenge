-- Current dealer view preserves the existing reporting grain.
select dealer_code, dealership_name, state, region, brands, status, closed_date
from {{ ref('dim_dealer_history') }} where is_current
