-- Fails if any normalised rating falls outside 1-5
select * from {{ ref('fct_feedback') }}
where rating_1to5 < 1 or rating_1to5 > 5
