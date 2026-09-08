import hashlib
import tarfile
import tempfile
import unittest
from pathlib import Path

from repobox.analyzer import analyse
from repobox.builder import build_bundle


class BuilderTests(unittest.TestCase):
    def _project(self, root: Path) -> None:
        (root / "app.py").write_text("print('hello')\n", encoding="utf-8")
        (root / ".env").write_text("SECRET=do-not-package\n", encoding="utf-8")
        (root / "readme.txt").write_text("demo\n", encoding="utf-8")

    def test_bundle_contains_installer_and_ignores_secrets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "app"
            root.mkdir()
            self._project(root)
            manifest = analyse(root, "Hello")
            result = build_bundle(root, manifest, "pi5", Path(temp) / "dist")
            with tarfile.open(result.path, "r:gz") as archive:
                names = archive.getnames()
                install_info = archive.getmember("hello-pi5/repobox/install.sh")
                install = archive.extractfile(install_info)
                install_text = install.read().decode() if install else ""
        self.assertIn("hello-pi5/app/app.py", names)
        self.assertNotIn("hello-pi5/app/.env", names)
        self.assertIn("Raspberry Pi 5", install_text)
        self.assertIn("apt-get install -y --no-install-recommends ca-certificates curl", install_text)
        self.assertIn("Health check failed", install_text)
        self.assertIn("sha256sum --check SHA256SUMS", install_text)
        self.assertIn("runuser -u repobox -- python3 -m venv", install_text)
        self.assertEqual(install_info.mode, 0o755)

    def test_bundle_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "app"
            root.mkdir()
            self._project(root)
            manifest = analyse(root, "Stable")
            first = build_bundle(root, manifest, "pi4", Path(temp) / "one")
            second = build_bundle(root, manifest, "pi4", Path(temp) / "two")
            self.assertEqual(hashlib.sha256(first.path.read_bytes()).digest(), hashlib.sha256(second.path.read_bytes()).digest())


if __name__ == "__main__":
    unittest.main()
