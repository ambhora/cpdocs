# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""The ``cpdocs`` command."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .build import build_current, build_versions, cmake_module
from .config import DEFAULT_CONFIG, load_config
from .python_manifest import write_manifest


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
    build.add_argument("--variants", choices=("all", "primary"), default="all")

    versions = documentation("versions", "document the configured branches and tags")
    versions.add_argument("--tags", help="override versions.tags.select")

    manifest = commands.add_parser("manifest", help="answer a cpdocs request as a build system")
    kinds = manifest.add_subparsers(dest="kind", required=True)
    python = kinds.add_parser("python", help="plain pyproject.toml project")
    python.add_argument("--request", type=_path, required=True)
    python.add_argument("--package", required=True)
    python.add_argument("--source", required=True, help="package directory, relative to the root")

    commands.add_parser("cmake-module", help="print the path of the CMake adapter")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "cmake-module":
            print(cmake_module())
        elif arguments.command == "manifest":
            write_manifest(
                arguments.request, package=arguments.package, package_source=arguments.source
            )
        else:
            config = load_config(arguments.config)
            output = arguments.output.resolve()
            if arguments.command == "build":
                build_current(
                    config, output=output, version=arguments.label, variants=arguments.variants
                )
            else:
                build_versions(config, output=output, tags=arguments.tags)
    except RuntimeError as error:
        parser.exit(1, f"cpdocs: error: {error}\n")
    return 0


__all__ = ["main"]
