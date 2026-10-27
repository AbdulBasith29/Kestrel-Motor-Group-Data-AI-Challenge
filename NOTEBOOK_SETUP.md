# Reproduce the investigation notebook

## Requirements

Tested interpreter: **CPython 3.14.0 on Windows**. Other interpreter versions and operating systems have not been verified. Run the commands below from the assignment root, the folder containing `feedback`, `reference` and `scripts`.

Keep the supplied data filenames and sheet names unchanged. The notebook investigates this particular assignment pack; its special-case examples deliberately refer to those sources. Original data must be supplied locally and should not be published in an unrestricted repository.

## Fresh environment: Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-notebook.txt
.\.venv\Scripts\python.exe scripts/verify_notebook.py
```

The automated check uses a real Jupyter kernel from that interpreter. It runs every code cell in a temporary, relocated copy of the assignment, starting without saved notebook variables or outputs. No manual execution of older audit scripts is required. Temporary working files live under `.repro` and are removed after the check.

## Open interactively in Antigravity or VS Code

Open `scripts/investigation.ipynb`. Select the Python interpreter in `.venv` as the notebook kernel. Restart the kernel, then choose **Run All**. The editor needs its Python/Jupyter notebook support installed. A standalone JupyterLab installation is not included or required for the automated check.

Launch the notebook from the assignment root or `scripts`, so its relative folder discovery can locate the data. Displayed paths in saved outputs are evidence from the run, not hardcoded input paths.

## Evidence and limits

- `reproducibility/run-log.json`: pass/fail, versions, cell counts, source-file hashes and source integrity checks.
- `reproducibility/investigation.executed.ipynb`: notebook with freshly generated outputs.
- `reproducibility/inspection_summaries`: structural inventories from the verified run.
- `reproducibility/environment-lock.txt`: exact Python package versions used by the verified environment. For an exact rebuild, install this file in place of the shorter direct-dependency file.

The verifier returns a nonzero exit status on a cell error. It checks both original and relocated feedback/reference file hashes after execution. A successful run establishes reproducibility for the supplied pack and tested environment; it does not validate the future ingestion pipeline or business conclusions.

Raw source files are never written by the notebook. Notebook previews mask common identifiers heuristically; personal names can remain in prose. Keep executed notebooks restricted until a fuller privacy review. Structural summary files omit raw response values.

## Privacy preview checks

The notebook now imports `scripts/privacy_preview.py` and runs the synthetic regression tests in `tests/test_privacy_preview.py`. Keep those files alongside the notebook when reproducing it. To run the checks separately from PowerShell at the assignment root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Default previews withhold free-text comments/actions, person/identifier fields, vehicle/model values, unknown columns and unrecognised values. This deliberately hides information rather than relying on regex to discover every possible personal detail. A separate heuristic text-redaction function is provided for restricted local review only; unknown names, addresses and unsupported formats may remain. It is not approved as the sole AI/export privacy gate.

`reproducibility/privacy-preview-check.json` records a local check of the display policy against the currently identified source header segments, without including raw identifiers. It does not prove universal anonymisation or complete header detection. The original source files are unchanged. The notebook committed to Git should continue to have outputs cleared; the verifier creates a separate local executed artifact.

The findings-first notebook also requires `scripts/investigation_support.py`. The automated verifier copies this support module into the relocated test folder. The main notebook has populated local results for presentation; clear outputs before committing if following the existing repository policy.
