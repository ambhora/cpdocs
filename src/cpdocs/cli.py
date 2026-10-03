# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""The ``cpdocs`` command."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .build import build_current, build_versions
from .config import DEFAULT_CONFIG, load_config
from .python_manifest import write_feature_sets as write_python_feature_sets
from .python_manifest import write_manifest as write_python_manifest


def _path(value: str) -> Path:
    return Path(value).expanduser()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cpdocs", description="Semantic API documentation")
    parser.add_argument("--version", action="version", version=f"cpdocs {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    def documentation(name: str, help_text: str) -> argparse.ArgumentParser:
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--config", type=_path, default=DEFAULT_CONFIG)
        command.add_argument(
            "--output",
            type=_path,
            default=Path("build"),
            help="output root; cpdocs writes below <output>/cpdocs (default: build)",
        )
        return command

    build = documentation("build", "document the working tree")
    build.add_argument("--label", default="main", help="version label of the working tree")

    documentation("versions", "document the configured versions")

    manifest = commands.add_parser("manifest", help="provide cpdocs contract files")
    kinds = manifest.add_subparsers(dest="kind", required=True)
    python = kinds.add_parser("python", help="plain pyproject.toml project")
    phases = python.add_subparsers(dest="phase", required=True)
    python_feature_sets = phases.add_parser("feature-sets", help="write feature-sets.json")
    python_feature_sets.add_argument("--source", type=_path, required=True)
    python_feature_sets.add_argument("--output", type=_path, required=True)
    python_manifest = phases.add_parser("build", help="build one feature set and write manifest.json")
    python_manifest.add_argument("--source", type=_path, required=True)
    python_manifest.add_argument("--feature-set", type=_path, required=True)
    python_manifest.add_argument("--output", type=_path, required=True)
    python_manifest.add_argument("--package", required=True)
    python_manifest.add_argument(
        "--package-source", required=True, help="package directory, relative to the root"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "manifest":
            if arguments.phase == "feature-sets":
                write_python_feature_sets(arguments.source.resolve(), arguments.output.resolve())
            else:
                write_python_manifest(
                    arguments.source.resolve(),
                    arguments.feature_set.resolve(),
                    arguments.output.resolve(),
                    package=arguments.package,
                    package_source=arguments.package_source,
                )
        else:
            config = load_config(arguments.config)
            output = arguments.output.resolve()
            if arguments.command == "build":
                build_current(config, output=output, version=arguments.label)
            else:
                build_versions(config, output=output)
    except RuntimeError as error:
        parser.exit(1, f"cpdocs: error: {error}\n")
    return 0


__all__ = ["main"]
