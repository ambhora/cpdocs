# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Execute and consume the generic cpdocs JSON build-system contract."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ..contract import (
    FeatureSetDeclaration,
    FeatureSets,
    Manifest,
    read_feature_sets,
    read_manifest,
    write_feature_set,
)

_PLACEHOLDER = re.compile(r"\{\{([a-z][a-z0-9-]*)\}\}")


def _expand(command: str, values: dict[str, str], *, allowed: set[str], name: str) -> str:
    placeholders = set(_PLACEHOLDER.findall(command))
    unknown = sorted(placeholders - allowed)
    if unknown:
        raise RuntimeError(
            f"cpdocs.yml: build.{name} uses unknown placeholders: {', '.join(unknown)}"
        )
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], command)


def _run_command(
    command: str,
    *,
    source: Path,
    values: dict[str, str],
    allowed: set[str],
    name: str,
    log: Path,
) -> None:
    expanded = _expand(command, values, allowed=allowed, name=name)
    environment = dict(os.environ)
    package_root = str(Path(__file__).resolve().parents[2])
    pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = package_root + (os.pathsep + pythonpath if pythonpath else "")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        stream.write("$ " + expanded + "\n")
        stream.flush()
        result = subprocess.run(
            expanded,
            cwd=source,
            shell=True,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=environment,
        )
        stream.write(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(
            f"build-system command failed (build.{name}):\n  {expanded}\n\n"
            + result.stdout.rstrip()
        )


def discover_feature_sets(command: str, *, source: Path, work: Path) -> FeatureSets:
    """Run ``build.feature-sets`` and read ``feature-sets.json``."""

    directory = work / "feature-sets"
    shutil.rmtree(directory, ignore_errors=True)
    tmpdir = directory / "tmp"
    tmpdir.mkdir(parents=True)
    output = directory / "feature-sets.json"
    _run_command(
        command,
        source=source.resolve(),
        values={
            "source": str(source.resolve()),
            "tmpdir": str(tmpdir.resolve()),
            "output-file": str(output.resolve()),
            "python": sys.executable,
        },
        allowed={"source", "tmpdir", "output-file", "python"},
        name="feature-sets",
        log=directory / "log.txt",
    )
    return read_feature_sets(output)


def resolve_manifest(
    command: str, feature_set: FeatureSetDeclaration, *, source: Path, work: Path
) -> Manifest:
    """Run ``build.build`` for one feature set and read ``manifest.json``."""

    directory = work / "feature-sets" / feature_set.key
    shutil.rmtree(directory, ignore_errors=True)
    tmpdir = directory / "tmp"
    tmpdir.mkdir(parents=True)
    feature_set_file = directory / "feature-set.json"
    output = directory / "manifest.json"
    write_feature_set(feature_set_file, feature_set)
    _run_command(
        command,
        source=source.resolve(),
        values={
            "source": str(source.resolve()),
            "tmpdir": str(tmpdir.resolve()),
            "feature-set": str(feature_set_file.resolve()),
            "output-file": str(output.resolve()),
            "python": sys.executable,
        },
        allowed={"source", "tmpdir", "feature-set", "output-file", "python"},
        name="build",
        log=directory / "log.txt",
    )
    return read_manifest(output, source=source.resolve())


__all__ = ["discover_feature_sets", "resolve_manifest"]
