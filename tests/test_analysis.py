import tempfile
import unittest
from pathlib import Path

from rooster_engine.analysis import CodebaseAnalyzer, prioritize_findings


class CodebaseAnalyzerTests(unittest.TestCase):
    def test_analyzer_reads_source_and_returns_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "rooster_engine").mkdir()
            (root / "rooster_engine" / "guard.py").write_text(
                'Permission.NETWORK\nrecord_hash = "x"\n', encoding="utf-8"
            )
            inventory = [{"name": "rooster_engine/guard.py", "type": "file"}]
            result = CodebaseAnalyzer(root).analyze(inventory)
            self.assertEqual(result["file_count"], 1)
            self.assertTrue(result["read_only"])
            self.assertEqual(result["files_read"], ["rooster_engine/guard.py"])
            self.assertTrue(result["findings"])
            self.assertTrue(all("file" in finding for finding in result["findings"]))

    def test_findings_identify_source_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "rooster_engine").mkdir()
            (root / "rooster_engine" / "command.py").write_text(
                'DEFAULT_ALLOWED = frozenset({"python"})\n', encoding="utf-8"
            )
            result = CodebaseAnalyzer(root).analyze([])
            finding = next(
                item for item in result["findings"] if item["area"] == "command execution"
            )
            self.assertEqual(finding["file"], "rooster_engine/command.py")

    def test_findings_are_prioritized(self):
        findings = [
            {"area": "runtime", "priority": "MEDIUM"},
            {"area": "network", "priority": "HIGH"},
        ]
        ordered = prioritize_findings(findings)
        self.assertEqual(ordered[0]["priority"], "HIGH")


if __name__ == "__main__":
    unittest.main()
