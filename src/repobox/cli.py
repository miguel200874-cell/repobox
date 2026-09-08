from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

from . import __version__
from .analyzer import analyse
from .builder import BuildResult, build_bundle
from .deploy import deploy_bundle
from .errors import RepoBoxError
from .image import RPI_IMAGE_GEN_VERSION, build_image, prepare_image_source
from .manifest import Manifest
from .source import resolve_source


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repobox",
        description="Turn a Python or Node.js repository into a bootable image or deployable Raspberry Pi service.",
    )
    parser.add_argument("--version", action="version", version=f"Repo2Box {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    analyse_parser = sub.add_parser("analyze", help="Detect the runtime and create repobox.toml.")
    analyse_parser.add_argument("source", help="Local directory or HTTPS/SSH Git URL.")
    analyse_parser.add_argument("-o", "--output", type=Path, help="Manifest path (default: SOURCE/repobox.toml).")
    analyse_parser.add_argument("--name", help="Override the detected application name.")
    analyse_parser.add_argument("--force", action="store_true", help="Overwrite an existing manifest.")
    analyse_parser.set_defaults(handler=_cmd_analyze)

    validate_parser = sub.add_parser("validate", help="Validate a repobox.toml manifest.")
    validate_parser.add_argument("manifest", nargs="?", type=Path, default=Path("repobox.toml"))
    validate_parser.set_defaults(handler=_cmd_validate)

    build_parser = sub.add_parser("build", help="Build a deterministic Raspberry Pi install bundle.")
    _add_build_arguments(build_parser)
    build_parser.set_defaults(handler=_cmd_build)

    inspect_parser = sub.add_parser("inspect", help="List a bundle without extracting it.")
    inspect_parser.add_argument("bundle", type=Path)
    inspect_parser.add_argument("--json", action="store_true", dest="as_json")
    inspect_parser.set_defaults(handler=_cmd_inspect)

    deploy_parser = sub.add_parser("deploy", help="Build and install a project over SSH.")
    _add_build_arguments(deploy_parser)
    deploy_parser.add_argument("--host", required=True, help="SSH destination, e.g. pi@raspberrypi.local.")
    deploy_parser.add_argument("--ssh-port", type=int, default=22)
    deploy_parser.add_argument("--identity", type=Path, help="SSH private key path.")
    deploy_parser.add_argument("--dry-run", action="store_true", help="Print commands without connecting.")
    deploy_parser.set_defaults(handler=_cmd_deploy)

    image_parser = sub.add_parser("image", help="Build a bootable Raspberry Pi OS image containing the app.")
    _add_build_arguments(image_parser)
    image_parser.add_argument("--hostname", default="repobox", help="Hostname baked into the image.")
    image_parser.add_argument(
        "--ssh-public-key",
        type=Path,
        help="OpenSSH public key to enable secure pi-user administration (never use a private key).",
    )
    image_parser.add_argument(
        "--engine-dir",
        type=Path,
        help=f"Path to the official rpi-image-gen {RPI_IMAGE_GEN_VERSION} checkout.",
    )
    image_parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Generate the rpi-image-gen source tree without compiling the image.",
    )
    image_parser.add_argument("--force", action="store_true", help="Replace an existing image workspace.")
    image_parser.set_defaults(handler=_cmd_image)

    doctor_parser = sub.add_parser("doctor", help="Check local tools used by Repo2Box.")
    doctor_parser.set_defaults(handler=_cmd_doctor)
    return parser


def _add_build_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source", help="Local directory or HTTPS/SSH Git URL.")
    parser.add_argument("--target", choices=("pi4", "pi5"), required=True)
    parser.add_argument("--manifest", type=Path, help="Explicit repobox.toml path.")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("dist"))


def _manifest_for(source: Path, explicit: Path | None) -> tuple[Manifest, str]:
    if explicit is not None:
        return Manifest.from_path(explicit.expanduser().resolve()), "provided"
    local = source / "repobox.toml"
    if local.exists():
        return Manifest.from_path(local), "repository"
    return analyse(source), "detected"


def _print_result(result: BuildResult, manifest_source: str) -> None:
    print(f"Built: {result.path}")
    print(f"SHA-256: {result.sha256}")
    print(f"Source: {result.file_count} files, {result.source_bytes} bytes")
    print(f"Manifest: {manifest_source}")


def _cmd_analyze(args: argparse.Namespace) -> int:
    with resolve_source(args.source) as resolved:
        manifest = analyse(resolved.path, args.name)
        if args.output:
            output = args.output.expanduser().resolve()
        elif resolved._temporary is None:
            output = resolved.path / "repobox.toml"
        else:
            output = Path.cwd() / "repobox.toml"
        if output.exists() and not args.force:
            raise RepoBoxError(f"Refusing to overwrite {output}. Use --force.")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(manifest.to_toml(), encoding="utf-8", newline="\n")
        print(f"Created: {output}")
        print(f"Detected: {manifest.app.runtime} / {manifest.app.start}")
        if manifest.environment:
            print("Environment variables: " + ", ".join(manifest.environment))
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    manifest = Manifest.from_path(args.manifest.expanduser().resolve())
    print(f"Valid: {args.manifest} ({manifest.app.runtime}, {manifest.app.name})")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    with resolve_source(args.source) as resolved:
        manifest, origin = _manifest_for(resolved.path, args.manifest)
        result = build_bundle(resolved.path, manifest, args.target, args.output_dir.expanduser().resolve())
        _print_result(result, origin)
    return 0


def _safe_members(bundle: Path) -> list[tarfile.TarInfo]:
    with tarfile.open(bundle, "r:gz") as archive:
        members = archive.getmembers()
    for member in members:
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise RepoBoxError(f"Unsafe path in bundle: {member.name}")
    return members


def _cmd_inspect(args: argparse.Namespace) -> int:
    bundle = args.bundle.expanduser().resolve()
    if not bundle.is_file():
        raise RepoBoxError(f"Bundle not found: {bundle}")
    members = _safe_members(bundle)
    if args.as_json:
        print(json.dumps([{"name": m.name, "size": m.size, "mode": oct(m.mode)} for m in members], indent=2))
    else:
        for member in members:
            suffix = "/" if member.isdir() else ""
            print(f"{member.size:>10}  {member.name}{suffix}")
    return 0


def _cmd_deploy(args: argparse.Namespace) -> int:
    with resolve_source(args.source) as resolved:
        manifest, origin = _manifest_for(resolved.path, args.manifest)
        if args.dry_run:
            output_dir = args.output_dir.expanduser().resolve()
            result = build_bundle(resolved.path, manifest, args.target, output_dir)
            commands = deploy_bundle(
                result.path, args.host, port=args.ssh_port, identity=args.identity, dry_run=True
            )
            _print_result(result, origin)
            print("Dry run (arguments are shown one per line):")
            for command in commands:
                print("  " + " | ".join(command))
        else:
            with tempfile.TemporaryDirectory(prefix="repobox-deploy-") as temporary:
                result = build_bundle(resolved.path, manifest, args.target, Path(temporary))
                deploy_bundle(result.path, args.host, port=args.ssh_port, identity=args.identity)
                print(f"Deployed {manifest.app.name} to {args.host}:{manifest.app.port}")
    return 0


def _cmd_image(args: argparse.Namespace) -> int:
    output_dir = args.output_dir.expanduser().resolve()
    with resolve_source(args.source) as resolved:
        manifest, origin = _manifest_for(resolved.path, args.manifest)
        plan = prepare_image_source(
            resolved.path,
            manifest,
            args.target,
            output_dir,
            hostname=args.hostname,
            ssh_public_key=args.ssh_public_key,
            force=args.force,
        )
        print(f"Prepared: {plan.workspace}")
        print(f"Manifest: {origin}")
        print(f"Backend: Raspberry Pi rpi-image-gen {RPI_IMAGE_GEN_VERSION}")
        if args.prepare_only:
            print("Image source is ready; compilation was skipped by --prepare-only.")
            return 0

        configured_engine = args.engine_dir or (
            Path(os.environ["RPI_IMAGE_GEN_DIR"]) if "RPI_IMAGE_GEN_DIR" in os.environ else None
        )
        if configured_engine is None:
            raise RepoBoxError(
                "Set --engine-dir to an rpi-image-gen checkout, or use --prepare-only/GitHub Actions."
            )
        result = build_image(plan, configured_engine, output_dir)
        print(f"Image: {result.path}")
        print(f"SHA-256: {result.sha256}")
    return 0


def _cmd_doctor(_args: argparse.Namespace) -> int:
    checks = {
        "Python 3.11+": sys.version_info >= (3, 11),
        "Git": shutil.which("git") is not None,
        "SSH": shutil.which("ssh") is not None,
        "SCP": shutil.which("scp") is not None,
    }
    for name, ok in checks.items():
        print(f"[{'ok' if ok else '--'}] {name}")
    required = checks["Python 3.11+"]
    return 0 if required else 1


def run(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        return int(args.handler(args))
    except RepoBoxError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


def main() -> None:
    raise SystemExit(run())
