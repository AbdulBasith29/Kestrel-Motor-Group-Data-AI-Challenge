# Kestrel Motor Group: what's driving negative customer feedback

## The answer

- **Service is the problem.** Service accounts for 1,306 of the 1,579 negative responses (83%) and is negative 27% of the time. Parts is at 16% and Sales at 11%.
- **Across Service, the drivers are poor communication and waiting.** Among AI-labelled negative Service comments, 38% complain about updates and follow-up, and 35% about waiting, booking or scheduling. Repair quality (18%) and price (17%) come well behind.
- **Four sites got much worse in the second half of the year, while the rest stayed flat.** Parramatta (18% → 37% negative), Dandenong (15% → 34%), Bendigo (10% → 29%) and Liverpool (14% → 29%). Together their negative share roughly doubled, from 15.5% in Oct–Mar (105 of 679) to 33.4% in Apr–Sep (247 of 739). It peaked at 42% in August and eased to 30% in September. The other 20 dealerships moved from 20.8% to 22.4%. Monthly samples at the four are about 100–155, so a single month moves by roughly ±8 points. I picked these four because they rose, so read this as a description, not a test.
- **At those four sites, booking and wait complaints grew most.** They rose from 32% to 42% of negative comments. This lines up with Dandenong's new online booking system going live on 5 May (noted in its May feedback sheet) and with Bendigo absorbing Shepparton's customers after it closed on 31 Mar.
- **Focus on Dandenong and Parramatta Service first.** They hold more than half of the estimated revenue exposure: about **$660k of $1.17M** across the top 8 sites (range $0.47M–$1.87M depending on churn).

![Four sites drove the rise in negative feedback](outputs/charts/monthly_trend.png)

**Interactive dashboard:** [Kestrel Motor Group - Customer Feedback on Tableau Public](https://public.tableau.com/app/profile/abdul.basith.mohammed7821/viz/KestrelMotorGroup-CustomerFeedback/KestrelMotorGroupwhatsdrivingnegativefeedback). The story's three dashboards are also in [`tableau/kestrel_cx.twbx`](tableau/kestrel_cx.twbx), with screenshots in the [Dashboard](#dashboard) section.

## Approach

```
52 dealer files ──> Bronze ──────────────> Silver ──────────────────────> Gold (dbt) ──> CSV export ──> Tableau
 (CSV / Excel,       mapped text + lineage,    one row per response,          facts, theme bridge,
  every sheet)       names/contacts masked  1–5 rating, flags, DQ rules    monthly revenue, tests
                     before storage              │
                                                 └─> Gemini: sentiment + themes on masked comments
                                                     (cached, versioned, checked against my labels)
```

- **DuckDB** gives me one local file with SQL and no server for an assessor to set up.
- **YAML source config** (`config/sources.yml`) holds every per-dealer rule in one readable place: sheets, header rows, date formats, rating scales and aliases.
- **dbt** builds Gold and publishes only if its 49 tests pass. Revenue joins at its own monthly grain, never through the multi-theme bridge.
- **Why not just pandas?** My first draft was plain pandas (`src/first_draft/`) and gave the same 7,089 rows. For a one-off answer that would have been enough. I moved to DuckDB, YAML and dbt so the per-dealer rules live in config rather than code, and a new file or a changed rule reruns with tests instead of a notebook edit.
- **Gemini** labels sentiment and themes. I tried a local Ollama model first, but it was too slow for the full run. The API cost was about US$1.94.

### Target schema

One row per customer response (`silver.feedback`, carried into `gold.fct_feedback`). The question is about responses by dealer, department and month, so that's the grain. Every clean value sits next to the raw value it came from, and nothing is deleted: rows are excluded by flag, so every decision can be traced back to a file, sheet and row.

| Column | What it holds | Why |
|---|---|---|
| `response_id` | Hash of source file, sheet and row | No natural key exists; this one is stable across reruns |
| `dealer_code` | Code from `dealerships.csv` | Files name sites inconsistently; the code is the join key to revenue |
| `date` / `date_raw` | ISO date, null if unknowable / original text | Dates arrive in several formats; raw kept to audit parsing |
| `department` / `department_raw` | Sales, Service or Parts / original label | Labels like "workshop" and "P&A" map to three owners |
| `rating_1to5` / `rating_raw`, `rating_scale` | One comparable scale, 5 = best / original value and scale | Geelong reverses, Ringwood is out of 10, Tamworth is Bad/OK/Good |
| `negative` | Rating ≤ 2; null if unrated | The KPI; missing ratings are never imputed from text |
| `comment` | Masked text, Silver only | Needed for AI themes; never reaches Gold or Tableau |
| `source_file`, `source_sheet`, `source_row`, `flags`, `in_analysis` | Lineage and quality flags | Excluded rows stay visible with a reason |

AI output lives in its own table (sentiment, themes, model and prompt version) keyed by `response_id`, so it can never overwrite a customer's rating.

## Data quality: what I found and what I did

All 7,432 physical rows across the files reconcile: **7,116 land in Bronze and 7,089 responses go into the analysis**, after removing headers, summary and total rows, non-responses, test entries and probable duplicates. Of those, 7,079 have a valid rating. This matches my first pandas draft (`src/first_draft/`) row for row. Every rule's pass/fail counts are in [`outputs/dq_results.csv`](outputs/dq_results.csv).

- **Removed (27 rows):** 14 notes, banners and monthly total rows; 9 exact duplicates; 4 staff test entries.
- **Flagged but kept:** 6 Shepparton dates with a year typo (corrected), 10 undated responses (left out of monthly trends), 10 unrated responses (left out of rating KPIs) and 1,728 with no comment (rating only, nothing to theme).

| Source | Problem | What I did |
|---|---|---|
| Geelong | Rating scale direction reverses between 2025 and 2026 | Reversed 2025 so 5 = best everywhere |
| Ringwood | Template and 10-point scale change mid-sheet | Rescaled linearly to 1–5, kept the raw score |
| Bendigo / Tamworth / Ballarat | Stars, Bad/OK/Good, text labels | Explicit mappings to 1–5 |
| Penrith | June tab is a copy of July | Counted once as July; June treated as missing |
| Chermside | Two "FINAL" Q1 files, v2 has 6 extra rows | Used v2 only |
| Toowoomba | Q4 summary counts, not responses | Excluded from response-level analysis |
| Southport | A tab of 8 Google reviews copied in by staff, dated only "a month ago" | Excluded: public reviews rather than feedback-log responses, and they can't be dated. Southport's 253 logged responses are all in |
| Hunter Motors | Not in the dealer list | Mapped to Newcastle (NSW05) and **flagged as an assumption** |
| Shepparton | Closed 31 Mar 2026; 6 rows misdated to 2026 | Kept up to closure, corrected and flagged the dates, left out of "where to focus" |
| Liverpool / North QLD / Wollongong | US month-first dates, Excel serials, `dd-Mon-yy` | Per-source date formats |
| Chatswood / Wollongong | Semicolon delimiter, cp1252 encoding | Per-source read settings |
| Frankston | Repeated header blocks and "Total" rows | Header detection plus a total-row rule |

- **Negative** means a normalised rating of 2 or below.
- **Missing ratings stay null.** I never imputed them from comment text, and AI sentiment is a separate field.
- **Duplicates** are a heuristic, because there's no natural key: same dealer, date, department, rating and comment. This can drop genuinely separate identical responses, so each duplicate decision keeps its lineage.

**Privacy:** I treated all personal data as real. Name and phone columns are read in memory only to build masks and are never stored. Known customer and staff names in comments are masked as [CUSTOMER] and [STAFF] before anything is written (190 staff names, 58 emails, 156 phones and 486 regos). Raw data, databases and labels stay out of Git, and Gold and Tableau carry no comment text. Masking missed some staff first names, so a few reached Gemini, which flagged 663 comments as possibly still containing a name. That's a gap I own. With more time I'd run NER masking (for example Presidio or spaCy) before any external call, or use a local model.

## Business answers

**1. Drivers by dealership and department.** Service negative share is highest at Parramatta (36%), Dandenong (35%), Chatswood (31%) and Essendon (30%). Sales and Parts are low almost everywhere. The main theme in each department:

| Department | Negative | Top negative themes (share of AI-labelled negative responses; a comment can carry several, so shares add to more than 100%) |
|---|---|---|
| Service | 27% | Communication/follow-up 38%, waiting/scheduling 35%, repair quality 18%, price 17% |
| Parts | 16% | Parts availability 55%, communication 39%, waiting 32% |
| Sales | 11% | Sales process 57%, communication 30%, staff 20% |

**2. Change over the year.**

![Negative share, first half vs second half](outputs/charts/h1_vs_h2_by_dealer.png)

![At the four worsening sites, booking and wait complaints grew most](outputs/charts/worsening_site_themes.png)

Four sites stand out, and Geelong improved (27% → 19%). At the four worsening sites, waiting and booking complaints grew from 32% to 42% of negatives. Parts availability also grew (4% → 16%), but Gemini over-tags this theme, so I treat it as a lead to check rather than a finding. More responses don't explain the rise: at the four sites, Service responses went from 2.4% to 2.7% of service jobs (2.4% both halves elsewhere), so the change is in what customers said, not how many replied.

**3. What it's worth.** I estimate the revenue exposure from the extra negative Service experiences in Apr–Sep, above each site's own Oct–Mar rate:

> exposure = (H2 negative rate − H1 negative rate) × H2 service jobs × churn × 2 jobs a year × revenue per job
>
> Dandenong at 25% churn: (46.6% − 20.0%) × 6,096 jobs ≈ 1,619 extra negative jobs → × 25% ≈ 405 lost customers → × 2 × $411 ≈ **$333k**

| Site | Service negative H1 → H2 | Exposure at 10% / 25% / 40% churn |
|---|---|---|
| Dandenong | 20% → 47% | $133k / **$333k** / $533k |
| Parramatta | 23% → 49% | $131k / **$328k** / $526k |
| Toowoomba* | 21% → 29% | $40k / $99k / $158k |
| Ipswich | 22% → 33% | $37k / $93k / $149k |
| Liverpool | 19% → 30% | $35k / $88k / $141k |
| Bendigo | 15% → 33% | $32k / $80k / $129k |
| Newcastle | 21% → 31% | $31k / $78k / $124k |
| Ringwood | 20% → 25% | $28k / $71k / $114k |
| **Top 8 total** | | **$0.47M / $1.17M / $1.87M** |

\*Toowoomba's Oct–Dec responses exist only as a summary sheet, so its H1 baseline is Jan–Mar only (76 Service responses).

This is potential exposure, not proven loss. It assumes the feedback sample represents all service jobs, that each negative job is one customer, and that a lost customer would have brought two jobs in the next 12 months. Revenue per job and job counts come from `monthly_revenue.csv`. Full table: [`outputs/business_answers/q3_value_at_risk.csv`](outputs/business_answers/q3_value_at_risk.csv).

## Dashboard

The [published Tableau story](https://public.tableau.com/app/profile/abdul.basith.mohammed7821/viz/KestrelMotorGroup-CustomerFeedback/KestrelMotorGroupwhatsdrivingnegativefeedback) has three sections: **What's driving it**, **Where to focus** and **Can we trust it**. It reads the Gold reporting export only, with no names and no comment text.

| View | What it shows |
|---|---|
| **CX overview** | KPI strip, monthly trend (worsening four vs the rest), themes at the worsening four, revenue at risk by site, negative share by department |
| **Dealer investigation** | Dealer × department heatmap that drills into a monthly trend and themes for the clicked cell, plus H1 vs H2 change for all 24 sites |
| **Data quality** | Missing ratings and dates, the Hunter → Newcastle assumption, AI coverage and errors, DQ rule results |

- **Interactive:** state and department filters, click-to-filter on the department bars, heatmap drill-down, and a churn slider (10–40%) that recalculates revenue at risk. Tooltips show the counts behind every percentage.
- **Reconciliation:** the KPIs match the Gold baseline (1,579 negative of 7,079 rated, 22.3%). The monthly views leave out 10 undated responses, which doesn't change the rate.
- **Refresh:** see [`docs/ENGINEERING.md`](docs/ENGINEERING.md#tableau-refresh). The public story doesn't update when the local pipeline reruns.

![CX overview](outputs/tableau/cx_overview.png)

![Dealer investigation](outputs/tableau/dealer_investigation.png)

![Data quality](outputs/tableau/data_quality.png)

## Recommendations

1. **Fix booking at Dandenong and Parramatta now.** Dandenong's new online booking system went live on 5 May, and its later complaints describe lost bookings, double-booked slots and appointments missing from the workshop system. Parramatta's sheet gained a booking-reference column in May and its comments mention a new system, but there's no note confirming a change there, so check that first. These two sites hold more than half the exposure.
2. **Proactive service updates group-wide.** Communication is the top Service complaint at every site. An SMS at drop-off, a mid-job update and a callback rule when a job runs late are cheap to try.
3. **Check Bendigo capacity.** Its rise starts when Shepparton's customers were redirected there. Compare booking lead times and staffing against volume.
4. **Track it monthly.** Alert when a site's negative share runs 10 pts above the group for two months running. On the monthly trend, the four sites together crossed that line in June (37% vs 23%).
5. **Standardise the feedback template.** One sheet layout, a 1–5 scale, ISO dates and the dealer code would remove most of the cleaning effort shown above.

## Can the AI be trusted?

**The headline numbers don't depend on it.** Negative share, the site trends and the revenue exposure all come from customer ratings. Gemini only answers *why*, through the theme shares, so an AI error changes the explanation, not the size of the problem.

- **Human check.** I labelled 49 of a 50-comment sample (all dealerships, departments and rating bands) before seeing any predictions.
  - Sentiment: 46/49 agree (94%).
  - Themes: at least one theme matches on 42/46 (91%). To score themes, my free-text labels were mapped onto Gemini's theme list with AI help, and I left out 3 rows where the mapping was ambiguous. Across all themes, 81% of Gemini's tags were right and it found 90% of mine.
  - The two themes the answer rests on hold up best: Gemini found 15 of my 17 communication labels and 8 of my 9 waiting labels, with 1 and 2 extra tags.
  - Leftover names: 48/49 agree.
- **Rating alignment (not independent accuracy).** 91% of 1–2 ratings come back negative and 92% of 4–5 ratings come back positive. Only 10 of 3,145 high ratings were called negative.
- **Where I don't trust it.** `parts_availability` was tagged 3 times in the sample and wrong every time (it fires when the parts team is just mentioned), so the Parts finding is a lead, not a conclusion. Staff and vehicle themes were also over-tagged (3 extra each). It struggles with very short comments.
- **Guardrails.** Gemini returns JSON with fixed theme IDs, its output is stored apart from the rating and can never overwrite it, and every result is cached with its model and prompt version. Each label is tied to a hash of the comment, so if a comment changes its old label drops out. Coverage: 5,358 comments labelled, 2 provider errors and 1 held back.
- **What that means.** For stable per-theme numbers I'd want closer to 100 labelled comments; I was short on time, so I stopped at 49. With a small, deliberately mixed sample, treat the theme shares (38% communication, 35% waiting) as directional. The ranking is solid; the exact percentages are not.

Details: [`outputs/gemini_evaluation.json`](outputs/gemini_evaluation.json).

## How I used AI to build it

- **Who did what.** I wrote the implementation guide and architecture, the initial Silver step and the original business-answer SQL, and made every data and business decision (schema, cleaning rules, negative = 2 or below, the theme list, the sizing method). Codex built most of the ingestion, masking, enrichment, Gold models and tests from that guide. Claude reviewed the work against the brief and challenged design choices. Gemini labelled the comments.
- **How I prompted.** I asked for checks, not answers: "inspect every file and every sheet, not just the first, and list anything that would break a simple concat", then checked its findings against all 52 files myself. For the evaluation: "leave the human label columns blank; I label first, then compare."
- **Where it was wrong, and how I caught it.**
  - *Masking leaked.* I asked it to show me what the masking missed. It had missed names in prose, landlines and unlabelled registrations, so I had it rebuilt with tests.
  - *Name repair damaged text.* I checked ten Ballarat examples and found eight where the proposed fix hit the wrong words and left the name visible. All 663 proposals were thrown out and redone with exact-string matching.
  - *The test-row filter removed real customers.* Matching "test" anywhere caught 17 genuine comments ("test drive", "battery test"). I read the flagged rows and narrowed it to 3.
  - *The sizing formula double-counted.* I challenged an extra ×2 in the exposure calculation; removing it halved the estimate.
- **How I checked it.** All 7,432 physical rows are accounted for, and the 7,089 analysis rows match my separate pandas first draft row for row. Gold publishes only if its 49 dbt tests pass. I worked the exposure for Dandenong by hand (above) to confirm the SQL.
- **What I kept for myself.** What counts as negative, which rows to exclude, the Hunter → Newcastle assumption and the final recommendations. These are judgement calls the data can't settle, so I didn't hand them to a model.

Full log: [AI_USAGE_LOG.md](AI_USAGE_LOG.md).

## Beyond the brief

The brief doesn't assess code polish, so these are optional. I built them to show how this would run day to day. Detail is in [`docs/ENGINEERING.md`](docs/ENGINEERING.md).

| Extra | Why | Limit |
|---|---|---|
| dbt Gold with 49 tests | Bad data can't reach the dashboard | Runs locally only |
| Prefect flow (`python flows/pipeline.py`) | One command runs every step in order, with run history | No scheduling or alerts |
| File watcher (`python flows/watch.py`) | Reruns when a dealer drops in a new file | Reprocesses the batch, not just new rows |
| Dealer history (SCD2) | Tracks changes to the dealer list, such as closures | History starts at the first run |

## Production next steps

- **Privacy:** NER masking before any external AI call, and a keyed customer hash if repeat-customer analysis is needed. Secrets in a vault.
- **Ingestion:** row-level incremental loads and run IDs instead of full rebuilds.
- **Orchestration:** scheduled runs with failure alerts.
- **AI operations:** pinned model and prompt versions, a fresh labelled sample each quarter, and a drift check on sentiment-vs-rating agreement.
- **Reporting:** a live Tableau connection or scheduled extract refresh instead of manual CSV exports.

## How to run

Tested with Python 3.14 on Windows. Obtain the assignment source data separately and put the `feedback/` and `reference/` folders in the project root (both are gitignored). Without the optional Gemini run, Gold still builds the rating and revenue reports with zero AI coverage.

```bash
pip install -r requirements.txt
python flows/pipeline.py                 # full batch run, Gemini off
# python flows/pipeline.py --enrich --budget-usd 5   # paid Gemini run; needs GEMINI_API_KEY in .env
python scripts/run_business_answers.py   # writes data/business_answers/; copy to outputs/business_answers/ to refresh the charts
python analysis/make_charts.py           # README charts (needs matplotlib)
python scripts/prepare_tableau.py        # Tableau CSVs in tableau/extracts/
python -m unittest discover -s tests     # tests
```

Individual steps (`src/bronze.py`, `src/silver.py`, `src/gold.py`) can also be run on their own. Assumptions and their impact: [ASSUMPTIONS.md](ASSUMPTIONS.md). Source investigation: [`scripts/investigation.ipynb`](scripts/investigation.ipynb) (outputs are stripped because they print source rows with personal data; the findings are in the Data quality table above).
