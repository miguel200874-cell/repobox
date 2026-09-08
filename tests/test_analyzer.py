import json
import tempfile
import unittest
from pathlib import Path

from repobox.analyzer import analyse
from repobox.errors import AnalysisError


class AnalyzerTests(unittest.TestCase):
    def test_stdlib_python_app(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "app.py").write_text(
                "import os\nTOKEN = os.getenv('API_TOKEN')\nprint(TOKEN)\n", encoding="utf-8"
            )
            manifest = analyse(root, "Demo")
        self.assertEqual(manifest.app.runtime, "python")
        self.assertEqual(manifest.app.start, "python3 app.py")
        self.assertIn("API_TOKEN", manifest.environment)

    def test_fastapi_app(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
            (root / "api.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
            manifest = analyse(root)
        self.assertIn("uvicorn api:app", manifest.app.start)

    def test_node_start_script(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = {"name": "node-demo", "scripts": {"start": "node server.js"}}
            (root / "package.json").write_text(json.dumps(package), encoding="utf-8")
            (root / "server.js").write_text("const port = 3456; app.listen(3456);", encoding="utf-8")
            manifest = analyse(root)
        self.assertEqual(manifest.app.runtime, "node")
        self.assertEqual(manifest.app.port, 3456)

    def test_unknown_project(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(AnalysisError):
                analyse(Path(temp))


if __name__ == "__main__":
    unittest.main()
