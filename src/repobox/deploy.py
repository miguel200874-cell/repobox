from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .errors import DeployError


HOST_PATTERN = re.compile(r"^(?:[A-Za-z0-9._-]+@)?[A-Za-z0-9._-]+$")


def deploy_bundle(
    bundle: Path,
    host: str,
    *,
    port: int = 22,
    identity: Path | None = None,
    dry_run: bool = False,
) -> tuple[list[str], list[str]]:
    if not HOST_PATTERN.fullmatch(host):
        raise DeployError("Host must look like pi@raspberrypi.local or pi@192.168.1.20.")
    if not 1 <= port <= 65535:
        raise DeployError("SSH port must be between 1 and 65535.")
    bundle = bundle.resolve()
    if not bundle.is_file():
        raise DeployError(f"Bundle not found: {bundle}")
    scp = shutil.which("scp")
    ssh = shutil.which("ssh")
    if scp is None or ssh is None:
        raise DeployError("OpenSSH client is required (ssh and scp commands).")

    remote_name = bundle.name
    if not re.fullmatch(r"[A-Za-z0-9._-]+", remote_name):
        raise DeployError("Bundle filename contains unsafe characters.")
    remote_path = f"/tmp/{remote_name}"
    common: list[str] = []
    if identity is not None:
        identity = identity.expanduser().resolve()
        if not identity.is_file():
            raise DeployError(f"SSH identity not found: {identity}")
        common.extend(["-i", str(identity)])

    scp_command = [scp, *common, "-P", str(port), str(bundle), f"{host}:{remote_path}"]
    remote_command = (
        "set -eu; "
        "workdir=$(mktemp -d); "
        f"tar -xzf {remote_path} -C \"$workdir\"; "
        "bundle_dir=$(find \"$workdir\" -mindepth 1 -maxdepth 1 -type d -print -quit); "
        "sudo \"$bundle_dir/repobox/install.sh\"; "
        f"rm -f {remote_path}; "
        "rm -rf \"$workdir\""
    )
    ssh_command = [ssh, *common, "-p", str(port), host, remote_command]
    if dry_run:
        return scp_command, ssh_command

    for command, label in ((scp_command, "copy"), (ssh_command, "install")):
        process = subprocess.run(command, check=False)
        if process.returncode != 0:
            raise DeployError(f"Remote {label} step failed with exit code {process.returncode}.")
    return scp_command, ssh_command
