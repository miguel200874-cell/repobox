from __future__ import annotations

import fnmatch
import gzip
import hashlib
import json
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .errors import BuildError
from .manifest import Manifest


MAX_BUNDLE_BYTES = 250 * 1024 * 1024
MAX_FILE_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class BuildResult:
    path: Path
    sha256: str
    file_count: int
    source_bytes: int


def _ignored(relative: Path, patterns: tuple[str, ...]) -> bool:
    posix = relative.as_posix()
    return any(
        fnmatch.fnmatch(posix, pattern)
        or fnmatch.fnmatch(relative.name, pattern)
        or any(fnmatch.fnmatch(part, pattern) for part in relative.parts)
        for pattern in patterns
    )


def _copy_source(source: Path, destination: Path, patterns: tuple[str, ...]) -> tuple[int, int]:
    file_count = 0
    total_bytes = 0
    destination = destination.resolve()
    for path in sorted(source.rglob("*")):
        if path.resolve() == destination or destination in path.resolve().parents:
            continue
        relative = path.relative_to(source)
        if _ignored(relative, patterns):
            continue
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise BuildError(f"Cannot inspect {relative}: {exc}") from exc
        if size > MAX_FILE_BYTES:
            raise BuildError(f"File is larger than 50 MiB: {relative}")
        total_bytes += size
        if total_bytes > MAX_BUNDLE_BYTES:
            raise BuildError("Source exceeds the 250 MiB safety limit.")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        file_count += 1
    if file_count == 0:
        raise BuildError("No source files remain after applying ignore rules.")
    return file_count, total_bytes


def _shell_single(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _service(manifest: Manifest) -> str:
    slug = manifest.app.slug
    app_dir = f"/opt/repobox/apps/{slug}"
    path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    if manifest.app.runtime == "python":
        path = f"{app_dir}/.venv/bin:" + path
    return f"""[Unit]
Description=Repo2Box application: {manifest.app.name}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=repobox
Group=repobox
WorkingDirectory={app_dir}/current
Environment=PORT={manifest.app.port}
Environment=HOST=0.0.0.0
Environment=PATH={path}
EnvironmentFile=-/etc/repobox/{slug}.env
ExecStart=/bin/bash -lc {_shell_single(manifest.app.start)}
Restart=on-failure
RestartSec=3
TimeoutStopSec=20
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full
ReadWritePaths=/var/lib/repobox/{slug} {app_dir}

[Install]
WantedBy=multi-user.target
"""


def _environment_file(manifest: Manifest) -> str:
    lines = ["# Configure values, then run: sudo systemctl restart repobox-" + manifest.app.slug]
    for key, value in sorted(manifest.environment.items()):
        clean = value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace('"', '\\"')
        lines.append(f'{key}="{clean}"')
    return "\n".join(lines) + "\n"


def _install_script(manifest: Manifest, target: str) -> str:
    slug = manifest.app.slug
    packages = " ".join(manifest.build.system_packages)
    runtime_install = ""
    if manifest.app.runtime == "python":
        runtime_install = f"""
rm -rf "$APP_DIR/.venv"
runuser -u repobox -- python3 -m venv "$APP_DIR/.venv"
if [ -f "$RELEASE_DIR/requirements.txt" ]; then
  runuser -u repobox -- "$APP_DIR/.venv/bin/python" -m pip install --disable-pip-version-check -r "$RELEASE_DIR/requirements.txt"
elif [ -f "$RELEASE_DIR/pyproject.toml" ]; then
  runuser -u repobox -- "$APP_DIR/.venv/bin/python" -m pip install --disable-pip-version-check "$RELEASE_DIR"
fi
"""
    elif manifest.app.runtime == "node":
        runtime_install = """
if [ -f "$RELEASE_DIR/package-lock.json" ]; then
  runuser -u repobox -- npm --prefix "$RELEASE_DIR" ci --omit=dev
else
  runuser -u repobox -- npm --prefix "$RELEASE_DIR" install --omit=dev
fi
"""
    return f"""#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Repo2Box installer must run as root. Try: sudo ./repobox/install.sh" >&2
  exit 1
fi

EXPECTED_TARGET={_shell_single(target)}
PI_MODEL="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || true)"
case "$EXPECTED_TARGET:$PI_MODEL" in
  pi4:*"Raspberry Pi 4"*|pi5:*"Raspberry Pi 5"*) ;;
  *)
    echo "Warning: bundle target is $EXPECTED_TARGET but this device reports: ${{PI_MODEL:-unknown}}" >&2
    echo "Set REPOBOX_ALLOW_TARGET_MISMATCH=1 to continue on a different machine." >&2
    [ "${{REPOBOX_ALLOW_TARGET_MISMATCH:-0}}" = "1" ] || exit 2
    ;;
esac

SLUG={_shell_single(slug)}
APP_DIR="/opt/repobox/apps/$SLUG"
RELEASE_DIR="$APP_DIR/current"
STATE_DIR="/var/lib/repobox/$SLUG"
CONFIG_DIR="/etc/repobox"
BUNDLE_ROOT="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)"

(cd "$BUNDLE_ROOT" && sha256sum --check SHA256SUMS)

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl {packages}

getent group repobox >/dev/null || groupadd --system repobox
id -u repobox >/dev/null 2>&1 || useradd --system --gid repobox --home-dir /var/lib/repobox --shell /usr/sbin/nologin repobox

install -d -m 0755 "$APP_DIR" "$STATE_DIR" "$CONFIG_DIR"
rm -rf "$RELEASE_DIR"
install -d -m 0755 "$RELEASE_DIR"
cp -a "$BUNDLE_ROOT/app/." "$RELEASE_DIR/"
chown -R repobox:repobox "$APP_DIR" "$STATE_DIR"

{runtime_install.strip()}

install -m 0644 "$BUNDLE_ROOT/repobox/repobox-{slug}.service" "/etc/systemd/system/repobox-{slug}.service"
if [ ! -f "$CONFIG_DIR/{slug}.env" ]; then
  install -m 0600 "$BUNDLE_ROOT/repobox/environment.example" "$CONFIG_DIR/{slug}.env"
fi
systemctl daemon-reload
systemctl enable --now "repobox-{slug}.service"

HEALTH_URL={_shell_single(f"http://127.0.0.1:{manifest.app.port}{manifest.app.healthcheck}")}
HEALTHY=0
for _attempt in $(seq 1 20); do
  if curl --fail --silent --show-error --max-time 2 "$HEALTH_URL" >/dev/null; then
    HEALTHY=1
    break
  fi
  sleep 1
done
if [ "$HEALTHY" -ne 1 ]; then
  echo "Health check failed: $HEALTH_URL" >&2
  journalctl -u "repobox-{slug}.service" --no-pager -n 40 >&2 || true
  exit 3
fi

echo
echo "Repo2Box installed {manifest.app.name}."
echo "Service: repobox-{slug}.service"
echo "URL: http://$(hostname -I | awk '{{print $1}}'):{manifest.app.port}"
echo "Logs: journalctl -u repobox-{slug} -f"
"""


def _uninstall_script(manifest: Manifest) -> str:
    slug = manifest.app.slug
    return f"""#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || {{ echo "Run with sudo." >&2; exit 1; }}
systemctl disable --now repobox-{slug}.service 2>/dev/null || true
rm -f /etc/systemd/system/repobox-{slug}.service
systemctl daemon-reload
echo "Service removed. Application data remains in /opt/repobox/apps/{slug} and /var/lib/repobox/{slug}."
"""


def _write_text(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    if executable:
        path.chmod(0o755)


def _checksums(root: Path) -> str:
    lines: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root).as_posix()}")
    return "\n".join(lines) + "\n"


def _tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = 0
    if info.isdir():
        info.mode = 0o755
    elif info.name.endswith(".sh"):
        info.mode = 0o755
    else:
        info.mode = 0o644
    return info


def build_bundle(source: Path, manifest: Manifest, target: str, output_dir: Path) -> BuildResult:
    manifest.validate()
    if target not in manifest.device.targets:
        raise BuildError(f"Target {target!r} is not enabled by the manifest.")
    source = source.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{manifest.app.slug}-{target}-arm64.rbx.tar.gz"
    output_path = (output_dir / filename).resolve()
    if output_dir.resolve() not in output_path.parents:
        raise BuildError("Unsafe output path.")

    with tempfile.TemporaryDirectory(prefix="repobox-build-") as temporary:
        staging = Path(temporary) / f"{manifest.app.slug}-{target}"
        app_dir = staging / "app"
        app_dir.mkdir(parents=True)
        file_count, source_bytes = _copy_source(source, app_dir, manifest.build.ignore)

        metadata = {
            "schema_version": manifest.schema_version,
            "name": manifest.app.name,
            "slug": manifest.app.slug,
            "runtime": manifest.app.runtime,
            "target": target,
            "port": manifest.app.port,
            "healthcheck": manifest.app.healthcheck,
        }
        _write_text(staging / "repobox.toml", manifest.to_toml())
        _write_text(staging / "repobox" / "runtime.json", json.dumps(metadata, indent=2) + "\n")
        _write_text(staging / "repobox" / f"repobox-{manifest.app.slug}.service", _service(manifest))
        _write_text(staging / "repobox" / "environment.example", _environment_file(manifest))
        _write_text(staging / "repobox" / "install.sh", _install_script(manifest, target), executable=True)
        _write_text(staging / "repobox" / "uninstall.sh", _uninstall_script(manifest), executable=True)
        _write_text(
            staging / "README-INSTALL.txt",
            f"""Repo2Box bundle for {manifest.app.name}

Target: Raspberry Pi {target.removeprefix('pi')}
Runtime: {manifest.app.runtime}

1. Copy this archive to a Raspberry Pi running 64-bit Raspberry Pi OS.
2. Extract it: tar -xzf {filename}
3. Enter the extracted directory.
4. Install it: sudo ./repobox/install.sh

Review repobox.toml and repobox/install.sh before installation.
Never install a bundle from an untrusted repository.
""",
        )
        _write_text(staging / "SHA256SUMS", _checksums(staging))

        with output_path.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as archive:
                    archive.add(staging, arcname=staging.name, filter=_tar_filter)

    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return BuildResult(output_path, digest, file_count, source_bytes)
