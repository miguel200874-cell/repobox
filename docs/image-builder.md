# Bootable image builder

Repo2Box 0.2 turns a detected application into an external source tree for the
official Raspberry Pi `rpi-image-gen` project. The backend is pinned to tag
`v2.7.0`, commit `a7b6d4806183195f3efadb533f58c8e46393d057`.

## What goes into the image

- 64-bit Debian Trixie/Raspberry Pi OS minimal base
- Pi 4 or Pi 5 device firmware and kernel
- wired and wireless networking from the upstream minimal suite
- OpenSSH server with login locked by default
- optional key-only SSH access for the `pi` administrator
- Python or Node.js runtime and resolved project dependencies
- project source under `/opt/repobox/apps/<name>/current`
- hardened systemd service enabled at boot
- build metadata under `/usr/share/repobox`

No password, Wi-Fi credential, private key, `.env`, PEM file, or API token is
added by default. Supplying `--ssh-public-key` accepts only a one-line OpenSSH
public key and enables key-only administration.

## Why compilation runs on Linux

Preparing a source tree is portable. Compiling it creates partitions,
filesystems and an ARM64 root filesystem, so the official engine uses Linux
build tools. Repo2Box offers both routes:

```bash
# Any operating system: prepare and audit everything
repobox image ./app --target pi5 --prepare-only

# Linux: prepare and compile the final image
repobox image ./app --target pi5 --engine-dir ./rpi-image-gen
```

On Windows and macOS, the repository's **Build Raspberry Pi image** workflow
runs the same command on GitHub's ARM64 Linux runner and returns `.img.xz` plus
`SHA256SUMS`.

## Upstream references

- [rpi-image-gen repository](https://github.com/raspberrypi/rpi-image-gen)
- [v2.7.0 source](https://github.com/raspberrypi/rpi-image-gen/tree/v2.7.0)
- [external source and overlay execution](https://github.com/raspberrypi/rpi-image-gen/blob/v2.7.0/docs/execution/index.adoc)
- [configuration reference](https://github.com/raspberrypi/rpi-image-gen/blob/v2.7.0/docs/config/index.adoc)
