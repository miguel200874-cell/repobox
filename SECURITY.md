# Security policy

Repo2Box packages and runs repository code. Treat every repository and every
generated installer as untrusted until you review it.

## Alpha guarantees

- `.env`, private-key patterns, virtual environments and dependency folders are
  excluded by default.
- symbolic links are not packaged.
- bundle members are inspected for path traversal.
- package names use a restricted character set.
- SSH deployment uses argument arrays instead of a local shell.
- the generated service runs as the unprivileged `repobox` user with basic
  systemd hardening.
- image builds use an isolated Linux environment, a pinned official
  `rpi-image-gen` release, and install application dependencies as the
  unprivileged service user inside the target filesystem.

Repo2Box does **not** audit the application itself. Installation runs package
managers and the application eventually executes the repository's configured
start command. Only deploy code you trust.

Never put Wi-Fi passwords, private SSH keys, API tokens, or other secrets in a
public image build. Configure secrets locally after flashing or through a
future dedicated provisioning mechanism.

Please report vulnerabilities privately to the repository owner before opening
a public issue.
