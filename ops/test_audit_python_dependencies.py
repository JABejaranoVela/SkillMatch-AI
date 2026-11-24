import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from audit_python_dependencies import audit_inventory, main


def distribution(name, version, **extra):
    return {"metadata": {"name": name, "version": version}, **extra}


class AuditPythonDependenciesTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        self.inventory = {
            "installed": [
                distribution("skillmatch-ai-backend", "0.1.0", direct_url={}),
                distribution("Sample_Package", "1.2.3"),
                distribution("sample-extra", "2.0"),
            ]
        }
        self.dependencies = [
            {"name": "sample.package", "version": "1.2.3", "vulns": []},
            {"name": "sample-extra", "version": "2.0", "vulns": []},
        ]

    def audit(self, exit_code):
        def write_report(*_args, **_kwargs):
            (self.output / "audit.json").write_text(
                json.dumps({"dependencies": self.dependencies}), encoding="utf-8"
            )
            return subprocess.CompletedProcess([], exit_code)

        with patch("audit_python_dependencies.subprocess.run") as run:
            run.side_effect = write_report
            result = audit_inventory(self.inventory, self.output)
            self.assertIn("--no-deps", run.call_args.args[0])
            self.assertIn("--disable-pip", run.call_args.args[0])
        return result

    def test_complete_audit_uses_exact_versions_and_excludes_first_party(self):
        result = self.audit(exit_code=0)
        self.assertEqual(result["status"], "clean")
        self.assertEqual(result["audited"], 2)
        self.assertEqual(
            (self.output / "requirements.txt").read_text(encoding="utf-8"),
            "sample-extra==2.0\nsample-package==1.2.3\n",
        )

    def test_findings_are_separate_from_audit_failure(self):
        self.dependencies[0]["vulns"] = [{"id": "TEST-ADVISORY"}]
        self.assertEqual(self.audit(exit_code=1)["status"], "findings")
        self.assertEqual(self.audit(exit_code=0)["status"], "incomplete")

    def test_incomplete_report_with_skipped_or_missing_version(self):
        self.dependencies[0] = {"name": "sample-package", "skip_reason": "Unavailable"}
        self.dependencies[1]["version"] = "2.1"
        result = self.audit(exit_code=0)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["unverified_distributions"], ["sample-extra", "sample-package"])

    def test_direct_url_is_separated_without_exporting_its_url(self):
        self.inventory["installed"][2]["direct_url"] = {"url": "https://example.invalid/artifact"}
        self.dependencies.pop()
        result = self.audit(exit_code=0)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["unverified_distributions"], ["sample-extra"])
        self.assertNotIn(
            "sample-extra",
            (self.output / "index-requirements.txt").read_text(encoding="utf-8"),
        )
        for path in self.output.iterdir():
            self.assertNotIn("example.invalid", path.read_text(encoding="utf-8"))

    def test_missing_audit_output_records_incomplete_and_exits_nonzero(self):
        inventory = self.output / "inventory.json"
        inventory.write_text(json.dumps(self.inventory), encoding="utf-8")
        args = [
            "audit", "--inventory", str(inventory), "--output-dir", str(self.output),
            "--profile", "production", "--source-sha", "example-commit",
        ]
        with patch("sys.argv", args), patch("audit_python_dependencies.subprocess.run") as run:
            run.return_value.returncode = 1
            self.assertEqual(main(), 1)
        status = json.loads((self.output / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["status"], "incomplete")
        self.assertEqual(status["source_sha"], "example-commit")

    def test_failed_rerun_cannot_reuse_an_old_report(self):
        self.dependencies[0]["vulns"] = [{"id": "TEST-ADVISORY"}]
        self.assertEqual(self.audit(exit_code=1)["status"], "findings")
        with patch("audit_python_dependencies.subprocess.run") as run:
            run.return_value.returncode = 1
            with self.assertRaises(FileNotFoundError):
                audit_inventory(self.inventory, self.output)
        self.assertFalse((self.output / "audit.json").exists())
