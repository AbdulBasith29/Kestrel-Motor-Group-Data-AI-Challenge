"""Orchestration contracts tested without running source-data or provider steps."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location("pipeline_flow", Path(__file__).resolve().parents[1] / "flows/pipeline.py")
pipeline_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline_module)
p = pipeline_module


class PipelineTests(unittest.TestCase):
    def test_default_order_skips_gemini(self):
        calls = []
        with patch.multiple(p, **{name: Mock(side_effect=lambda *a, n=name: calls.append(n))
                                   for name in ["bronze", "silver", "enrich", "gold", "business_answers"]}), patch.object(p, "get_run_logger"):
            p.pipeline.fn("working.duckdb", "reporting.duckdb")
        self.assertEqual(calls, ["bronze", "silver", "gold", "business_answers"])

    def test_silver_failure_blocks_publication(self):
        with patch.object(p, "bronze") as bronze, patch.object(p, "silver", side_effect=RuntimeError("silver failed")), patch.object(p, "gold") as gold, patch.object(p, "business_answers") as answers:
            with self.assertRaisesRegex(RuntimeError, "silver failed"):
                p.pipeline.fn("working.duckdb", "reporting.duckdb")
            bronze.assert_called_once()
            gold.assert_not_called()
            answers.assert_not_called()

    def test_enrichment_is_opt_in_and_only_retrying_task(self):
        calls=[]
        with patch.multiple(p, **{name: Mock(side_effect=lambda *a, n=name: calls.append(n))
                                   for name in ["bronze", "silver", "enrich", "gold", "business_answers"]}), patch.object(p, "get_run_logger"):
            p.pipeline.fn("working.duckdb", "reporting.duckdb", True)
        self.assertEqual(calls, ["bronze", "silver", "enrich", "gold", "business_answers"])
        self.assertEqual(p.enrich.retries, 2)
        for item in [p.bronze, p.silver, p.gold, p.business_answers, p.pipeline]:
            self.assertEqual(item.retries, 0)

    def test_prefect_runtime_success_and_silver_failure(self):
        calls=[]
        with patch.object(p, "run_command", side_effect=lambda args: calls.append(args[0])):
            p.pipeline("stub.duckdb", "stub_reporting.duckdb")
        self.assertEqual(calls, ["src/bronze.py", "src/silver.py", "src/gold.py", "scripts/run_business_answers.py"])
        calls=[]
        def fail_silver(args):
            calls.append(args[0])
            if args[0] == "src/silver.py":
                raise RuntimeError("forced Silver failure")
        with patch.object(p, "run_command", side_effect=fail_silver):
            with self.assertRaisesRegex(RuntimeError, "forced Silver failure"):
                p.pipeline("stub.duckdb", "stub_reporting.duckdb")
        self.assertEqual(calls, ["src/bronze.py", "src/silver.py"])

    def test_prefect_runtime_retries_only_ai(self):
        calls=[]
        attempts=0
        def transient_failure(args):
            nonlocal attempts
            calls.append(args[0])
            if args[0] == "src/gemini_enrichment.py":
                attempts += 1
                if attempts == 1:
                    raise RuntimeError("synthetic provider failure")
        fast_enrich = p.enrich.with_options(retry_delay_seconds=0)
        with patch.object(p, "enrich", fast_enrich), patch.object(p, "run_command", side_effect=transient_failure):
            p.pipeline("stub.duckdb", "stub_reporting.duckdb", True)
        self.assertEqual(calls.count("src/bronze.py"), 1)
        self.assertEqual(calls.count("src/silver.py"), 1)
        self.assertEqual(attempts, 2)
        self.assertEqual(calls[-2:], ["src/gold.py", "scripts/run_business_answers.py"])

    def test_reporting_export_lock_has_safe_actionable_message(self):
        result=Mock(returncode=1,stdout="private",stderr="REPORTING_EXPORT_LOCKED: private")
        with patch.object(p.subprocess,"run",return_value=result):
            with self.assertRaisesRegex(RuntimeError,"close the gold_reporting") as err:
                p.run_command(["src/gold.py"])
        self.assertNotIn("private",str(err.exception))

    def test_subprocess_failure_does_not_log_source_output(self):
        with patch.object(p.subprocess, "run", return_value=Mock(returncode=1, stdout="private", stderr="private")) as run:
            with self.assertRaises(RuntimeError) as err:
                p.run_command(["src/silver.py", "--database", "some path.duckdb"])
        self.assertNotIn("private", str(err.exception))
        self.assertEqual(run.call_args.kwargs["cwd"], p.ROOT)
        self.assertEqual(run.call_args.args[0][0], p.sys.executable)


if __name__ == "__main__":
    unittest.main()
