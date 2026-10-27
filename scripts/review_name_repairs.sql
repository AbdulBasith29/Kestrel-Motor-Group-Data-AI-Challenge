-- Attach data/gemini_review_fixed.duckdb, then run this file in the SQL editor.
SELECT proposal_status, count(*) AS comments
FROM gemini_review_fixed.silver.name_redaction_review GROUP BY proposal_status;

-- Revisit the applicant's first ten examples with exact-name proposals.
SELECT f.source_file,f.source_row,f.comment,n.proposed_comment,n.proposal_status
FROM gemini_review_fixed.silver.feedback f
JOIN gemini_review_fixed.silver.name_redaction_review n USING(response_id)
WHERE f.source_file='Ballarat - Customer Satisfaction.xlsx'
  AND f.source_row IN (4,14,16,17,18,26,31,42,43,51)
ORDER BY f.source_row;

-- Unresolved or conflicting name detection remains for human review.
SELECT f.source_file,f.source_row,f.comment,n.proposal_status
FROM gemini_review_fixed.silver.feedback f
JOIN gemini_review_fixed.silver.name_redaction_review n USING(response_id)
WHERE n.proposal_status <> 'literal_match_pending_review'
ORDER BY f.source_file,f.source_row;
