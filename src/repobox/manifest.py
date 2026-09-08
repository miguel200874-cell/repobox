from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ManifestError


SCHEMA_VERSION = 1
SUPPORTED_RUNTIMES = {"python", "node"}
SUPPORTED_TARGETS = {"pi4", "pi5"}


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not value:
        raise ManifestError("The application name must contain a letter or number.")
    return value[:48]


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_quote(item) for item in values) + "]"


@dataclass(frozen=True)
class AppConfig:
    name: str
    runtime: str
    start: str
    port: int = 8080
    healthcheck: str = "/"
    description: str = ""

    @property
    def slug(self) -> str:
        return slugify(self.name)


@dataclass(frozen=True)
class BuildConfig:
    system_packages: tuple[str, ...] = ()
    ignore: tuple[str, ...] = (
        ".git",
        ".github",
        ".env",
        ".env.*",
        "*.key",
        "*.pem",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
    )


@dataclass(frozen=True)
class DeviceConfig:
    targets: tuple[str, ...] = ("pi4", "pi5")


@dataclass(frozen=True)
class Manifest:
    app: AppConfig
    build: BuildConfig = field(default_factory=BuildConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)
    environment: dict[str, str] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def validate(self) -> None:
        errors: list[str] = []
        if self.schema_version != SCHEMA_VERSION:
            errors.append(f"schema_version must be {SCHEMA_VERSION}")
        if self.app.runtime not in SUPPORTED_RUNTIMES:
            errors.append(f"runtime must be one of: {', '.join(sorted(SUPPORTED_RUNTIMES))}")
        if not self.app.start.strip():
            errors.append("app.start cannot be empty")
        if not re.fullmatch(r"[^\r\n\x00]{1,1000}", self.app.start):
            errors.append("app.start must be one line and at most 1000 characters")
        if not re.fullmatch(r"[^\r\n\x00-\x1f\x7f]{1,100}", self.app.name):
            errors.append("app.name must be one printable line of at most 100 characters")
        if self.app.description and not re.fullmatch(r"[^\r\n\x00-\x1f\x7f]{1,200}", self.app.description):
            errors.append("app.description must be one printable line of at most 200 characters")
        if not 1 <= self.app.port <= 65535:
            errors.append("app.port must be between 1 and 65535")
        if not re.fullmatch(r"/[A-Za-z0-9/_?&=.%:+~-]*", self.app.healthcheck):
            errors.append("app.healthcheck must be a safe URL path beginning with /")
        if not self.device.targets:
            errors.append("at least one device target is required")
        invalid_targets = set(self.device.targets) - SUPPORTED_TARGETS
        if invalid_targets:
            errors.append(f"unsupported targets: {', '.join(sorted(invalid_targets))}")
        invalid_packages = [p for p in self.build.system_packages if not re.fullmatch(r"[a-zA-Z0-9.+:-]+", p)]
        if invalid_packages:
            errors.append("system package names contain unsupported characters")
        invalid_env = [key for key in self.environment if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", key)]
        if invalid_env:
            errors.append(f"invalid environment names: {', '.join(invalid_env)}")
        try:
            self.app.slug
        except ManifestError as exc:
            errors.append(str(exc))
        if errors:
            raise ManifestError("Invalid repobox.toml:\n- " + "\n- ".join(errors))

    def to_toml(self) -> str:
        self.validate()
        lines = [
            f"schema_version = {self.schema_version}",
            "",
            "[app]",
            f"name = {_quote(self.app.name)}",
            f"runtime = {_quote(self.app.runtime)}",
            f"start = {_quote(self.app.start)}",
            f"port = {self.app.port}",
            f"healthcheck = {_quote(self.app.healthcheck)}",
            f"description = {_quote(self.app.description)}",
            "",
            "[build]",
            f"system_packages = {_array(self.build.system_packages)}",
            f"ignore = {_array(self.build.ignore)}",
            "",
            "[device]",
            f"targets = {_array(self.device.targets)}",
            "",
            "[environment]",
        ]
        for key in sorted(self.environment):
            lines.append(f"{key} = {_quote(self.environment[key])}")
        return "\n".join(lines) + "\n"

    @classmethod
    def from_path(cls, path: Path) -> "Manifest":
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ManifestError(f"Manifest not found: {path}") from exc
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ManifestError(f"Cannot read {path}: {exc}") from exc

        try:
            app_data = raw["app"]
            build_data = raw.get("build", {})
            device_data = raw.get("device", {})
            manifest = cls(
                schema_version=int(raw.get("schema_version", 0)),
                app=AppConfig(
                    name=str(app_data["name"]),
                    runtime=str(app_data["runtime"]),
                    start=str(app_data["start"]),
                    port=int(app_data.get("port", 8080)),
                    healthcheck=str(app_data.get("healthcheck", "/")),
                    description=str(app_data.get("description", "")),
                ),
                build=BuildConfig(
                    system_packages=tuple(str(x) for x in build_data.get("system_packages", [])),
                    ignore=tuple(str(x) for x in build_data.get("ignore", BuildConfig().ignore)),
                ),
                device=DeviceConfig(
                    targets=tuple(str(x) for x in device_data.get("targets", ("pi4", "pi5"))),
                ),
                environment={str(k): str(v) for k, v in raw.get("environment", {}).items()},
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ManifestError(f"Malformed manifest {path}: {exc}") from exc
        manifest.validate()
        return manifest
