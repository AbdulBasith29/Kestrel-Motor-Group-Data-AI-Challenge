-- Unique response/theme grain. Polarity is per theme, independent of the customer rating.
select f.response_id, json_extract_string(j.value,'$.theme') as theme_id,
       json_extract_string(j.value,'$.polarity') as theme_polarity
from {{ ref('fct_feedback') }} f
join {{ source('silver','ai_enrichment_gemini') }} a
  on f.response_id=a.response_id and f.ai_request_key=a.request_key
cross join json_each(a.themes_json) j
where f.ai_status='success'
