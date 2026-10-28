-- Original business questions and first SQL written by me.
-- Codex adapted them to the reporting-only Gold schema and added validation corrections.
-- Business answers from the reporting-only Gold database.
-- In the viewer, attach data/gold_reporting.duckdb once, then execute this in a SQL editor.
-- Cross-platform runner: python scripts/run_business_answers.py
USE gold_reporting;

CREATE OR REPLACE TEMP VIEW accepted AS
SELECT f.*,d.dealership_name,d.region,
       CASE WHEN f.response_date IS NULL THEN NULL
            WHEN f.response_date<DATE '2026-04-01' THEN 'H1' ELSE 'H2' END AS half
FROM gold.fct_feedback f JOIN gold.dim_dealer d USING(dealer_code);
CREATE OR REPLACE TEMP VIEW fb AS SELECT * FROM accepted WHERE rating_1to5 IS NOT NULL;

-- Compute, rather than hard-code, the four largest H1-to-H2 increases among n>=30 per half.
CREATE OR REPLACE TEMP VIEW dealer_halves AS
SELECT dealer_code,dealership_name,
       count(*) FILTER(WHERE half='H1') AS n_h1,count(*) FILTER(WHERE half='H2') AS n_h2,
       avg(negative::int) FILTER(WHERE half='H1') AS h1_rate,
       avg(negative::int) FILTER(WHERE half='H2') AS h2_rate
FROM fb WHERE response_date IS NOT NULL GROUP BY dealer_code,dealership_name;
CREATE OR REPLACE TEMP VIEW worsening_four AS
SELECT dealer_code FROM dealer_halves WHERE n_h1>=30 AND n_h2>=30 AND h2_rate>h1_rate
ORDER BY h2_rate-h1_rate DESC,dealer_code LIMIT 4;

-- Q1a: Negative ratings by department; missing ratings never enter the denominator.
SELECT /* Q1a */ department,count(*) AS rated,count(*) FILTER(WHERE negative) AS negative,
       round(100.0*avg(negative::int),1) AS negative_pct
FROM fb GROUP BY department ORDER BY negative DESC;

-- Q1b: Long form keeps each department's own denominator visible.
SELECT /* Q1b */ dealership_name,department,rated_responses,negative_responses,
       round(100.0*negative_share,1) AS negative_pct,comparison_sample_sufficient,
       assumed_dealer_responses
FROM gold.mart_dealer_dept_summary ORDER BY negative_responses DESC;

-- Q2a: Dated-only half-year comparison; unknown dates are not assigned to H2.
SELECT /* Q2a */ dealership_name,round(100*h1_rate,1) AS h1_pct,round(100*h2_rate,1) AS h2_pct,
       round(100*(h2_rate-h1_rate),1) AS change_pts,n_h1,n_h2,
       n_h1>=30 AND n_h2>=30 AS comparison_sample_sufficient
FROM dealer_halves ORDER BY change_pts DESC NULLS LAST;

-- Q2b: Response-weighted monthly comparison; cohort is selected above, not pre-assumed.
SELECT /* Q2b */ month,
       round(100.0*avg(negative::int) FILTER(WHERE dealer_code IN(SELECT dealer_code FROM worsening_four)),1) AS worsening_four_pct,
       round(100.0*avg(negative::int) FILTER(WHERE dealer_code NOT IN(SELECT dealer_code FROM worsening_four)),1) AS rest_of_group_pct,
       count(*) FILTER(WHERE dealer_code IN(SELECT dealer_code FROM worsening_four)) AS worsening_four_rated,
       count(*) FILTER(WHERE dealer_code NOT IN(SELECT dealer_code FROM worsening_four)) AS rest_of_group_rated
FROM fb WHERE response_date IS NOT NULL GROUP BY month ORDER BY month;

-- Q3: ILLUSTRATIVE H2-cohort job-based sensitivity, not measured loss/profit/forecast.
-- Assumptions: survey shares generalise to jobs; an affected job proxies one affected customer;
-- 10/25/40% of that hypothetical cohort churn; future 12-month spend is TWO jobs per customer.
-- No separate x2 annualisation of H2 job counts. Distinct customers are not identifiable here.
WITH rates AS (
 SELECT dealer_code,dealership_name,
        avg(negative::int) FILTER(WHERE half='H1') AS h1_rate,
        avg(negative::int) FILTER(WHERE half='H2') AS h2_rate,
        count(*) FILTER(WHERE half='H1') AS n_h1,count(*) FILTER(WHERE half='H2') AS n_h2
 FROM fb WHERE department='Service' AND response_date IS NOT NULL GROUP BY dealer_code,dealership_name
), volume AS (
 SELECT dealer_code,sum(volume) AS h2_jobs,sum(revenue_aud)/nullif(sum(volume),0) AS revenue_per_job
 FROM gold.fct_monthly_revenue WHERE department='Service' AND month BETWEEN '2026-04' AND '2026-09'
 GROUP BY dealer_code
), eligible AS (
 SELECT *,CASE WHEN n_h1>=30 AND n_h2>=30 AND h1_rate IS NOT NULL AND h2_rate IS NOT NULL AND h2_jobs>0
               THEN greatest(h2_rate-h1_rate,0)*h2_jobs END AS excess_bad_job_proxy
 FROM rates JOIN volume USING(dealer_code)
)
SELECT /* Q3 */ dealership_name,round(100*h1_rate,1) AS h1_pct,round(100*h2_rate,1) AS h2_pct,
       n_h1,n_h2,h2_jobs,round(excess_bad_job_proxy) AS excess_bad_job_proxy_h2,
       round(excess_bad_job_proxy*0.10*2*revenue_per_job,-3) AS h2_cohort_12m_revenue_proxy_low_aud,
       round(excess_bad_job_proxy*0.25*2*revenue_per_job,-3) AS h2_cohort_12m_revenue_proxy_mid_aud,
       round(excess_bad_job_proxy*0.40*2*revenue_per_job,-3) AS h2_cohort_12m_revenue_proxy_high_aud
FROM eligible ORDER BY h2_cohort_12m_revenue_proxy_mid_aud DESC NULLS LAST LIMIT 8;

-- Q4: DESCRIPTIVE rating/sentiment alignment, not an accuracy test against human labels.
-- Middle band includes fractional normalised ten-point scores; unrated comments stay visible.
SELECT /* Q4 */ CASE WHEN rating_1to5 IS NULL THEN 'unrated'
            WHEN rating_1to5<=2 THEN 'rated low (<=2)'
            WHEN rating_1to5>=4 THEN 'rated high (>=4)' ELSE 'rated middle (2<score<4)' END AS rating_band,
       ai_status,ai_sentiment,count(*) AS responses
FROM accepted WHERE has_comment GROUP BY ALL ORDER BY rating_band,responses DESC;

-- Q1c: Negative-rating drivers. Both strict-negative and negative-or-mixed polarity are explicit.
-- The bridge already excludes failed/stale AI via the Gold model's current-text hash check.
WITH denominator AS (
 SELECT department,count(*) FILTER(WHERE negative) AS all_negative_rated,
        count(*) FILTER(WHERE negative AND ai_status='success') AS ai_enriched_negative_rated
 FROM accepted GROUP BY department
), counts AS (
 SELECT f.department,b.theme_id,
        count(DISTINCT f.response_id) FILTER(WHERE b.theme_polarity='negative') AS strictly_negative_mentions,
        count(DISTINCT f.response_id) AS negative_or_mixed_mentions,
        count(DISTINCT f.response_id) FILTER(WHERE f.ai_needs_review) AS review_flagged_mentions
 FROM accepted f JOIN gold.bridge_feedback_theme b USING(response_id)
 WHERE f.negative AND b.theme_polarity IN('negative','mixed') GROUP BY f.department,b.theme_id
)
SELECT /* Q1c */ c.*,d.all_negative_rated,d.ai_enriched_negative_rated,
       round(100.0*c.negative_or_mixed_mentions/nullif(d.all_negative_rated,0),1) AS pct_of_all_dept_negatives,
       round(100.0*c.negative_or_mixed_mentions/nullif(d.ai_enriched_negative_rated,0),1) AS pct_of_enriched_dept_negatives
FROM counts c JOIN denominator d USING(department)
QUALIFY row_number() OVER(PARTITION BY c.department ORDER BY negative_or_mixed_mentions DESC,theme_id)<=5
ORDER BY c.department,negative_or_mixed_mentions DESC;

-- Q2c: Same cohort and same rating-negative/polarity definition. Dated-only; coverage denominators shown.
WITH denominator AS (
 SELECT count(*) FILTER(WHERE half='H1') AS h1_enriched_negative_rated,
        count(*) FILTER(WHERE half='H2') AS h2_enriched_negative_rated
 FROM accepted WHERE negative AND ai_status='success' AND response_date IS NOT NULL
   AND dealer_code IN(SELECT dealer_code FROM worsening_four)
), counts AS (
 SELECT b.theme_id,count(DISTINCT f.response_id) FILTER(WHERE f.half='H1') AS h1_mentions,
        count(DISTINCT f.response_id) FILTER(WHERE f.half='H2') AS h2_mentions
 FROM accepted f JOIN gold.bridge_feedback_theme b USING(response_id)
 WHERE f.negative AND b.theme_polarity IN('negative','mixed') AND f.response_date IS NOT NULL
   AND f.dealer_code IN(SELECT dealer_code FROM worsening_four)
 GROUP BY b.theme_id
)
SELECT /* Q2c */ c.*,d.*,
       round(100.0*c.h1_mentions/nullif(d.h1_enriched_negative_rated,0),1) AS h1_driver_pct,
       round(100.0*c.h2_mentions/nullif(d.h2_enriched_negative_rated,0),1) AS h2_driver_pct
FROM counts c CROSS JOIN denominator d ORDER BY h2_driver_pct-h1_driver_pct DESC;
