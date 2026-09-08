from __future__ import annotations

import json
import re
from pathlib import Path

from .errors import AnalysisError
from .manifest import AppConfig, BuildConfig, DeviceConfig, Manifest


TEXT_LIMIT = 512_000
SOURCE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx"}
COMMON_ENV = {"PORT", "HOST", "NODE_ENV", "PYTHONUNBUFFERED"}


def _read_text(path: Path) -> str:
    try:
        if path.stat().st_size > TEXT_LIMIT:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _source_files(root: Path) -> list[Path]:
    ignored = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if any(part in ignored for part in path.relative_to(root).parts):
            continue
        files.append(path)
        if len(files) >= 300:
            break
    return files


def _module_name(root: Path, path: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    return ".".join(relative.parts)


def _detect_port(texts: list[str]) -> int:
    patterns = [
        r"(?:PORT|port)\s*[:=]\s*(\d{2,5})",
        r"listen\s*\(\s*(\d{2,5})",
        r"run\s*\([^)]*port\s*=\s*(\d{2,5})",
    ]
    for text in texts:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                port = int(match.group(1))
                if 1 <= port <= 65535:
                    return port
    return 8080


def _detect_environment(texts: list[str]) -> dict[str, str]:
    keys: set[str] = set()
    patterns = [
        r"os\.(?:getenv|environ\.get)\(\s*['\"]([A-Z_][A-Z0-9_]*)['\"]",
        r"process\.env\.([A-Z_][A-Z0-9_]*)",
        r"process\.env\[['\"]([A-Z_][A-Z0-9_]*)['\"]\]",
    ]
    for text in texts:
        for pattern in patterns:
            keys.update(re.findall(pattern, text))
    return {key: "" for key in sorted(keys - COMMON_ENV)}


def _python_manifest(root: Path, files: list[Path], texts: list[str], name: str) -> Manifest:
    port = _detect_port(texts)
    start = ""
    description = "Python service detected by Repo2Box"

    if (root / "manage.py").exists():
        start = f"python3 manage.py runserver 0.0.0.0:{port}"
        description = "Django application"
    else:
        for path, text in zip(files, texts):
            fastapi = re.search(r"([A-Za-z_]\w*)\s*=\s*FastAPI\s*\(", text)
            if fastapi:
                start = f"python3 -m uvicorn {_module_name(root, path)}:{fastapi.group(1)} --host 0.0.0.0 --port {port}"
                description = "FastAPI application"
                break
            flask = re.search(r"([A-Za-z_]\w*)\s*=\s*Flask\s*\(", text)
            if flask:
                start = f"python3 -m flask --app {_module_name(root, path)}:{flask.group(1)} run --host 0.0.0.0 --port {port}"
                description = "Flask application"
                break

    if not start:
        for candidate in ("app.py", "main.py", "server.py", "src/app.py", "src/main.py"):
            if (root / candidate).exists():
                start = f"python3 {candidate}"
                break
    if not start:
        raise AnalysisError(
            "Python was detected, but no safe entry point was found. "
            "Create repobox.toml and set app.start explicitly."
        )

    packages = ("python3", "python3-venv", "python3-pip")
    return Manifest(
        app=AppConfig(name=name, runtime="python", start=start, port=port, description=description),
        build=BuildConfig(system_packages=packages),
        device=DeviceConfig(),
        environment=_detect_environment(texts),
    )


def _node_manifest(root: Path, texts: list[str], name: str) -> Manifest:
    package_path = root / "package.json"
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"Cannot parse package.json: {exc}") from exc
    scripts = package.get("scripts", {})
    if "start" in scripts:
        start = "npm run start"
    elif "serve" in scripts:
        start = "npm run serve -- --host 0.0.0.0"
    elif "dev" in scripts:
        start = "npm run dev -- --host 0.0.0.0"
    else:
        raise AnalysisError("Node.js was detected, but package.json has no start, serve, or dev script.")
    return Manifest(
        app=AppConfig(
            name=str(package.get("name") or name),
            runtime="node",
            start=start,
            port=_detect_port(texts),
            description=str(package.get("description") or "Node.js service detected by Repo2Box"),
        ),
        build=BuildConfig(system_packages=("nodejs", "npm")),
        device=DeviceConfig(),
        environment=_detect_environment(texts),
    )


def analyse(root: Path, name: str | None = None) -> Manifest:
    root = root.resolve()
    files = _source_files(root)
    texts = [_read_text(path) for path in files]
    project_name = name or root.name
    has_node = (root / "package.json").exists()
    has_python = any((root / filename).exists() for filename in ("requirements.txt", "pyproject.toml", "Pipfile")) or any(
        path.suffix == ".py" for path in files
    )
    if has_node:
        manifest = _node_manifest(root, texts, project_name)
    elif has_python:
        manifest = _python_manifest(root, files, texts, project_name)
    else:
        raise AnalysisError("No supported Python or Node.js project was detected.")
    manifest.validate()
    return manifest
