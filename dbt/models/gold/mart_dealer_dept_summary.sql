-- Annual feedback includes undated responses; revenue is separately aggregated once.
with feedback as (
 select dealer_code,department,count(*) as responses,count(rating_1to5) as rated_responses,
        count(*) filter(where negative) as negative_responses,avg(rating_1to5) as mean_rating_1to5,
        count(*) filter(where is_undated) as undated_responses,count(*) filter(where is_unrated) as unrated_responses,
        count(*) filter(where has_comment) as commented_responses,
        count(*) filter(where ai_status='success') as enriched_responses,
        count(*) filter(where ai_needs_review) as ai_review_flagged_responses,
        count(*) filter(where dealer_mapping_assumed) as assumed_dealer_responses
 from {{ ref('fct_feedback') }} group by dealer_code,department
), revenue as (
 select dealer_code,department,sum(volume) as volume,sum(revenue_aud) as revenue_aud
 from {{ ref('fct_monthly_revenue') }} group by dealer_code,department
)
select coalesce(r.dealer_code,f.dealer_code) as dealer_code,coalesce(r.department,f.department) as department,
       d.dealership_name,d.state,d.region,
       coalesce(f.responses,0) as responses,coalesce(f.rated_responses,0) as rated_responses,
       coalesce(f.negative_responses,0) as negative_responses,
       f.negative_responses/nullif(f.rated_responses,0) as negative_share,f.mean_rating_1to5,
       coalesce(f.undated_responses,0) as undated_responses,coalesce(f.unrated_responses,0) as unrated_responses,
       coalesce(f.commented_responses,0) as commented_responses,coalesce(f.enriched_responses,0) as enriched_responses,
       f.enriched_responses/nullif(f.commented_responses,0) as ai_coverage,
       coalesce(f.ai_review_flagged_responses,0) as ai_review_flagged_responses,
       coalesce(f.assumed_dealer_responses,0) as assumed_dealer_responses,
       r.volume,r.revenue_aud,r.revenue_aud/nullif(r.volume,0) as revenue_per_unit,
       coalesce(f.rated_responses,0)>={{ var('minimum_rated_responses') }} as comparison_sample_sufficient
from revenue r full outer join feedback f using(dealer_code,department)
left join {{ ref('dim_dealer') }} d on d.dealer_code=coalesce(r.dealer_code,f.dealer_code)
