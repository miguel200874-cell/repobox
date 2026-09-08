import tempfile
import unittest
from pathlib import Path

from repobox.errors import ManifestError
from repobox.manifest import AppConfig, Manifest


class ManifestTests(unittest.TestCase):
    def test_round_trip(self):
        original = Manifest(
            app=AppConfig(
                name="Hello Pi",
                runtime="python",
                start="python3 app.py",
                port=8123,
                description="A tiny service",
            ),
            environment={"API_TOKEN": ""},
        )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "repobox.toml"
            path.write_text(original.to_toml(), encoding="utf-8")
            loaded = Manifest.from_path(path)
        self.assertEqual(loaded, original)
        self.assertEqual(loaded.app.slug, "hello-pi")

    def test_invalid_port(self):
        manifest = Manifest(app=AppConfig(name="bad", runtime="python", start="x", port=70000))
        with self.assertRaises(ManifestError):
            manifest.validate()

    def test_rejects_shell_in_package_name(self):
        text = """
schema_version = 1
[app]
name = "bad"
runtime = "python"
start = "python3 app.py"
port = 8080
healthcheck = "/"
[build]
system_packages = ["python3; reboot"]
[device]
targets = ["pi5"]
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "repobox.toml"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ManifestError):
                Manifest.from_path(path)

    def test_rejects_unsafe_healthcheck(self):
        manifest = Manifest(
            app=AppConfig(
                name="unsafe-health",
                runtime="python",
                start="python3 app.py",
                healthcheck="/health;shutdown now",
            )
        )
        with self.assertRaises(ManifestError):
            manifest.validate()

    def test_rejects_newline_in_service_fields(self):
        manifest = Manifest(
            app=AppConfig(
                name="unsafe\n[Service]",
                runtime="python",
                start="python3 app.py\nExecStart=/bin/reboot",
            )
        )
        with self.assertRaises(ManifestError):
            manifest.validate()


if __name__ == "__main__":
    unittest.main()
