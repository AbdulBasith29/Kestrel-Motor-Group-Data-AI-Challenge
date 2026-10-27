with expected as (
 select count(*) as responses,coalesce(sum(json_array_length(a.themes_json)),0) as themes
 from {{ source('silver','feedback') }} s join {{ source('silver','ai_enrichment_gemini') }} a using(response_id)
 where s.in_analysis and a.status='success' and a.content_sha256=sha256(s.comment) and s.comment<>''
)
select 'ai response count' as issue from expected
where responses<>(select count(*) from {{ ref('fct_feedback') }} where ai_status='success')
union all select 'theme bridge count' from expected
where themes<>(select count(*) from {{ ref('bridge_feedback_theme') }})
union all select 'too many themes' from {{ ref('bridge_feedback_theme') }} group by response_id having count(*)>3
