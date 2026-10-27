# AI usage and verification log

This log records how AI assisted the assignment, what was checked, errors found and corrective decisions. Entries describe completed actions separately from planned work. No raw customer identifiers, API keys or unredacted feedback are included.

## Assignment permissions and privacy boundary

Checked against the supplied `PS_Data_AI_Assignment.pdf`, pages 1–2, on 27 October 2026.

- The brief explicitly permits AI tools, including coding agents/assistants and LLM use for feedback classification or interpreting messy columns. It also permits external services.
- It says names, contact details and businesses are fictional, while requiring personal information to be handled as if real.
- It requests a brief, honest account of AI use, including where AI was wrong and how its output was verified.
- It does not explicitly prohibit AI inspection of unmasked source files, nor explicitly authorize unrestricted disclosure of personal information. This log therefore does not characterize the inspection as a confirmed breach of an express assignment prohibition, or claim that general AI permission removes the privacy obligation. Any additional employer or service-specific conditions would require separate checking.

**What actually happened:** the AI agent read local source files through tools during structural investigation. Some tool results and workbook previews exposed unmasked source content, including fictional personal identifiers, to this AI-assisted session. Local file processing should not be described as proof that no data entered the AI context. No claim is made about service-provider retention beyond separately checked terms. No Gemini enrichment API run has been performed.

**Limitation and response:** privacy protection was not consistently enforced at the inspection-output boundary. The applicant challenged the masking assurance; the agent inspected its code and demonstrated gaps. The existing preview helper is not a verified production privacy gate. The agreed next step is to restrict preview/export fields, improve redaction, add tests and review remaining exposures before further AI enrichment or export. These corrective checks remain pending; no claim of completed remediation or universal anonymisation is made.

This account preserves the observed facts without reproducing personal values. It records a control limitation and an improvement plan, rather than concealing the exposure or asserting an unverified rule violation.

## Responsibility and decision record

This account is based on the recorded working discussion and verified actions. **Applicant** means the person completing the assignment; **AI agent** means the coding/research assistant. Proposed or agreed design is not described as implemented. The applicant reported manually reviewing all 52 files; this is a self-reported review, not an independently audited review checklist.

### 1. Scope and architecture

- **Applicant:** supplied the assignment context and proposed laptop architecture; chose to work visibly in Antigravity and prioritised completing the assignment over extra infrastructure. The authorship of the earlier architecture diagram is not established here.
- **AI agent:** inspected the ZIP/brief, translated the requested architecture into implementation suggestions and recommended a focused batch baseline before orchestration and reporting.
- **Status:** Python/pandas investigation implemented. DuckDB Bronze/Silver/Gold, YAML mappings, production validation, pytest pipeline coverage, Watchdog, AI enrichment and Tableau remain planned.

### 2. Investigation format and source review

- **Applicant:** brought an in-progress investigation notebook, explained that standalone audit scripts were difficult to present, requested smaller explained cells, and manually compared sources and notebook findings. Noted variations in file periods, worksheets, column names/order, department labels, ratings and available identifiers.
- **AI agent:** generated the initial inspection helpers, inspected the inputs programmatically, restructured the notebook into 32 cells with 15 executable cells, and removed the four redundant scripts after the applicant requested deletion. No claim is made that the applicant independently wrote the agent-generated code.
- **Check:** applicant review complements the agent's all-file/all-sheet structural inventory; it does not replace later row-level validation.

### 3. Canonical schema and primary measures

- **Applicant:** proposed date, department, numeric rating and comments as the core canonical fields; favoured a one-to-five numeric representation over text-only satisfaction labels. Identified optional customer/model fields and argued that customer identifiers should not appear in the end reporting product.
- **AI agent:** proposed adding dealership, internal feedback key, lineage, raw rating/scale/direction, optional sales subtype/model/follow-up and quality flags. Warned that rating conversions can change meaning and must be explicit.
- **Shared design:** retain original values, represent absent ratings as null, and separate normalized values from customer-reported values. A final cross-scale conversion policy, definition of negative feedback, KPI thresholds and denominator rules for the full report are **not yet finalized**. The applicant's preference for numeric ratings is not a completed KPI specification.

### 4. Department and site mappings

- **Applicant:** identified that Workshop/Service Dept/Svc plausibly mean Service; New Cars/Used Cars belong to Sales; and P&A/Parts Counter/Parts & Accessories plausibly mean Parts. Requested that these assumptions be recorded. Proposed broader first-letter regex rules for sites and departments.
- **AI agent:** checked observed labels, proposed preserving sales subtypes and source labels, and explained collisions and unseen-value risks in broad prefix rules. Verified the mixed North Queensland workbook's full and abbreviated site labels and compared them with the reference list.
- **Shared decision:** use reviewed, source-specific alias mappings after case/whitespace normalization; flag unknowns. Applicant accepted the reason for this restriction. Business confirmation of department boundaries is outstanding; see A001 in `ASSUMPTIONS.md`.

### 5. Chermside file versions and source integrity

- **Applicant:** noticed two Q1 FINAL versions, identified the six-row increase, and distinguished overlapping-file deduplication from an SCD requirement.
- **AI agent:** had also identified the overlapping versions in its earlier inspection; verified 112 shared unchanged responses plus six additional responses in v2, excluding headers. Compared all 52 current feedback files with the original ZIP and found no changes.
- **Shared design:** retain both sources and avoid counting shared responses twice. The applicant's observation and agent's earlier finding are both recorded; neither is presented as the sole discovery. Production deduplication is not implemented.

### 6. Dates, rating scales and workbook structure

- **Applicant:** questioned visible Excel serial dates, inspected Ringwood's February template change and score-column shift, and examined the different monthly/annual/department worksheet arrangements. Initially thought some Ringwood scores were absent, then corrected that observation during review.
- **AI agent:** checked actual cell formats and date origin, confirmed that Chermside's serial-date display was a viewer issue, and verified Ringwood's changed header and ten-point scale. Earlier programmatic inspection had already identified Ringwood and Geelong scale changes. Corrected the initial impression that Dandenong contained only October by checking its monthly tabs.
- **Decision/status:** handle schemas by segment/sheet and preserve scale direction. Shepparton closure/date checks and Penrith copied-tab handling remain pipeline work.

### 7. Missing ratings and AI-derived interpretation

- **Applicant:** questioned whether every response had a rating; proposed estimating missing scores from comments; accepted the distinction between an inferred interpretation and a customer-provided score; requested documentation.
- **AI agent:** disproved universal rating completeness with ten dated Tamworth rows missing ratings, eight with comments. Recommended retaining null customer scores and storing AI sentiment/themes independently rather than imputing customer ratings.
- **Shared decision:** preserve unrated responses, exclude missing/invalid ratings from rating KPIs with explicit denominators, and evaluate AI-derived fields separately. See A002 in `ASSUMPTIONS.md`. Policy documented; implementation pending.

### 8. Privacy and verification failure

- **Applicant:** identified names, phone numbers, registrations and email fields as information to exclude from AI/reporting; challenged whether the preview masking actually worked and asked for evidence of misses; explicitly requested an honest AI-error log.
- **AI agent:** authored the preview helper, then inspected and tested its own code in response. Found synthetic failures for names in prose, unlabelled registrations and landlines, plus actual unmasked person-name cells in Noosa's preview. Corrected the applicant's interpretation of `Card given by` as necessarily a customer name; staff interpretation is provisional too.
- **Decision/status:** successful code execution is not proof of privacy. The existing helper must not be used as the sole external-processing/export gate. Full details and limitations appear in AI-001 below; fixes are outstanding.

### 9. Ambiguous dealership identity and summary-only data

- **Applicant:** questioned the meaning of the repeated Ipswich site label, the location of Hunter Motors, and the risks of assigning it to Newcastle; noticed Toowoomba's summary-only layout and absent Sales rows.
- **AI agent:** checked reference identities, described Ipswich as a plausible alias mapping, and floated Newcastle as an unconfirmed candidate for Hunter. Explained how a wrong mapping affects dealership metrics and revenue joins. Proposed a clearly flagged provisional mapping with sensitivity analysis as an alternative to leaving it unresolved.
- **Status:** Hunter-to-Newcastle has not been confirmed, implemented or entered as an agreed final mapping. Keep the uncertainty explicit. Toowoomba aggregate counts must remain distinguishable from individual responses; absence of Sales rows is not evidence of zero Sales feedback.

### 10. Reproducibility and Git checkpoint

- **Applicant:** requested portable setup, clean-environment verification, removal of redundant helpers, and a first GitHub checkpoint; created the repository and reported changing it to private.
- **AI agent:** created dependencies/setup/verifier, ran the clean relocated-kernel test, recorded hashes/results, cleared notebook outputs, reviewed the selected files, connected Git and pushed the first 14-file milestone after authorization. Independently verified private repository visibility and the remote commit.
- **Check/status:** 15 code cells completed without errors; original feedback/reference hashes stayed unchanged. The first commit predates this usage log and the subsequent assumptions documentation; those changes are local and not yet committed.

### 11. AI provider and sequencing

- **Applicant:** chose Gemini as the intended enrichment provider because an API key was already available and local model setup would add work; insisted on finishing DuckDB ingestion/canonical data first; checked that AI analysis remains required by the assignment.
- **AI agent:** compared cloud/local tradeoffs and current data-use terms; recommended redaction, a human-labelled evaluation sample and separate enrichment outputs. Clarified that optional execution of enrichment within the pipeline does not make the assignment's AI deliverable optional.
- **Status:** no enrichment API calls, full-data classification, model benchmark or paid-service configuration verification has been performed. Provider choice does not establish privacy readiness or accuracy.

### 12. Ownership of the next implementation stage

- **Applicant:** owns selection/approval of business definitions, source interpretation, unresolved-assumption decisions, human review labels and final conclusions. The applicant has requested traceable attribution throughout the project.
- **AI agent:** may propose schemas/rules, write code/tests/docs and execute authorized checks. AI-generated code and suggestions require review; agreement with a suggestion is distinct from independent authorship.
- **Next work:** implement and verify ingestion/validation before AI enrichment and business analysis. No completed DuckDB ingestion or canonical clean dataset is claimed.

### Required attribution for future entries

For each material step, record: **task; applicant observation/decision; AI proposal or code contribution; who actually performed verification; evidence and result; disagreement/error and correction; accepted decision; remaining uncertainty; implementation status**. Label joint decisions explicitly and do not imply that planned tests have run or that an AI proposal originated independently with the applicant.


## AI-001 — Preview masking code missed personal information

Ownership: applicant requested and challenged privacy verification; AI agent generated the helper and performed the targeted checks; the limitation and need for corrective work were discussed jointly.

Date: 27 October 2026. Status: **Verified limitation; masking fix and full validation outstanding**.

### Task and AI contribution

An AI coding agent generated the investigation notebook, including `mask_text()` and `safe_preview()` to hide obvious identifiers in displayed examples. The helper uses column-label checks plus regular expressions for emails, Australian mobile numbers and explicitly labelled vehicle registrations. It is a local preview convenience, not a validated production privacy gate.

Key interaction, paraphrased: during manual review of the notebook, the user asked how to verify that the preview helper worked and had not missed personal information. This prompted an explicit inspection and test of the AI-generated masking code rather than relying on successful notebook execution.

### Verification performed and results

The agent tested the existing helper with synthetic strings, then checked an actual local workbook preview. No underlying personal values were printed in the verification report.

- Synthetic email example: masked successfully.
- Synthetic Australian mobile example: masked successfully.
- Synthetic personal name embedded in a comment: remained visible.
- Synthetic registration without a `rego` or `registration` label: remained visible.
- Synthetic landline number: remained visible. The generated phone pattern covered Australian mobiles, not all phone numbers.
- Actual Noosa workbook: all four staff-name cells in the first four response rows of the `Card given by` column remained visible. The helper did not recognise that column as a possible person identifier. This observation does not establish the column's business meaning; interpreting it as staff rather than customer information remains provisional.

The first five checks were targeted synthetic tests, not a complete scan proving those identifier types occur throughout the real dataset. The Noosa result was verified against the supplied workbook. Names embedded in prose were already acknowledged as a limitation in the notebook; that acknowledgement does not make the output safe for external use.

### Error and significance

Successful execution of all notebook cells had established execution reproducibility, **not privacy completeness**. The helper cannot support a claim that every displayed identifier has been removed. Names and contact details can occur in comments, and person-related columns do not always have predictable names. Staff information also needs consideration.

### Decision and next checks

- Do not use the current helper as the sole gate for sending feedback to Gemini or exporting comments.
- Keep raw source files unchanged and restricted; deleting columns from a preview does not anonymise the source data.
- Add explicit expected-output tests for supported identifier types and formatting variants.
- Review identifier columns across every source layout; prefer explicitly selected display/export fields to guessing from column names alone.
- Scan proposed outputs for residual contact details, registrations and known source identifiers, without putting raw matches into shared logs.
- Review restricted local before-and-after examples, including flagged cases, names embedded in prose and unexpected columns. Document residual limitations; automated tests cannot prove universal removal of personal information.

These fixes and dataset-wide privacy checks have **not** been implemented or completed. No full-dataset privacy certification is claimed.

## AI-002 — Notebook restructuring and reproducibility support

Ownership: applicant selected the notebook presentation approach and requested reproducibility; AI agent wrote/restructured the code and executed the verification; applicant performed source review and questioned interpretations.

Date: 27 October 2026. Status: **Execution verified; interpretation remains subject to manual review**.

The AI coding agent reorganised the investigation into explained sections, added a CSV loader and all-worksheet inspection, and created setup instructions, dependency pins and an automated verifier. A fresh virtual environment and real Jupyter kernel successfully executed all 15 code cells in a relocated assignment copy. Input hashes confirmed that all 52 feedback files and both reference files were unchanged. The user is independently reviewing the supplied sources and questioning the findings and design choices.

This verification supports reproducibility of the exploratory code. It does not establish that mappings, privacy handling, deduplication policies or business conclusions are correct. DuckDB ingestion, production validation and AI-based feedback enrichment have not been implemented. Gemini has been discussed as the planned enrichment provider; no feedback-enrichment API run has been performed in this work.


## AI-003 — Fixing default previews after the verified masking failure

Date: 27 October 2026. Status: **Default preview hardening implemented and tested; external text-release gate still pending**. This entry supersedes earlier pending-preview-fix statements without erasing the original failure evidence.

- **Applicant decision:** requested the masking fix after challenging the generated helper and discussing the boundary between restricted raw data and AI/dashboard outputs.
- **AI agent implementation:** added a shared `privacy_preview.py` module; changed the notebook to display only allowlisted structured values and withhold comments, action notes, person/identifier fields (including staff and Noosa's `Card given by`), vehicle/model values, unknown fields and unrecognised values by default. Source data is not rewritten. Added selected email, Australian mobile/landline, registration-format and known-name rules to a separate local-review redactor, without claiming it handles arbitrary text safely.
- **AI agent verification:** authored and ran eleven synthetic regression tests, including source immutability, unknown-field suppression, names in prose and the previous contact/registration misses. Ran the updated notebook through the isolated, relocated real-Jupyter-kernel verifier: all sixteen code cells passed, and all 54 source/reference file hashes stayed unchanged. Checked default identity/text suppression across the currently identified real source header segments; counts and limits are recorded in `reproducibility/privacy-preview-check.json`. No raw source values are included in the check report.
- **Applicant review outstanding:** inspect the changed notebook and synthetic checks. No claim is made that the applicant has independently verified this implementation yet.
- **Remaining limits:** unknown names, addresses or unsupported formats may remain in the optional heuristic redactor. Default preview suppression does not certify every possible input as anonymous, prove header-detection completeness, erase earlier session exposure, or implement a vetted AI/export dataset. Do not use heuristic redaction alone to send text externally.
- **Repository status:** changes are local; no new commit or push was performed for this fix.


## AI-004 — Applicant-directed findings-first notebook presentation

Date: 27 October 2026. Status: **Implemented and execution verified; local changes not committed**.

- **Applicant editorial decisions:** requested a findings table at the top, finding-first section openings, a single privacy-policy statement, plain section titles, technical checks moved out of the narrative, and takeaways rather than long unannotated tables.
- **AI agent implementation:** reorganised the notebook into four narrative sections plus an appendix; added a file/problem/proposed-decision table; moved reusable parsing/inventory code into `scripts/investigation_support.py`; removed the long signature and blank-cell displays; retained privacy tests, reconciliation and output-saving in the appendix. Added the already verified Tamworth missing-rating evidence to the narrative. Populated local notebook results from the executed artifact for review.
- **AI agent verification:** reran the revised notebook through the isolated relocated Jupyter verifier. All twelve code cells in the twenty-five-cell notebook passed; the eleven privacy tests ran in the appendix; all 54 source/reference file hashes remained unchanged. The source mappings and Bronze/Silver transformations remain future implementation work.
- **Applicant review:** requested presentation structure is implemented; independent review of the revised document remains outstanding. Saved outputs remain local and have not been pushed to GitHub.


## AI-005 — Applicant-directed curated masked feedback examples

Date: 27 October 2026. Status: **Five local display examples implemented and verified; applicant review and commit pending**.

- **Applicant decision:** requested three to five masked comments illustrating actual findings instead of withholding every comment; suggested Geelong scale direction and Tamworth missing-rating examples, with an individual check before committing.
- **AI agent implementation/review:** clarified that no clean canonical dataset or production masker yet exists. Selected five source excerpts: two Geelong 2025 responses, two unrated Tamworth responses and one Chermside response. Applied existing local-review redaction and inspected the exact selected output individually for names/contact/registration identifiers. A registration and mobile number are replaced by tags. The other chosen excerpts contain no evident person names, contact details or registration identifiers. The source wording and missing ratings remain intact.
- **Attribution:** the notebook explicitly identifies the AI agent as the reviewer; it does not claim the applicant hand-checked or approved the examples. The user should review the selected examples before committing. An individual review of five excerpts is not a dataset-wide privacy certification.
- **Verification:** the displayed masked strings must match redaction of their specified source rows; unexpected source changes stop display. All thirteen code cells in the twenty-seven-cell notebook passed in the isolated relocated kernel, including the existing eleven privacy regression tests; all 54 original/reference source file hashes remained unchanged. Default previews continue to withhold free text; only these explicitly curated excerpts are displayed.
- **Remaining work:** applicant review, a production text-release policy, canonical dataset and external AI/export privacy checks remain pending. No Gemini enrichment call or new commit/push was performed.


## AI-007 — Applicant selection of local Ollama

Date: 27 October 2026. Status: **Provider decision recorded; enrichment not executed**.

- **Applicant decision:** chose Ollama with local inference instead of Gemini to avoid API charges.
- **AI agent contribution:** explained that local runtime, memory and classification quality still require a benchmark, and that local inference does not remove the need for privacy and output checks.
- **Next verification:** evaluate a selected local model against human-labelled comments, retain model/prompt versions and document errors. No local-model result or completed enrichment run is claimed.
