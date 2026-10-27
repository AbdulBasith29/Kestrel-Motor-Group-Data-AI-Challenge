# Your independent 50-comment review

Open data/gemini_review_50.csv locally. This is a fresh diagnostic sample spanning all 24 dealerships and Sales, Service and Parts. It has 14 low-rating, 10 middle-rating, 22 high-rating and four missing-rating comments. Previously displayed pilot rows and the ten Ballarat examples are excluded. Two known failed-model cases are included. Neither predictions nor source ratings are shown in the file.

Read each masked_comment and fill:

- human_sentiment: positive, negative, mixed, neutral or unclear. Mixed means both praise and complaint; neutral means factual without evaluation; unclear means insufficient meaning.
- human_themes: up to three theme IDs, separated by |; use none when no theme is supported.
- human_has_unmasked_name: true or false. Existing [STAFF]/[CUSTOMER]/[PERSON] tags are already masked; identify remaining visible person names, not vehicle/place names.
- review_notes: optional explanation of ambiguity. Keep the source comment unchanged so its hash remains verifiable.

Allowed theme IDs:

- communication_follow_up: updates, explanations, callbacks.
- waiting_time_scheduling: delays, queues, appointments.
- workmanship_repair_quality: diagnosis, repairs, repeat faults.
- staff_service: conduct, courtesy, helpfulness. A staff name by itself does not establish this theme.
- pricing_value: charges, prices, value.
- sales_process: buying, finance, handover, trade-in.
- parts_availability: stock and parts orders.
- vehicle_product: vehicle features or condition.
- other: a supported topic outside these categories.

Example using invented feedback: “The team were lovely, but I waited two hours.” Overall sentiment mixed; themes staff_service|waiting_time_scheduling; unmasked-name flag false.

Label before opening model predictions. All 50 human-label rows were left blank by the AI agent. This file contains restricted comment text and stays outside Git. Leave a note if uncertain; do not copy the model's answer to make it agree.

After saving, run from the project root:

```powershell
python src/evaluate_enrichment.py --provider gemini --labels data/gemini_review_50.csv
```

The evaluator reports sentiment agreement, theme precision/recall/exact match and missed/false name flags. It also reports all_reviewed_fields_exact_count: the number of rows where overall sentiment, the complete theme set and remaining-name flag all match your labels. A failed model response counts as incorrect. This does not score per-theme polarity, the proposed masking text or person roles; those need their separate review. Four evaluator tests passed, including agreement on every reviewed field and disagreement despite correct sentiment.

Report the result as agreement on this 50-comment diagnostic sample. Because it deliberately spreads across rating bands and includes known failures, its unweighted score is not an estimate of accuracy across all feedback. If rules/prompts are changed after seeing disagreements, retain a new unseen sample for subsequent evaluation. No performance result exists until you supply the labels.


## Partial-credit scoring refinement

Gemini supports mixed directly; do not collapse it into another class. Use unclear when meaning/sentiment is genuinely insufficient or ambiguous, rather than forcing a guess. One minute per comment is a practical guide, not a requirement to invent certainty; record doubts in review_notes.

Primary theme comparisons now include micro precision/recall/F1, per-theme hits/extra predictions/misses, and the fraction of human-themed comments with at least one matching theme. Comments labelled none are excluded from that last denominator and assessed separately by exact match. Keep exact-set and all-reviewed-field agreement as stricter diagnostics; a single overlapping theme alone can hide extra incorrect themes or missed topics.

Save as CSV UTF-8 (UTF-8 with BOM is also supported). Encoding alone does not change a text hash if decoding preserves the same characters; Excel edits, substitutions or character loss can. Leave masked_comment verbatim.

After all rows are labelled, the evaluator writes data/gemini_disagreements.csv for restricted review. It includes human/model labels and missed/extra themes. No disagreement file is generated during partial labelling, so predictions stay hidden. Select three to five useful disagreements and verify masking before including any comment excerpt in the README. No private comment text is published automatically. Six synthetic evaluator tests pass, including partial overlap with extra/missed themes and the no-theme denominator.


## Pasted label import and scoring

The applicant supplied 49 labels in chat; they were imported without changing any masked_comment. Original wording is preserved in data/human_labels_as_supplied.csv and human_themes_raw. The untouched earlier review file is backed up locally. Response R6e9a5aef6c3a2b7a4027b5bd was not supplied and remains blank.

The raw theme vocabulary differs from the fixed model categories. config/human_theme_crosswalk.yml records an AI-assisted, not-yet-confirmed translation, including dropped context-only descriptors and unresolved process labels. It was written before model predictions were queried for this comparison. Three rows are excluded only from theme comparisons; all 49 sentiment and name labels are scored. Seven evaluator tests pass, including preservation of component denominators when theme mapping is unresolved. Do not interpret translated themes as independently human-authored canonical gold.

Run python src/evaluate_enrichment.py --provider gemini --labels data/gemini_review_50.csv --export-disagreements to reproduce the partial evaluation and restricted disagreement file without filling the missing label. Explicit export is used because the applicant ended this label submission with 49 rows. No additional model calls or source-data edits are needed.
