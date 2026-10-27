-- Sensitivity proxy ONLY: not measured loss, profit, causation or a forecast.
with scenarios as (
 {% for fraction in var('scenario_recovery_fractions') %}
 select cast({{ fraction }} as double) as recovery_fraction{% if not loop.last %} union all {% endif %}
 {% endfor %}
)
select s.dealer_code,s.department,s.rated_responses,s.negative_responses,s.negative_share,s.revenue_aud,
       s.comparison_sample_sufficient,x.recovery_fraction,
       case when s.comparison_sample_sufficient then s.revenue_aud*s.negative_share end as negative_share_associated_revenue_proxy_aud,
       case when s.comparison_sample_sufficient then s.revenue_aud*s.negative_share*x.recovery_fraction end as scenario_value_proxy_aud
from {{ ref('mart_dealer_dept_summary') }} s cross join scenarios x
