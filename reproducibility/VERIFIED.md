# Notebook verification

Result: **PASS** on 27 October 2026 (Australia/Sydney).

- Fresh virtual environment, without access to globally installed Python packages.
- CPython 3.14.0 on Windows; direct dependencies in `../requirements-notebook.txt`, all resolved packages in `environment-lock.txt`.
- Executed with nbclient and a real ipykernel, using a relocated temporary assignment folder and no saved notebook state.
- All 15 code cells in the 32-cell notebook completed; zero cell error outputs.
- All 54 original and relocated feedback/reference files retained their input hashes.
- All five expected structural summaries were generated.
- Machine-readable evidence and notebook/input fingerprints: `run-log.json`.
- Freshly executed artifact: `investigation.executed.ipynb`.

The sandbox blocked temporary package and Jupyter connection files; installation and verification succeeded through approved execution outside the sandbox. Jupyter emitted a Windows event-loop compatibility warning and automatically used its supported selector-thread fallback; notebook execution passed. Other Python versions and operating systems have not been tested.

This verifies the exploratory notebook, not the unimplemented ingestion/validation pipeline or AI/business analysis. The supplied input files remain necessary. Keep the executed notebook restricted because preview masking is heuristic.
