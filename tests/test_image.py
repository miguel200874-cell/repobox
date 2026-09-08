import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repobox.errors import ImageBuildError
from repobox.image import build_image, prepare_image_source
from repobox.manifest import AppConfig, BuildConfig, Manifest


class ImageTests(unittest.TestCase):
    def _project(self, root: Path) -> Manifest:
        (root / "app.py").write_text("print('image ready')\n", encoding="utf-8")
        return Manifest(
            app=AppConfig(
                name="Image Demo",
                runtime="python",
                start="python3 app.py",
                port=8080,
                healthcheck="/health",
            ),
            build=BuildConfig(system_packages=("python3", "python3-venv", "python3-pip"), ignore=()),
        )

    def test_prepares_rpi_image_gen_source_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            root.mkdir()
            manifest = self._project(root)
            plan = prepare_image_source(root, manifest, "pi4", root / "dist", hostname="demo-pi")
            config = plan.config_path.read_text(encoding="utf-8")
            layer = plan.layer_path.read_text(encoding="utf-8")
            app = (
                plan.workspace
                / "layer"
                / "repobox-app.rootfs-overlay"
                / "opt"
                / "repobox"
                / "apps"
                / "image-demo"
                / "current"
                / "app.py"
            )
            unit = (
                plan.workspace
                / "layer"
                / "repobox-app.rootfs-overlay"
                / "etc"
                / "systemd"
                / "system"
                / "repobox-image-demo.service"
            )

            self.assertTrue(app.is_file())
            self.assertTrue(unit.is_file())
            self.assertIn("layer: rpi4", config)
            self.assertIn("hostname: demo-pi", config)
            self.assertIn("X-Env-Layer-Name: repobox-app", layer)
            self.assertIn("chroot --userspec=repobox:repobox", layer)
            self.assertIn("enable-units", layer)
            self.assertIn('enable-units "$1" avahi-daemon', layer)

    def test_workspace_requires_force_to_replace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            root.mkdir()
            manifest = self._project(root)
            output = Path(temp) / "out"
            prepare_image_source(root, manifest, "pi5", output)
            with self.assertRaises(ImageBuildError):
                prepare_image_source(root, manifest, "pi5", output)
            replaced = prepare_image_source(root, manifest, "pi5", output, force=True)
            self.assertTrue(replaced.config_path.is_file())

    def test_rejects_unsafe_hostname(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self._project(root)
            with self.assertRaises(ImageBuildError):
                prepare_image_source(root, manifest, "pi5", root / "out", hostname="pi; reboot")

    def test_embeds_supported_public_key_and_enables_key_only_ssh(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            root.mkdir()
            manifest = self._project(root)
            key = Path(temp) / "admin.pub"
            key.write_text("ssh-ed25519 QUJDREVGRw== engineer@example\n", encoding="utf-8")
            plan = prepare_image_source(root, manifest, "pi5", Path(temp) / "out", ssh_public_key=key)
            config = plan.config_path.read_text(encoding="utf-8")
            self.assertIn("pubkey_only: y", config)
            self.assertIn("user1sudo: nopasswd", config)
            self.assertEqual(
                (plan.workspace / "ssh-authorized-key.pub").read_text(encoding="utf-8"),
                "ssh-ed25519 QUJDREVGRw== engineer@example\n",
            )

    def test_rejects_private_or_malformed_ssh_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            root.mkdir()
            manifest = self._project(root)
            key = Path(temp) / "bad-key"
            key.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\n", encoding="utf-8")
            with self.assertRaises(ImageBuildError):
                prepare_image_source(root, manifest, "pi5", Path(temp) / "out", ssh_public_key=key)

    def test_build_moves_image_and_hashes_in_chunks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            plan = prepare_image_source(project, self._project(project), "pi5", root / "plan")
            engine = root / "engine"
            engine.mkdir()
            (engine / "rpi-image-gen").write_text("#!/bin/sh\n", encoding="utf-8")

            def fake_run(command, **_kwargs):
                if "build" in command:
                    generated = engine / "work" / f"image-{plan.image_name}" / f"{plan.image_name}.img"
                    generated.parent.mkdir(parents=True)
                    generated.write_bytes(b"bootable-image")
                return subprocess.CompletedProcess(command, 0)

            with patch("repobox.image.platform.system", return_value="Linux"), patch(
                "repobox.image.subprocess.run", side_effect=fake_run
            ):
                result = build_image(plan, engine, root / "final")

            self.assertEqual(result.path.read_bytes(), b"bootable-image")
            self.assertEqual(result.sha256, hashlib.sha256(b"bootable-image").hexdigest())


if __name__ == "__main__":
    unittest.main()
