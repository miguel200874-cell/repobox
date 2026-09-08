<p align="center">
  <img src="assets/logo.svg" width="520" alt="Repo2Box">
</p>

<p align="center"><strong>Turn a repository into a Raspberry Pi service.</strong></p>

<p align="center">
  One repository · One bootable image · Python & Node.js · Pi 4 & Pi 5
</p>

> **Alpha:** Repo2Box can create a bootable Raspberry Pi OS `.img` containing
> the application, or use a smaller SSH bundle for fast updates. Image builds
> use the official Raspberry Pi `rpi-image-gen` backend pinned to `v2.7.0`.

[Leia em português](docs/README.pt-BR.md)

## The ten-second demo

Create the source tree for a bootable image on any operating system:

```bash
repobox image https://github.com/you/my-app \
  --target pi5 \
  --prepare-only
```

Compile it on Linux with the official image engine:

```bash
repobox image https://github.com/you/my-app \
  --target pi5 \
  --engine-dir ./rpi-image-gen
```

The result is `dist/my-app-pi5.img`: Raspberry Pi OS, dependencies, a
least-privilege service user and the application enabled at boot.

For a Pi that already has Raspberry Pi OS, deploy without rewriting the card:

```bash
repobox deploy https://github.com/you/my-app \
  --target pi5 \
  --host pi@raspberrypi.local
```

Repo2Box clones the repository, detects the runtime and entry point, excludes
common secrets and generates either a complete OS image or a reviewable update
bundle.

```text
repository ──► detect ──► manifest ──┬─► bootable .img ─► SD card
                                    └─► SSH bundle ────► running Pi
```

## Why

Great projects are trapped behind setup guides. Repo2Box makes the deployment
step inspectable and repeatable without requiring every project author to
become an embedded-Linux expert.

## Supported in v0.2

| Runtime | Detection | Dependency install | Start detection |
|---|---:|---:|---:|
| Plain Python | yes | yes | `app.py`, `main.py`, `server.py` |
| FastAPI | yes | yes | `uvicorn module:app` |
| Flask | yes | yes | `flask --app module:app` |
| Django | yes | yes | `manage.py runserver` |
| Node.js | yes | yes | `start`, `serve`, or `dev` script |

Targets: Raspberry Pi 4 and Raspberry Pi 5 running a 64-bit Raspberry Pi OS.

## Build a bootable image

The easiest route from Windows or macOS is the included GitHub workflow:

1. Publish the repository on GitHub.
2. Open **Actions → Build Raspberry Pi image → Run workflow**.
3. Choose `pi4` or `pi5` and download the `.img.xz` artifact.
4. In Raspberry Pi Imager, choose **Use custom** and select that file.

The Imager is only writing Repo2Box's finished image to the card. It is no
longer downloading or configuring a separate operating system, and SSH is not
part of this first-install path.

For a local Linux build, install the official engine once:

```bash
git clone --branch v2.7.0 --depth 1 \
  https://github.com/raspberrypi/rpi-image-gen.git
sudo ./rpi-image-gen/install_deps.sh

repobox image examples/hello-python \
  --target pi5 \
  --hostname repobox \
  --ssh-public-key ~/.ssh/id_ed25519.pub \
  --engine-dir ./rpi-image-gen
```

The SSH key is optional. Without it the default login remains locked and the
application still starts normally. With it, Repo2Box enables key-only SSH for
the `pi` administrator; private keys are always rejected.

Image compilation is intentionally Linux-only because it creates partitions,
filesystems and a complete ARM64 root filesystem. Preparing the image source
works everywhere with `--prepare-only`.

See [the image-builder design and security notes](docs/image-builder.md).

## Install for development

Requires Python 3.11 or newer and Git. SSH and SCP are only needed for remote
deployment.

```bash
git clone https://github.com/miguel200874-cell/repobox.git
cd repobox
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
repobox doctor
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Quick start without a Pi

Analyse the included example and build both targets:

```bash
repobox analyze examples/hello-python --output demo.toml --force
repobox validate examples/hello-python/repobox.toml
repobox build examples/hello-python --target pi4 --output-dir dist
repobox build examples/hello-python --target pi5 --output-dir dist
repobox inspect dist/repo2box-hello-pi5-arm64.rbx.tar.gz
```

The bundle includes the application, manifest, checksums, systemd unit,
environment template, installer and conservative uninstaller.

## Deploy to a Pi

Start with a clean Pi running 64-bit Raspberry Pi OS, enable SSH, then run:

```bash
repobox deploy examples/hello-python \
  --target pi5 \
  --host pi@raspberrypi.local
```

Preview the SSH/SCP operations without connecting:

```bash
repobox deploy examples/hello-python \
  --target pi5 \
  --host pi@raspberrypi.local \
  --dry-run
```

After installation, visit `http://raspberrypi.local:8080` and inspect logs:

```bash
ssh pi@raspberrypi.local
journalctl -u repobox-repobox-hello -f
```

## `repobox.toml`

Auto-detection creates a manifest that is meant to be reviewed and committed:

```toml
schema_version = 1

[app]
name = "My API"
runtime = "python"
start = "python3 -m uvicorn api:app --host 0.0.0.0 --port 8080"
port = 8080
healthcheck = "/health"

[build]
system_packages = ["python3", "python3-venv", "python3-pip"]
ignore = [".git", ".env", "*.key", "*.pem", ".venv", "node_modules"]

[device]
targets = ["pi4", "pi5"]

[environment]
API_TOKEN = ""
```

Secrets should be configured on the Pi in `/etc/repobox/<app>.env`; do not put
real secrets in the manifest.

## Safety model

Repo2Box deliberately does not hide its installer. Every generated bundle is
reviewable and includes SHA-256 checksums. Symlinks and common secret files are
excluded, but Repo2Box cannot determine whether arbitrary application code is
safe. Read [SECURITY.md](SECURITY.md) before deploying third-party code.

## Roadmap

- [x] Python and Node.js detection
- [x] deterministic Pi 4/Pi 5 install bundles
- [x] SSH deployment
- [x] systemd service generation and basic hardening
- [x] health-check verification after deployment
- [ ] first-boot Wi-Fi portal
- [x] bootable `.img` output through Raspberry Pi `rpi-image-gen`
- [ ] signed releases and A/B updates
- [ ] optional cloud builds and fleet management

## Project principles

1. Local-first: no account is required.
2. Inspectable: generated scripts remain readable.
3. Conservative: ambiguity becomes a manifest edit, not a dangerous guess.
4. Reproducible: the same source and manifest produce the same bundle.
5. Useful free core: paid hosting must sell convenience, not artificial locks.

MIT licensed. Built for makers who want software to leave the laptop.
