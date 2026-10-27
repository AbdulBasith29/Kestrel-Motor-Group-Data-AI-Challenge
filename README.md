# Kestrel Motor Group — feedback consolidation and AI enrichment

This checkpoint covers source investigation, the CSV baseline, DuckDB Bronze/Silver and optional AI enrichment. Gemini produced 5,358 structured results, with two quarantined errors and one pre-transmission holdout. The applicant found an incorrect name-redaction method; exact-name proposals replace it. Applicant-supplied labels now give 46/49 sentiment agreement (93.9%) on a diagnostic sample; theme metrics use a provisional, documented crosswalk. Gold reporting models are implemented locally for review; the final dashboard and business recommendations remain outstanding.

- Start with [notebook setup](NOTEBOOK_SETUP.md).
- Review the [Gold reporting checkpoint](docs/gold_checkpoint.md) and run [review_gold.sql](scripts/review_gold.sql) against the separate reporting-only database.
- Review the [Silver checkpoint](docs/silver_checkpoint.md), [Gemini run and masking correction](docs/gemini_checkpoint.md), and [independent 50-comment evaluation guide](docs/human_review_50.md).
- Use [Gemini enrichment](src/gemini_enrichment.py) for cloud inference or [Ollama enrichment](src/enrichment.py) for local inference; both are optional and separate from ingestion.
- API keys belong in a local `.env` copied from `.env.example`; databases, comments and human-review CSVs remain outside Git.
- Review the [DuckDB Bronze checkpoint](docs/bronze_checkpoint.md) and its reproducible ingestion checks.
- Run and review the [CSV baseline checkpoint](docs/baseline_checkpoint.md), including applicant-approved decisions and aggregate validation results.
- Explore [the investigation notebook](scripts/investigation.ipynb).
- Review [mapping assumptions](ASSUMPTIONS.md), including provisional department aliases awaiting business confirmation.
- Read the [AI usage and verification log](AI_USAGE_LOG.md), including a verified failure of the generated preview-masking helper.
- See [verification evidence](reproducibility/VERIFIED.md): 13 code cells passed in an isolated, relocated environment; input files were unchanged.
- Notebook outputs are cleared in Git. Obtain the original assignment data separately and retain the `feedback` and `reference` folders locally; these are deliberately excluded from version control.

## Design and ownership

The applicant supplied the implementation guide and architecture, proposed the marts design, authored the original business-answer SQL and initial Silver implementation, inspected the sources, set business rules and supplied the evaluation labels. Codex assisted with implementation, schema adaptations, testing and verification. The applicant also discovered the incorrect AI name-redaction proposals; the correction and remaining limits are recorded in the AI log. Marts and the original business queries are the applicant's work, not AI-originated ideas.

## AI evaluation against applicant labels

The applicant supplied 49 labelled rows from the 50-comment diagnostic sample; the missing row is left blank. Comments were preserved unchanged. Sentiment agrees on **46/49 (93.9%)**, counting one failed model response as incorrect. The two other sentiment disagreements were a positive explanation interpreted as mixed and a short positive comment classified unclear. Name flags agree on **48/49**, with one unassessed failed response; all three applicant-marked visible-name cases were detected among assessed outputs. This does not establish complete anonymisation.

The applicant used finer-grained theme wording than the model's fixed taxonomy. [The crosswalk](config/human_theme_crosswalk.yml) preserves raw labels, records context-only tags and leaves three generic process cases unresolved. It was defined before comparing model predictions. Its mappings are AI-assisted and await applicant confirmation. On **46 provisionally mapped rows**, at least one theme matches in **42/46 (91.3%)**; micro precision is **81.2%**, recall **90.3%**, and F1 **85.5%**. Strict agreement across all three reviewed fields is **31/46 (67.4%)**. These are diagnostic-sample results, not population accuracy estimates or per-theme-polarity scores.

Observed disagreements worth reviewing:

- **Helpful explanation misread:** “The explanation was very slow and clear for me” was positive to the applicant but mixed to Gemini; slowness was helpful in this context.
- **Unsupported topic:** praise for courteous parts staff acquired a parts_availability label, despite no statement about stock or supply. A department mention alone is insufficient evidence.
- **Short-text ambiguity:** “Wasn't lost for once.” was positive to the applicant but unclear to the model; limited context makes this a disagreement to inspect, rather than proof of universally correct interpretation.
- **Technical failure:** one labelled booking/appointment case has no usable model classification. It remains counted as incorrect in end-to-end agreement rather than being dropped from the denominator.

See [aggregate evaluation](outputs/gemini_evaluation.json) and [labelling/scoring instructions](docs/human_review_50.md). Raw comments, supplied labels and the detailed disagreement CSV stay local under data/. The applicant found the earlier offset-redaction failure; its correction and remaining limits are documented in the [AI usage log](AI_USAGE_LOG.md).

## Supplied assignment brief

Kestrel Motor Group: Data & AI Challenge
========================================
The Kestrel Motor Group is an Australian dealership group consisting of 24 dealerships across Victoria, New South Wales and Queensland, selling and servicing several vehicle brands. Each dealership collects customer feedback from sales, service and parts customers and sends it to head office.

The Problem
-----------
Some dealerships send a new file each month or quarter; others keep one running workbook and send that.

Nobody ever agreed on a template. Each site's spreadsheet has evolved over the years, built by whoever happened to own it at the time. Head office has a folder full of these files and cannot answer simple questions about their customers' experience and dealership performance.

The Head of Customer Experience has asked you to help!

Your task
---------
1. **Bring it together.** Consolidate the feedback into a single, clean dataset. Decide what it should look like, and explain why.
2. **Decide what you can trust.** Define data quality and validation rules, apply them, and report what passed, what failed, and what you did about it.
3. **Make sense of the words.** Use AI to turn free-text feedback into something you can analyse, such as themes, sentiment or anything else you think matters. Show how you know whether it worked.
4. **Answer the business.** Tell the Head of Customer Experience:
   - What are the main drivers of negative feedback, and how do they vary across dealerships and departments?
   - Has anything changed over the year?
   - Where should Kestrel focus first, and roughly what is it worth?

### What's in this pack
- **`feedback/`**: 52 spreadsheets (.xlsx and .csv) of customer feedback from the dealerships, covering October 2025 to September 2026
- **`reference/dealerships.csv`**: the official list of dealerships, with codes, regions and brands
- **`reference/monthly_revenue.csv`**: vehicles sold, service jobs, parts transactions and revenue by dealership and month

The files were created by people, not systems. Treat everything you find with healthy suspicion. All names, contact details and businesses are fictional (any resemblance to real persons is purely coincidental), but please handle the personal information as if it were real.

### What technology you can use
**It's your call**, as long as you can explain your choices (and "it's new and I wanted to try it" is a perfectly valid reason). Use any language, any frameworks or libraries, even external services (at your own expense!).

### Can you use AI?
Yes! We expect you'll want to use AI tools, both to help you build (coding agents and assistants) and inside your solution (for example, using an LLM to classify feedback or interpret messy columns). There are no restrictions on which tools you use. We are interested in *how* you use them: what you delegate, what you check, and where you catch them getting it wrong.

### What to submit
Put everything in your repo:
- **Your solution.** Code, notebooks, scripts, etc., in any language or stack. It should be reproducible enough for us to follow what you did.
- **Your report.** A document (`README.md`, or PDF, etc.) covering:
    - Overview of your approach, assumptions, and solution
    - Tech choices and rationale
    - Observations about data quality
    - Answers to the business questions for the Head of Customer Experience
    - Insights and recommendations about the feedback across dealerships
    - AI usage overview: a brief, honest record of how you used AI: key prompts or interactions, where it helped, where it was wrong, and how you verified its output.

Keep it concise - it doesn't have to be an essay; in fact, we'd prefer it wasn't. Bullets and short paragraphs are enough.

### How to submit
Submission as a git repo is preferred, via the platform of your own choosing (github, bitbucket, gitlab, self-host. As long as we can access and clone it).

### What's important
We are **not** assessing code quality or polish. We will look at:
- **Problem solving:** did you understand what the business actually needs?
- **Data analysis:** what did you notice, and how did you handle it?
- **Trust and verification:** how do you know your results, and the AI's output, are right?
- **Insight and communication:** is your answer clear, useful and honest about its limits?
- **AI fluency:** did you use AI tools thoughtfully and effectively?

Good luck and have fun!


Local investigation notebook
----------------------------
See [NOTEBOOK_SETUP.md](NOTEBOOK_SETUP.md) for dependency installation, interactive execution, and the clean-environment verification command. The investigation notebook is exploratory; executable ingestion, validation and enrichment are separate modules. Business reporting and recommendations remain outstanding.
