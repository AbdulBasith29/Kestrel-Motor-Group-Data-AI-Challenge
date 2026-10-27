-- Aggregate feedback BEFORE joining the independent monthly revenue fact.
with feedback as (
 select dealer_code,month,department,count(*) as responses,
        count(rating_1to5) as rated_responses,avg(rating_1to5) as mean_rating_1to5,
        count(*) filter(where negative) as negative_responses,
        count(*) filter(where has_comment) as commented_responses,
        count(*) filter(where ai_status='success') as enriched_responses,
        count(*) filter(where ai_status='success' and ai_sentiment='negative') as ai_negative_responses,
        count(*) filter(where ai_status='success' and ai_sentiment='mixed') as ai_mixed_responses,
        count(*) filter(where ai_needs_review) as ai_review_flagged_responses,
        count(*) filter(where dealer_mapping_assumed) as assumed_dealer_responses
 from {{ ref('fct_feedback') }} where month is not null group by dealer_code,month,department
)
select coalesce(r.dealer_code,f.dealer_code) as dealer_code,
       coalesce(r.month,f.month) as month,coalesce(r.department,f.department) as department,
       d.dealership_name,d.state,d.region,m.half_year,
       coalesce(f.responses,0) as responses,coalesce(f.rated_responses,0) as rated_responses,
       coalesce(f.negative_responses,0) as negative_responses,
       f.negative_responses/nullif(f.rated_responses,0) as negative_share,
       f.mean_rating_1to5,coalesce(f.commented_responses,0) as commented_responses,
       coalesce(f.enriched_responses,0) as enriched_responses,
       f.enriched_responses/nullif(f.commented_responses,0) as ai_coverage,
       coalesce(f.ai_negative_responses,0) as ai_negative_responses,
       coalesce(f.ai_mixed_responses,0) as ai_mixed_responses,
       coalesce(f.ai_review_flagged_responses,0) as ai_review_flagged_responses,
       coalesce(f.assumed_dealer_responses,0) as assumed_dealer_responses,
       r.volume,r.revenue_aud,r.revenue_aud/nullif(r.volume,0) as revenue_per_unit,
       1000.0*f.responses/nullif(r.volume,0) as feedback_count_per_1000_units,
       r.dealer_code is not null as has_revenue_reference,
       coalesce(f.rated_responses,0)>={{ var('minimum_rated_responses') }} as comparison_sample_sufficient
from {{ ref('fct_monthly_revenue') }} r
full outer join feedback f using(dealer_code,month,department)
left join {{ ref('dim_dealer') }} d on d.dealer_code=coalesce(r.dealer_code,f.dealer_code)
left join {{ ref('dim_month') }} m on m.month=coalesce(r.month,f.month)
