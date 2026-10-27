# Notebook verification

Result: **PASS** on 27 October 2026 (Australia/Sydney).

- Fresh virtual environment, without access to globally installed Python packages.
- CPython 3.14.0 on Windows; direct dependencies in `../requirements-notebook.txt`, all resolved packages in `environment-lock.txt`.
- Executed with nbclient and a real ipykernel, using a relocated temporary assignment folder and no saved notebook state.
- All 13 code cells in the 27-cell notebook completed; zero cell error outputs.
- All 54 original and relocated feedback/reference files retained their input hashes.
- All five expected structural summaries were generated.
- Machine-readable evidence and notebook/input fingerprints: `run-log.json`.
- Freshly executed artifact: `investigation.executed.ipynb`.

The sandbox blocked temporary package and Jupyter connection files; installation and verification succeeded through approved execution outside the sandbox. Jupyter emitted a Windows event-loop compatibility warning and automatically used its supported selector-thread fallback; notebook execution passed. Other Python versions and operating systems have not been tested.

This verifies the exploratory notebook, not the unimplemented ingestion/validation pipeline or AI/business analysis. The supplied input files remain necessary. Keep the executed notebook restricted because preview masking is heuristic.

Privacy-preview update: eleven synthetic regression tests passed. The updated notebook runs these tests before examples. The real-layout check in `privacy-preview-check.json` verifies default suppression for the identified header segments, including Noosa person fields. External free-text enrichment/export privacy controls remain unimplemented.

Narrative update: the notebook now opens with findings and proposed decisions, uses four plain sections, and moves parsing support to `scripts/investigation_support.py`. Synthetic privacy tests and output-saving run in the appendix. The revised twelve code cells passed in the isolated kernel. Local notebook outputs are populated for review; clear them before the next Git commit if that remains the chosen repository policy.

Curated feedback update: five selected masked excerpts are displayed at the start of the traps section. Each was individually reviewed by the AI agent, with applicant review explicitly pending. Each displayed string is checked against its source through the redactor; a changed or unexpectedly redacted source stops the example cell rather than displaying replacement text automatically. The updated thirteen code cells passed and source hashes remained unchanged.
