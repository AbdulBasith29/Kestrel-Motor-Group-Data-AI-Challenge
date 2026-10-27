-- Reporting months, October 2025 to September 2026
select
    cast(month_start as date) as month_start,
    strftime(month_start, '%Y-%m') as month,
    case when month_start < date '2026-04-01' then 'H1 (Oct-Mar)' else 'H2 (Apr-Sep)' end as half_year
from range(date '2025-10-01', date '2026-10-01', interval 1 month) as t(month_start)
