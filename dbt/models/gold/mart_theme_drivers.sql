-- Monthly multi-label theme counts; revenue deliberately absent to avoid fanout.
with denominators as (
 select dealer_code,department,month,
        count(*) filter(where negative and ai_status='success') as negative_rated_with_ai
 from {{ ref('fct_feedback') }} group by dealer_code,department,month
), counts as (
 select f.dealer_code,f.department,f.month,b.theme_id,count(*) as theme_mentions,
        count(*) filter(where f.negative and b.theme_polarity in ('negative','mixed')) as negative_rated_driver_mentions,
        count(*) filter(where f.negative and b.theme_polarity='negative') as strictly_negative_rated_driver_mentions,
        count(*) filter(where f.ai_sentiment in ('negative','mixed') and b.theme_polarity in ('negative','mixed')) as text_negative_or_mixed_driver_mentions,
        count(*) filter(where f.rating_1to5 is null) as unrated_theme_mentions,
        count(*) filter(where f.negative and b.theme_polarity in ('negative','mixed') and f.ai_needs_review) as review_flagged_driver_mentions,
        count(*) filter(where f.negative and b.theme_polarity in ('negative','mixed') and not f.ai_needs_review) as unflagged_driver_mentions
 from {{ ref('bridge_feedback_theme') }} b join {{ ref('fct_feedback') }} f using(response_id)
 group by f.dealer_code,f.department,f.month,b.theme_id
)
select c.*,d.negative_rated_with_ai,
       c.negative_rated_driver_mentions/nullif(d.negative_rated_with_ai,0) as driver_share_of_enriched_negative_feedback
from counts c join denominators d
 on c.dealer_code=d.dealer_code and c.department=d.department and c.month is not distinct from d.month
