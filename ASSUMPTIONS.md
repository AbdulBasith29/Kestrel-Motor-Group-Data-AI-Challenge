# Mapping and interpretation assumptions

An observed label is evidence; its business meaning remains an assumption until confirmed. Preserve raw values and the mapping version in the future standardized dataset. The investigation notebook currently inventories sources and does not apply these department mappings.

## A001 — Frankston department aliases

Recorded: 27 October 2026. Status: **Provisional — awaiting business confirmation**.

Evidence: `feedback/Frankston_CX_tracker.xlsx`, worksheet `Tracker`, area column. Inspection found the following labels after trimming whitespace and ignoring case. Repeated `Area` headers, blank rows and totals are not departments and must be classified separately.

Proposed mappings:

- `workshop`, `service dept`, `service`, `svc` → canonical department **Service**.
- `sales`, `new cars`, `used cars` → canonical department **Sales**.
- `parts`, `parts counter`, `p&a`, `parts & accessories` → canonical department **Parts**.

Preservation rules:

- Retain the exact source area label as `department_raw`, plus source file, sheet and row lineage.
- Retain **New** and **Used** as sales subtypes when explicitly stated by `New Cars` or `Used Cars`. Generic `Sales` does not establish a subtype; leave it unknown.
- Record the applied rule/version with the standardized value.
- Flag unknown labels for review; do not guess from customer comments or silently map them to an existing department.

Rationale: the brief describes sales, service and parts as the group-level departments. These labels plausibly name those functions or their subcategories, but the workbook does not provide a business glossary.

Validation required: ask the dealership/data owner whether `Workshop` belongs wholly to Service; whether new/used-car feedback belongs in Sales; and whether P&A and the parts counter share the Parts reporting boundary. Confirm aliases per source before extending this rule to other dealerships. No owner confirmation has been obtained.

Risk: grouping operationally distinct teams could distort department comparisons and assign complaints to the wrong owner. Keep this assumption visible in the eventual report and assess any material changes if the business confirms a different mapping.

Implementation acceptance checks: every observed alias maps as documented; case/whitespace normalization preserves the original label; explicit sales subtypes survive; blank/header/total rows are excluded by row-classification rules; and previously unseen labels produce a review issue. These checks are planned, not yet implemented.

## A002 — Missing customer ratings and independent AI text enrichment

Recorded: 27 October 2026. Status: **Agreed analysis policy — implementation pending**. This policy is distinct from the unconfirmed business aliases in A001.

Observed evidence: `feedback/Tamworth.xlsx`, worksheet `Sheet1`, has 143 feedback rows excluding the header. Ten dated rows have blank `HOW WAS IT` values; eight of those have nonblank `COMMENTS`. The affected one-based source rows are 15, 29, 34, 46, 56, 90, 110, 122, 135 and 139. The claim that every feedback response has a customer rating is therefore false. A populated rating is not automatically valid: its value, scale and direction require separate validation.

Agreed handling:

- Preserve the response and its source lineage. Keep the customer rating null when absent; do not infer or impute a numeric customer score from the comment.
- Record a missing-rating quality flag. Missing rating alone does not require discarding a potentially useful comment; other validation rules still apply.
- Exclude missing or invalid ratings from rating-based KPI numerators and denominators. Report the valid-rating denominator and missing/invalid counts alongside each rating KPI.
- Analyse nonblank comments separately for sentiment and themes, including comments from responses without ratings. Do not infer sentiment for the two Tamworth rows missing both rating and comment.
- Store AI-derived sentiment/themes in separate fields or an enrichment table, never in the customer-rating field. Identify the derivation method, model/version, prompt version, processing time and source feedback key.
- Allow mixed, unclear and abstained classifications. Any model confidence is a model output, not a calibrated probability unless evaluated as such. Make uncertainty and review status explicit.
- Mask personal information before sending text to an AI provider or exporting it. Production masking and AI enrichment have not been implemented yet.

Verification planned: human-review all eight commented Tamworth cases plus a representative sample of rated comments, including mixed and sarcastic examples; record disagreements and revisions. Assess sentiment/theme performance against human labels rather than assuming the customer rating is sentiment ground truth. Acceptance checks must ensure that missing scores remain null after enrichment and AI-derived fields never enter customer-rating KPIs.

Business interpretation: text-derived sentiment provides additional evidence about feedback; it cannot establish the numerical rating a customer would have selected. Any later sentiment KPI must have its own definition, denominator and AI-quality limitations.
