select dealer_code,department,recovery_fraction from {{ ref('mart_opportunity_scenarios') }}
where recovery_fraction not between 0 and 1
 or (not comparison_sample_sufficient and scenario_value_proxy_aud is not null)
 or scenario_value_proxy_aud>negative_share_associated_revenue_proxy_aud
 or abs(scenario_value_proxy_aud-negative_share_associated_revenue_proxy_aud*recovery_fraction)>0.005
