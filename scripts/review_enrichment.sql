-- Attach data/enrichment_viewer.duckdb once; execute queries in the SQL editor.
-- Fill data/ai_review_sample.csv independently before inspecting predictions below.
SELECT sentiment, count(*) AS comments FROM enrichment_viewer.silver.ai_enrichment GROUP BY sentiment;

SELECT a.response_id, a.sentiment, a.themes_json, a.has_unmasked_name,
       a.needs_review, a.status, a.human_review_status
FROM enrichment_viewer.silver.ai_enrichment a ORDER BY a.response_id;

-- Restricted local review of the name flag and proposed replacement; do not export text.
SELECT a.response_id, f.comment AS masked_source_comment, a.proposed_comment
FROM enrichment_viewer.silver.ai_enrichment a
JOIN enrichment_viewer.silver.feedback f USING (response_id)
WHERE a.has_unmasked_name;
