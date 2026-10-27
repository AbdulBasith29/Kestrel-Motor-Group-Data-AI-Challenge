-- Keep all Silver response dispositions visible, not just accepted records.
select s.dealer_code,coalesce(s.department,'Unknown') as department,count(*) as source_feedback_rows,
       count(*) filter(where s.in_analysis) as accepted_responses,
       count(*) filter(where not s.in_analysis) as excluded_responses,
       count(*) filter(where s.in_analysis and s.date is null) as accepted_undated_responses,
       count(*) filter(where s.in_analysis and s.rating_1to5 is null) as accepted_unrated_responses,
       count(*) filter(where f.ai_status='provider_error') as ai_error_responses,
       count(*) filter(where f.ai_status='not_enriched') as ai_missing_responses,
       count(*) filter(where f.ai_status='stale_result') as ai_stale_responses,
       count(*) filter(where f.ai_name_flag) as ai_name_flagged_responses
from {{ source('silver','feedback') }} s
left join {{ ref('fct_feedback') }} f using(response_id)
group by s.dealer_code,coalesce(s.department,'Unknown')
