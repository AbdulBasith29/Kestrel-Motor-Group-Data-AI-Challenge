-- Fails for any dealership with no feedback at all (a mapping gap)
select d.dealer_code
from {{ ref('dim_dealer') }} d
left join {{ ref('fct_feedback') }} f using (dealer_code)
group by d.dealer_code
having count(f.response_id) = 0
