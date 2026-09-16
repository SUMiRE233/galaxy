from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import PROJECT_ROOT


class DemoEndToEndTests(unittest.TestCase):
    def test_demo_pipeline_runs_in_clean_temporary_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            shutil.copytree(
                PROJECT_ROOT / "scripts",
                workspace / "scripts",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(workspace / "scripts" / "05_run_pipeline.py"),
                    "--mode",
                    "demo",
                    "--demo-count",
                    "20",
                    "--top-k",
                    "3",
                ],
                cwd=workspace,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            graph_path = workspace / "web" / "music_graph.json"
            self.assertTrue(graph_path.exists())

            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            self.assertEqual(graph["meta"]["trackCount"], 20)
            self.assertEqual(graph["meta"]["topK"], 3)
            self.assertEqual({node["source"] for node in graph["nodes"]}, {"demo"})
            self.assertFalse(any(node["path"] for node in graph["nodes"]))

    def test_public_fixture_is_sanitized(self) -> None:
        graph = json.loads(
            (PROJECT_ROOT / "web" / "music_graph.example.json").read_text(encoding="utf-8")
        )

        self.assertGreaterEqual(len(graph["nodes"]), 2)
        self.assertEqual({node["source"] for node in graph["nodes"]}, {"demo"})
        self.assertFalse(any(node.get("isPersonal") for node in graph["nodes"]))
        self.assertFalse(any(node.get("path") for node in graph["nodes"]))


if __name__ == "__main__":
    unittest.main()
