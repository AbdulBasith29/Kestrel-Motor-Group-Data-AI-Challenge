# Tableau workbook and refresh

The published story link is in the project README. The packaged workbook is `tableau/kestrel_cx.twbx`; the editable workbook is `tableau/kestrel_cx.twb`. Screenshots are in `outputs/tableau/`.

## Rebuild data

1. Run `python flows/pipeline.py` with the usual working database; this rebuilds Gold and writes fresh business answers to `data/business_answers/`.
2. Copy `data/business_answers/Q3.csv` to `outputs/business_answers/q3_value_at_risk.csv` before preparing extracts. This is the labelled H2-cohort sensitivity, not observed loss.
3. Run `python scripts/prepare_tableau.py`.
4. Open the workbook in Tableau, refresh or reconnect its data sources, review the results, save a new package and republish. Local CSV updates do not refresh the public story or an older packaged workbook automatically.

## Current data sources

- `feedback_monthly.csv`: dealer/department/month counts; calculate negative share as SUM(negative_responses)/SUM(rated_responses).
- `theme_drivers.csv`: dealer/department/half-year/theme counts; for a selected theme use SUM(negative_theme_mentions)/SUM(negative_responses_with_ai). The denominator is repeated for each theme: do not sum across theme IDs to produce an overall coverage denominator. Multiple themes can apply to one response.
- `data_quality.csv`: accepted/excluded counts, missing dates/ratings, mapping assumptions and AI coverage. Missing dates and ratings can overlap; do not sum them as unique affected responses.
- `value_scenarios.csv`: hypothetical exposure at assumed 10%, 25% and 40% churn. Keep assumptions visible.

## Checks before republication

Full Gold: 7,089 responses, 7,079 rated and 1,579 negative. Monthly extract: 7,079 dated responses, 7,069 rated and 1,576 negative. Ten undated responses explain the difference; three of those have negative ratings. Ratios must use matching numerator/denominator populations.

Confirm counts in tooltips, distinguish the full-period headline from dated charts, and check the third trust page and all filters. The public pages are a reporting deliverable; automated public refresh is not configured. The workbook generator uses local absolute paths, so reconnect data sources after relocating the project.
