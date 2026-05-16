"""Smoke tests for the official graph pipeline and validation status handling."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nodes.validation_check import validation_check_node  # noqa: E402
from schemas.annotation import create_empty_state  # noqa: E402


class GraphPipelineSmokeTests(unittest.TestCase):
    def test_main_graph_without_api_key_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "graph_output.json"
            ttl_path = Path(tmpdir) / "graph_output.ttl"
            env = os.environ.copy()
            env["OPENAI_API_KEY"] = ""
            env["STDICT_API_KEY"] = ""
            env["PYTHON_DOTENV_DISABLED"] = "true"
            command = [
                sys.executable,
                "src/main.py",
                "--input",
                "data/input.txt",
                "--output",
                str(output_path),
                "--pipeline",
                "graph",
                "--ttl-output",
                str(ttl_path),
            ]
            completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=False, capture_output=True, text=True)

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertIn("metadata", payload)
            self.assertFalse(payload["metadata"].get("llm_available", True))
            self.assertTrue(payload.get("errors"))
            self.assertTrue(ttl_path.exists())


class ValidationStatusTests(unittest.TestCase):
    def test_validation_errors_set_needs_repair_status(self) -> None:
        state = create_empty_state(document_id="doc-1", case_id="case-1", raw_text="테스트")
        state["metadata"] = {"pipeline": "graph"}
        state["mipvu_annotations"] = [
            {
                "candidate_id": "C001",
                "mipvu_label": "MRW",
                "basic_meaning_source": "unavailable",
                "distinctness": False,
                "similarity": True,
                "comparison_possible": False,
                "confidence": 0.4,
            }
        ]
        state["metaphor_annotations"] = [
            {
                "metaphor_id": "M001",
                "candidate_id": "C001",
                "source_domain": "",
                "target_domain": "LegalSystem",
                "metaphor_type": "uncertain",
                "confidence": 0.4,
            }
        ]

        result = validation_check_node(state)
        self.assertEqual(result.get("status"), "needs_repair")
        self.assertEqual(result.get("metadata", {}).get("validation_status"), "needs_repair")
        self.assertTrue(result.get("human_review_items"))


if __name__ == "__main__":
    unittest.main()
