"""Meaningful arrival/recovery tests; never modify the assignment source pack."""
import importlib.util
from pathlib import Path
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from watchdog.events import FileCreatedEvent

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("watcher_module", ROOT / "flows/watch.py")
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
from run_lock import exclusive_lock


class WatcherTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory(dir=ROOT / "data")
        root = Path(temp.name)
        for name in w.FOLDERS:
            (root / name).mkdir()
        (root / "feedback/a.csv").write_text("date,rating\n2026-01-01,1\n",encoding="utf-8")
        return temp, root

    def test_settle_waits_and_resets_after_writes(self):
        s=w.Settler(3)
        self.assertFalse(s.ready({"a":"1"},0))
        self.assertFalse(s.ready({"a":"2"},2))
        self.assertFalse(s.ready({"a":"2"},4))
        self.assertTrue(s.ready({"a":"2"},5))
        self.assertFalse(s.ready(None,6))
        self.assertFalse(s.ready({"a":"2"},7))

    def test_success_skip_restart_and_content_change(self):
        temp,root=self.fixture()
        with temp:
            state=root/"state"
            c=w.Coordinator(root,state,0)
            manifest=w.scan(root)
            self.assertEqual(c.process(manifest,lambda:SimpleNamespace(returncode=0)),"succeeded")
            self.assertFalse(c.eligible(manifest)); c.close()
            c=w.Coordinator(root,state,0)
            self.assertFalse(c.eligible(manifest))
            (root/"feedback/a.csv").write_text("changed",encoding="utf-8")
            self.assertTrue(c.eligible(w.scan(root)))
            self.assertEqual(len(list((state/"archive").glob("*/feedback/a.csv"))),1)
            c.close()

    def test_failure_retries_and_does_not_skip_previous_success(self):
        temp,root=self.fixture()
        with temp:
            c=w.Coordinator(root,root/"state",0)
            original=w.scan(root)
            c.process(original,lambda:SimpleNamespace(returncode=0))
            path=root/"feedback/a.csv"; original_text=path.read_text()
            path.write_text("changed")
            failed=w.scan(root)
            self.assertEqual(c.process(failed,lambda:SimpleNamespace(returncode=1)),"failed")
            self.assertTrue(c.eligible(failed))
            path.write_text(original_text)
            self.assertTrue(c.eligible(w.scan(root)), "A failed rebuild may have partially replaced tables")
            self.assertEqual(len(list((root/"state/quarantine").glob("*/run.json"))),1)
            c.close()

    def test_mid_run_change_never_marked_successful(self):
        temp,root=self.fixture()
        with temp:
            c=w.Coordinator(root,root/"state",0)
            def change():
                (root/"feedback/a.csv").write_text("changed during run")
                return SimpleNamespace(returncode=0)
            self.assertEqual(c.process(w.scan(root),change),"superseded")
            self.assertTrue(c.eligible(w.scan(root)))
            c.close()

    def test_interrupted_attempt_recovers_and_temp_files_ignored(self):
        temp,root=self.fixture()
        with temp:
            manifest=w.scan(root)
            (root/"feedback/~$a.xlsx").write_text("temporary")
            self.assertEqual(w.scan(root),manifest)
            c=w.Coordinator(root,root/"state",0)
            c.db.execute("insert into runs values ('interrupted',?,'processing',?,null,null)",[w.signature(manifest),time.time()]);c.db.commit();c.close()
            c=w.Coordinator(root,root/"state",0)
            self.assertEqual(c.latest()[1],"failed");self.assertTrue(c.eligible(manifest));c.close()

    def test_config_and_reference_changes_affect_signature(self):
        temp,root=self.fixture()
        with temp:
            before=w.scan(root)
            (root/"config/sources.yml").write_text("version: 2")
            self.assertNotEqual(w.signature(before),w.signature(w.scan(root)))
            (root/"reference/dealers.csv").write_text("dealer_code\nTEST\n")
            self.assertEqual(len(w.scan(root)),3)

    def test_events_wake_worker(self):
        wake=threading.Event()
        w.WakeOnChange(wake).on_any_event(FileCreatedEvent("fixture.csv"))
        self.assertTrue(wake.is_set())

    def test_archive_failure_stays_retryable(self):
        temp,root=self.fixture()
        with temp:
            c=w.Coordinator(root,root/"state",0)
            manifest=w.scan(root)
            with patch.object(w.shutil,"copytree",side_effect=PermissionError("simulated sync lock")):
                self.assertEqual(c.process(manifest,lambda:SimpleNamespace(returncode=0)),"failed")
            self.assertTrue(c.eligible(manifest))
            self.assertEqual(c.latest()[1],"failed")
            c.close()

    def test_native_watchdog_observes_arrival(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"data") as temp:
            wake=threading.Event()
            observer=w.Observer()
            observer.schedule(w.WakeOnChange(wake),temp,recursive=False)
            observer.start()
            try:
                (Path(temp)/"arrived.csv").write_text("fixture",encoding="utf-8")
                self.assertTrue(wake.wait(5),"No native arrival event received")
            finally:
                observer.stop();observer.join()

    def test_process_lock_excludes_second_writer_and_releases(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"data") as temp:
            path=Path(temp)/"pipeline.lock"
            with exclusive_lock(path):
                with self.assertRaises(RuntimeError):
                    with exclusive_lock(path):
                        self.fail("second writer entered")
            with exclusive_lock(path):
                pass


if __name__ == "__main__":
    unittest.main()
