"""Execute the investigation notebook in an isolated, relocated assignment copy."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from datetime import datetime, timezone

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reproducibility"
SCRATCH = ROOT / ".repro"


def hashes(root):
    return {str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("feedback", "reference") for p in sorted((root / folder).rglob("*")) if p.is_file()}


def main():
    OUTPUT.mkdir(exist_ok=True)
    SCRATCH.mkdir(exist_ok=True)
    source_hashes = hashes(ROOT)
    report = {"status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              "python": platform.python_version(), "platform": platform.system(),
              "dependencies": {name: importlib.metadata.version(name) for name in
                               ("pandas", "openpyxl", "nbformat", "nbclient", "ipykernel")},
              "source_file_count": len(source_hashes), "source_hashes": source_hashes,
              "privacy_helper_sha256": hashlib.sha256((ROOT / "scripts" / "privacy_preview.py").read_bytes()).hexdigest(),
              "privacy_tests_sha256": hashlib.sha256((ROOT / "tests" / "test_privacy_preview.py").read_bytes()).hexdigest(),
              "notebook_sha256": hashlib.sha256((ROOT / "scripts" / "investigation.ipynb").read_bytes()).hexdigest(),
              "notebook_code_sha256": hashlib.sha256(json.dumps(["".join(c["source"]) for c in json.loads((ROOT / "scripts" / "investigation.ipynb").read_text(encoding="utf-8"))["cells"] if c["cell_type"] == "code"], ensure_ascii=False).encode("utf-8")).hexdigest(),
              "test": "Run every cell in a relocated copy with an isolated kernel, then verify source hashes."}
    try:
        with tempfile.TemporaryDirectory(prefix="notebook-check-", dir=SCRATCH) as temporary:
            base = Path(temporary)
            relocated = base / "relocated-assignment"
            for folder in ("feedback", "reference"):
                shutil.copytree(ROOT / folder, relocated / folder)
            (relocated / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts" / "privacy_preview.py", relocated / "scripts" / "privacy_preview.py")
            shutil.copy2(ROOT / "scripts" / "investigation_support.py", relocated / "scripts" / "investigation_support.py")
            shutil.copytree(ROOT / "tests", relocated / "tests", ignore=shutil.ignore_patterns("__pycache__"))
            kernel_root = base / "jupyter"
            kernel_dir = kernel_root / "kernels" / "kestrel-repro"
            kernel_dir.mkdir(parents=True)
            (kernel_dir / "kernel.json").write_text(json.dumps({
                "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                "display_name": "Kestrel isolated verification", "language": "python"
            }), encoding="utf-8")
            # Process-local settings: no kernel registration or changes to the user's Jupyter configuration.
            os.environ["JUPYTER_PATH"] = str(kernel_root)
            os.environ["JUPYTER_RUNTIME_DIR"] = str(base / "runtime")
            os.environ["JUPYTER_CONFIG_DIR"] = str(base / "jupyter-config")
            os.environ["IPYTHONDIR"] = str(base / "ipython")
            notebook = nbformat.read(ROOT / "scripts" / "investigation.ipynb", as_version=4)
            for cell in notebook.cells:
                if cell.cell_type == "code":
                    cell.outputs = []
                    cell.execution_count = None
            client = NotebookClient(notebook, timeout=180, kernel_name="kestrel-repro",
                                    resources={"metadata": {"path": str(relocated / "scripts")}},
                                    allow_errors=False)
            client.execute()
            nbformat.validate(notebook)
            code_cells = [c for c in notebook.cells if c.cell_type == "code"]
            assert all(c.execution_count is not None for c in code_cells), "Some code cells did not run."
            assert not any(o.output_type == "error" for c in code_cells for o in c.outputs), "Cell error."
            assert hashes(ROOT) == source_hashes, "Original source files changed."
            assert hashes(relocated) == source_hashes, "Relocated source files changed."
            report.update(status="passed", total_cells=len(notebook.cells), code_cells_executed=len(code_cells),
                          error_outputs=0, source_files_unchanged=True, relocated_execution=True)
            nbformat.write(notebook, OUTPUT / "investigation.executed.ipynb")
            summaries = relocated / "scripts" / "investigation_outputs"
            evidence_dir = OUTPUT / "inspection_summaries"
            evidence_dir.mkdir(exist_ok=True)
            report["summary_files"] = []
            for path in sorted(summaries.iterdir()):
                if path.is_file():
                    shutil.copy2(path, evidence_dir / path.name)
                    report["summary_files"].append(path.name)
    except Exception as exc:
        report.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        (OUTPUT / "run-log.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k not in ("source_hashes", "error")}, indent=2))


if __name__ == "__main__":
    main()
