import shutil
import tempfile
import unittest
from pathlib import Path

from repobox.deploy import deploy_bundle
from repobox.errors import DeployError


class DeployTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ssh") and shutil.which("scp"), "OpenSSH is not installed")
    def test_dry_run_uses_argument_arrays(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "safe-bundle.rbx.tar.gz"
            bundle.write_bytes(b"placeholder")
            scp_command, ssh_command = deploy_bundle(
                bundle, "pi@raspberrypi.local", port=2222, dry_run=True
            )
        self.assertEqual(scp_command[-1], "pi@raspberrypi.local:/tmp/safe-bundle.rbx.tar.gz")
        self.assertIn("2222", ssh_command)

    def test_rejects_shell_metacharacters_in_host(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "safe.rbx.tar.gz"
            bundle.write_bytes(b"placeholder")
            with self.assertRaises(DeployError):
                deploy_bundle(bundle, "pi@host;reboot", dry_run=True)


if __name__ == "__main__":
    unittest.main()
