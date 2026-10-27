-- One observed version per dealer; intervals are [valid_from, valid_to).
select dbt_scd_id as dealer_version_id, dealer_code, dealership_name, suburb,
       state, region, brands, status, closed_date,
       dbt_valid_from as valid_from, dbt_valid_to as valid_to,
       dbt_valid_to is null as is_current
from {{ ref('dealer_history_snapshot') }}
