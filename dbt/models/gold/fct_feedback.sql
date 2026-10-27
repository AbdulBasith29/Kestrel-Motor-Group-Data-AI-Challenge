-- Accepted response grain; dates may be missing. No comment/customer/staff/contact columns.
with base as (
    select s.*, a.request_key as ai_request_key, a.content_sha256,
           a.status as provider_status, a.sentiment, a.needs_review,
           a.has_unmasked_name as provider_name_flag, a.human_review_status,
           a.model, a.prompt_version,
           a.content_sha256 = sha256(s.comment) as ai_matches_current_text
    from {{ source('silver','feedback') }} s
    left join {{ source('silver','ai_enrichment_gemini') }} a using (response_id)
    where s.in_analysis
)
select response_id, dealer_code, cast(date as date) as response_date,
       cast(date_trunc('month',date) as date) as month_start,
       strftime(date,'%Y-%m') as month, coalesce(department,'Unknown') as department,
       sales_subtype, rating_1to5, rating_scale, negative,
       comment <> '' as has_comment, flags <> '' as has_quality_flags,
       date is null as is_undated, rating_1to5 is null as is_unrated,
       source_file like 'Hunter Motors%' as dealer_mapping_assumed,
       case when comment='' then 'no_comment'
            when ai_request_key is null then 'not_enriched'
            when not coalesce(ai_matches_current_text,false) then 'stale_result'
            when provider_status='success' then 'success' else 'provider_error' end as ai_status,
       case when ai_matches_current_text and provider_status='success' then sentiment end as ai_sentiment,
       case when ai_matches_current_text then coalesce(needs_review,true) else comment<>'' end as ai_needs_review,
       case when ai_matches_current_text then provider_name_flag end as ai_name_flag,
       case when ai_matches_current_text then human_review_status end as ai_human_review_status,
       case when ai_matches_current_text then model end as ai_model,
       case when ai_matches_current_text then prompt_version end as ai_prompt_version,
       case when ai_matches_current_text then ai_request_key end as ai_request_key
from base
