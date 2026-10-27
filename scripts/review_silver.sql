-- Attach data/silver_viewer.duckdb once in the DuckDB extension.
-- Run each SELECT in the SQL editor using DuckDB: Execute Query.
SELECT record_type, in_analysis, count(*) AS rows
FROM silver_viewer.silver.row_decisions GROUP BY ALL;

SELECT * FROM silver_viewer.ops.dq_results;

SELECT source_file, source_sheet, source_row, date_raw, date, department_raw,
       department, sales_subtype, rating_raw, rating_scale, rating_1to5, flags
FROM silver_viewer.silver.feedback
WHERE flags LIKE '%year_typo_corrected%' OR flags LIKE '%rating_missing%'
ORDER BY source_file, source_row;

SELECT source_file, rating_scale, count(*) AS rows,
       min(rating_1to5) AS min_score, max(rating_1to5) AS max_score
FROM silver_viewer.silver.feedback
WHERE source_file LIKE 'Ringwood%' OR source_file LIKE 'Geelong%'
GROUP BY ALL ORDER BY source_file, rating_scale;

SELECT department, count(*) AS responses,
       count(rating_1to5) AS valid_ratings,
       count(*) FILTER (WHERE negative) AS negative_ratings,
       round(100.0 * count(*) FILTER (WHERE negative) / nullif(count(rating_1to5),0),2) AS negative_pct
FROM silver_viewer.silver.feedback WHERE in_analysis GROUP BY department;
