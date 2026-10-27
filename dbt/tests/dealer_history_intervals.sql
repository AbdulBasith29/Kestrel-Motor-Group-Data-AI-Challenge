with intervals as (
    select *, lead(valid_from) over (partition by dealer_code order by valid_from) as next_start
    from {{ ref('dim_dealer_history') }}
)
select dealer_code from intervals
where valid_to <= valid_from
   or (next_start is not null and (valid_to is null or valid_to > next_start))
union all
select dealer_code from {{ ref('dim_dealer_history') }}
group by dealer_code having sum(case when is_current then 1 else 0 end) > 1
