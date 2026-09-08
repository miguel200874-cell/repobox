from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import AnalysisError


@dataclass
class ResolvedSource:
    path: Path
    origin: str
    _temporary: tempfile.TemporaryDirectory[str] | None = None

    def close(self) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def __enter__(self) -> "ResolvedSource":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def is_git_url(value: str) -> bool:
    if value.startswith("git@"):
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"https", "ssh"} and bool(parsed.netloc)


def resolve_source(value: str) -> ResolvedSource:
    candidate = Path(value).expanduser()
    if candidate.exists():
        root = candidate.resolve()
        if not root.is_dir():
            raise AnalysisError(f"Source must be a directory: {root}")
        return ResolvedSource(root, str(root))

    if not is_git_url(value):
        raise AnalysisError(f"Source does not exist and is not a supported Git URL: {value}")
    if value.startswith("http://"):
        raise AnalysisError("Plain HTTP Git URLs are rejected. Use HTTPS or SSH.")
    git = shutil.which("git")
    if git is None:
        raise AnalysisError("Git is required to analyse a remote repository.")
    temporary = tempfile.TemporaryDirectory(prefix="repobox-source-")
    destination = Path(temporary.name) / "repository"
    process = subprocess.run(
        [git, "clone", "--depth", "1", "--no-recurse-submodules", value, str(destination)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
        check=False,
    )
    if process.returncode != 0:
        temporary.cleanup()
        message = process.stderr.strip().splitlines()[-1] if process.stderr.strip() else "unknown Git error"
        raise AnalysisError(f"Could not clone repository: {message}")
    return ResolvedSource(destination, value, temporary)
