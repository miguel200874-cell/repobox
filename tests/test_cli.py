import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from repobox.cli import run


class CliTests(unittest.TestCase):
    def test_analyze_and_validate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "app.py").write_text("print('ready')\n", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(run(["analyze", str(root)]), 0)
                self.assertEqual(run(["validate", str(root / "repobox.toml")]), 0)
            self.assertIn("Created:", output.getvalue())

    def test_prepare_bootable_image_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "app"
            root.mkdir()
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")
            output_dir = Path(temp) / "dist"
            with contextlib.redirect_stdout(io.StringIO()):
                code = run(
                    [
                        "image",
                        str(root),
                        "--target",
                        "pi5",
                        "--output-dir",
                        str(output_dir),
                        "--prepare-only",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue((output_dir / "app-pi5-image-source" / "config" / "repobox.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
