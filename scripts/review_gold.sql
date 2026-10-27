-- Attach data/gold_reporting.duckdb once in the DuckDB extension.
-- Run queries from a .sql editor with DuckDB: Execute Query.
SELECT table_name FROM information_schema.tables
WHERE table_catalog='gold_reporting' AND table_schema='gold' ORDER BY table_name;

SELECT count(*) AS responses,count(rating_1to5) AS valid_ratings,
       count(*) FILTER(WHERE negative) AS negative_ratings,
       count(*) FILTER(WHERE negative)*1.0/count(rating_1to5) AS negative_share
FROM gold_reporting.gold.fct_feedback;

SELECT ai_status,count(*) AS responses
FROM gold_reporting.gold.fct_feedback GROUP BY ai_status;

-- All three totals should equal 838685990.00. Do not join revenue to the theme bridge.
SELECT 'reference fact' AS source,sum(revenue_aud) AS revenue_aud FROM gold_reporting.gold.fct_monthly_revenue
UNION ALL SELECT 'monthly reporting',sum(revenue_aud) FROM gold_reporting.gold.mart_dealer_dept_month
UNION ALL SELECT 'annual reporting',sum(revenue_aud) FROM gold_reporting.gold.mart_dealer_dept_summary;

-- Themes are multi-label and provisional. Mixed polarity is included explicitly.
SELECT theme_id,sum(negative_rated_driver_mentions) AS negative_rated_driver_mentions,
       sum(strictly_negative_rated_driver_mentions) AS strictly_negative_driver_mentions,
       sum(review_flagged_driver_mentions) AS review_flagged_mentions
FROM gold_reporting.gold.mart_theme_drivers GROUP BY theme_id
ORDER BY negative_rated_driver_mentions DESC;

-- Dated responses only; the ten unknown dates are retained in annual totals.
SELECT half_year,sum(rated_responses) AS valid_ratings,sum(negative_responses) AS negative_ratings,
       sum(negative_responses)*1.0/nullif(sum(rated_responses),0) AS negative_share
FROM gold_reporting.gold.mart_dealer_dept_month GROUP BY half_year ORDER BY half_year;

SELECT dealership_name,department,rated_responses,negative_responses,negative_share,
       ai_coverage,ai_review_flagged_responses,assumed_dealer_responses
FROM gold_reporting.gold.mart_dealer_dept_summary
WHERE comparison_sample_sufficient ORDER BY negative_responses DESC LIMIT 10;

-- Illustrative sensitivity ONLY, not lost revenue/profit or a forecast. Pick ONE scenario.
SELECT dealer_code,department,negative_share_associated_revenue_proxy_aud,scenario_value_proxy_aud
FROM gold_reporting.gold.mart_opportunity_scenarios
WHERE recovery_fraction=0.01 AND comparison_sample_sufficient
ORDER BY scenario_value_proxy_aud DESC LIMIT 10;
