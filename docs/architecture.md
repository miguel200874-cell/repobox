# Architecture

## Current flow

1. `source.resolve_source` accepts a local directory or clones an HTTPS/SSH Git
   repository without recursively fetching submodules.
2. `analyzer.analyse` detects Python or Node.js, entry point, port and referenced
   environment variables.
3. `manifest.Manifest` validates the explicit deployment contract.
4. `builder.build_bundle` copies allow-listed project content, creates the
   service/install metadata, hashes it, and writes a deterministic archive.
5. `deploy.deploy_bundle` uses local `scp` and `ssh` executables without invoking
   a local shell.
6. The generated installer validates the Pi model, installs runtime packages,
   creates an unprivileged service user, resolves application dependencies, and
   starts a systemd unit.
7. `image.prepare_image_source` converts the same manifest into an external
   `rpi-image-gen` layer and root-filesystem overlay.
8. `image.build_image` validates the layer and invokes the pinned official
   Raspberry Pi image backend on Linux to create a bootable `.img`.

## Trust boundaries

```text
untrusted repository
        │
        ▼
 analyser + exclusions ──► reviewable manifest
        │
        ▼
 deterministic bundle ──► reviewable installer + checksums
        │
        ▼
   trusted Pi operator ──► package manager + untrusted app execution
```

Repo2Box protects its own packaging path; it does not sandbox or certify the
application. A later release should build inside disposable VMs, produce an
SBOM, scan known vulnerabilities, sign bundles, and use A/B operating-system
updates.

## Bootable-image path

The official Raspberry Pi `rpi-image-gen` is the image backend. Repo2Box emits
a self-contained external source tree containing a device configuration, an
application layer and a root-filesystem overlay. The layer installs packages,
creates a restricted service user, resolves dependencies and enables the
systemd unit during image construction.

The implemented boundary is:

```text
repository ─► Repo2Box manifest ─► generated rpi-image-gen layer
                                      │
                                      ▼
                    Linux ARM64 builder ─► .img ─► .img.xz artifact
```

Portable machines can prepare and inspect the source tree. Image compilation
runs on Linux because it requires partition, filesystem and root-filesystem
tooling. The included GitHub Actions workflow supplies that Linux ARM64 build
environment without requiring a second computer.
