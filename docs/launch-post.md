# Launch kit

## Headline

**I built a tool that turns a GitHub repository into a bootable Raspberry Pi image.**

## Short post

What if a repository could become a complete Raspberry Pi OS image?

```bash
repobox image https://github.com/you/app --target pi5 --engine-dir ./rpi-image-gen
```

Repo2Box detects Python/Node, creates a reviewable manifest, excludes common
secrets, builds the operating-system image and enables the app as a hardened
systemd service. Flash the resulting `.img`, turn on the Pi, and the app starts.

No account. No cloud. MIT licensed.

## 45-second demo script

1. Show the `hello-python` repository and its tiny manifest.
2. Trigger **Build Raspberry Pi image** in GitHub Actions.
3. Download the `.img.xz` artifact and show its checksum.
4. Flash it with **Use custom** in Raspberry Pi Imager.
5. Boot the Pi and open `repobox.local:8080` without an SSH installation.
6. Show the same workflow with `pi4` selected.
7. End on: “A repository should be able to become a device.”

## Launch checklist

- Repository links point to `miguel200874-cell/repobox`.
- Record the demo on a real Pi 4 and Pi 5.
- Publish the exact source commit used in the recording.
- Add terminal recording or GIF below the logo.
- Enable GitHub Discussions and issue templates.
- Share in Raspberry Pi, Python, self-hosted and maker communities.
- Ask for runtime contributions, not generic stars.
