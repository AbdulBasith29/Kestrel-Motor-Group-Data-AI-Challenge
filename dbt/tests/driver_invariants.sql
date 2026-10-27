select dealer_code,department,month,theme_id from {{ ref('mart_theme_drivers') }}
where negative_rated_driver_mentions>negative_rated_with_ai
 or strictly_negative_rated_driver_mentions>negative_rated_driver_mentions
 or review_flagged_driver_mentions+unflagged_driver_mentions<>negative_rated_driver_mentions
 or driver_share_of_enriched_negative_feedback not between 0 and 1
