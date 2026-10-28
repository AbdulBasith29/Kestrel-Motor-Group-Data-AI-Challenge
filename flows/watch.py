"""Watch source folders and serially trigger the existing Prefect batch CLI.

No source files are moved. Gemini remains opt-in. Local state and source archives
live under ignored data/watcher/. A successful batch is skipped only while its
manifest is still the latest known-good state, not merely seen sometime before.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from run_lock import exclusive_lock
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

FOLDERS = {"feedback": {".csv", ".xlsx"}, "reference": {".csv"}, "config": {".yml", ".yaml"}}


def scan(root):
    """Hash stable readable files; return None if a write races the scan."""
    result = {}
    try:
        for folder, suffixes in FOLDERS.items():
            for path in sorted((root / folder).iterdir()):
                if not path.is_file() or path.name.startswith(("~$", ".")) or path.suffix.lower() not in suffixes:
                    continue
                before = path.stat()
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    return None
                result[path.relative_to(root).as_posix()] = digest
    except (OSError, FileNotFoundError):
        return None
    return result


def signature(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


class Settler:
    def __init__(self, quiet_seconds):
        self.quiet = quiet_seconds
        self.previous = None
        self.since = None

    def ready(self, manifest, now):
        if manifest is None:
            self.previous = self.since = None
            return False
        if manifest != self.previous:
            self.previous = manifest.copy(); self.since = now
            return False
        return now - self.since >= self.quiet


class Coordinator:
    def __init__(self, root, state_dir, retry_seconds=30):
        self.root, self.state = Path(root), Path(state_dir)
        self.state.mkdir(parents=True, exist_ok=True)
        self.retry_seconds = retry_seconds
        self.db = sqlite3.connect(self.state / "runs.sqlite")
        self.db.execute("create table if not exists runs (run_id text primary key, manifest_hash text, status text, started real, finished real, reason text)")
        # Caller holds the watcher singleton lock. An unfinished previous attempt
        # was interrupted and must never count as successfully loaded.
        self.db.execute("update runs set status='failed',finished=?,reason='interrupted' where status='processing'", [time.time()])
        # Recover a crash between pipeline completion and receipt finalisation.
        for (run_id,) in self.db.execute("select run_id from runs where status='succeeded'").fetchall():
            if not (self.state / "archive" / run_id / "run.json").exists():
                self.db.execute("update runs set status='failed',finished=?,reason='archive_receipt_missing' where run_id=?", [time.time(),run_id])
        self.db.commit()

    def latest(self):
        return self.db.execute("select manifest_hash,status,finished from runs order by rowid desc limit 1").fetchone()

    def eligible(self, manifest):
        last = self.latest()
        if not last or last[0] != signature(manifest):
            return True
        if last[1] == "succeeded":
            return False
        return time.time() - (last[2] or 0) >= self.retry_seconds

    def process(self, manifest, runner):
        run_id = uuid.uuid4().hex
        digest = signature(manifest)
        self.db.execute("insert into runs values (?,?, 'processing', ?,null,null)", [run_id,digest,time.time()])
        self.db.commit()
        status, reason = "failed", "pipeline_failed"
        try:
            # Preserve the received version for audit without moving active inputs.
            received = self.state / "received" / run_id
            for relative in manifest:
                dest = received / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.root / relative, dest)
                if hashlib.sha256(dest.read_bytes()).hexdigest() != manifest[relative]:
                    raise RuntimeError("input_changed_before_run")
            if scan(self.root) != manifest:
                raise RuntimeError("input_changed_before_run")
            result = runner()
            if result.returncode == 0:
                status, reason = ("succeeded", "completed") if scan(self.root) == manifest else ("superseded", "inputs_changed_during_run")
        except Exception:
            # Source/provider exception text can contain data; store only safe categories.
            reason = "input_or_runner_error"
        destination = self.state / ("archive" if status == "succeeded" else "quarantine") / run_id
        received = self.state / "received" / run_id
        try:
            # OneDrive may lock directory renames. Copy rather than move, retain
            # the received version, and finalise state only after receipt succeeds.
            if received.exists():
                shutil.copytree(received, destination, dirs_exist_ok=True)
            else:
                destination.mkdir(parents=True, exist_ok=True)
            (destination / "run.json").write_text(json.dumps({"run_id":run_id,"manifest_hash":digest,"status":status,"reason":reason,"files":manifest},indent=2),encoding="utf-8")
        except OSError:
            status, reason = "failed", "archive_receipt_error"
        self.db.execute("update runs set status=?,finished=?,reason=? where run_id=?", [status,time.time(),reason,run_id])
        self.db.commit()
        print(f"watcher run {run_id}: {status} ({reason})", flush=True)
        return status

    def close(self):
        self.db.close()


class WakeOnChange(FileSystemEventHandler):
    def __init__(self, wake):
        self.wake = wake

    def on_any_event(self, event):
        if event.event_type in {"created", "modified", "deleted", "moved"}:
            self.wake.set()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--once", action="store_true", help="Settle and process one manifest, or skip a successful unchanged one")
    p.add_argument("--quiet-seconds", type=float, default=3)
    p.add_argument("--retry-seconds", type=float, default=30)
    p.add_argument("--database", default=str(ROOT / "data/bronze_review.duckdb"))
    p.add_argument("--reporting-database", default=str(ROOT / "data/gold_reporting.duckdb"))
    p.add_argument("--state-dir", default=str(ROOT / "data/watcher"))
    p.add_argument("--enrich", action="store_true")
    p.add_argument("--budget-usd", type=float, default=5)
    a = p.parse_args()
    if a.quiet_seconds <= 0 or a.retry_seconds <= 0 or a.budget_usd <= 0:
        p.error("Quiet/retry intervals and AI budget must be positive")
    state = Path(a.state_dir).resolve()
    if not state.is_relative_to((ROOT / "data").resolve()):
        p.error("State and source archives must stay under ignored data/")
    command = [sys.executable, str(ROOT / "flows/pipeline.py"), "--database", a.database, "--reporting-database", a.reporting_database]
    if a.enrich:
        command += ["--enrich", "--budget-usd", str(a.budget_usd)]
    wake = threading.Event()
    with exclusive_lock(ROOT / "data/watcher.lock"):
        state.mkdir(parents=True, exist_ok=True)
        settings = {"database":str(Path(a.database).resolve()),
                    "reporting_database":str(Path(a.reporting_database).resolve()),
                    "enrichment":a.enrich}
        binding = state / "targets.json"
        if binding.exists() and json.loads(binding.read_text(encoding="utf-8")) != settings:
            raise RuntimeError("Watcher state belongs to different targets/enrichment settings; choose a separate --state-dir")
        binding.write_text(json.dumps(settings,indent=2),encoding="utf-8")
        coordinator = Coordinator(ROOT, state, a.retry_seconds)
        observer = Observer()
        for folder in FOLDERS:
            observer.schedule(WakeOnChange(wake), str(ROOT / folder), recursive=False)
        observer.start()
        settler = Settler(a.quiet_seconds)
        print("Watching feedback/, reference/ and config/. Gemini " + ("enabled" if a.enrich else "disabled"), flush=True)
        try:
            while True:
                manifest = scan(ROOT)
                if settler.ready(manifest, time.monotonic()):
                    if coordinator.eligible(manifest):
                        status = coordinator.process(manifest, lambda: subprocess.run(command, cwd=ROOT))
                        if a.once:
                            return 0 if status == "succeeded" else 1
                        settler = Settler(a.quiet_seconds)
                    elif a.once:
                        print("Skipped: unchanged successful manifest (or retry backoff active)", flush=True)
                        return 0 if coordinator.latest()[1] == "succeeded" else 1
                wake.wait(timeout=min(1, a.quiet_seconds))
                wake.clear()
        except KeyboardInterrupt:
            print("Watcher stopped", flush=True)
            return 0
        finally:
            observer.stop(); observer.join(); coordinator.close()


if __name__ == "__main__":
    raise SystemExit(main())
