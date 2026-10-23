# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Execute and consume the generic cpdocs JSON build-system contract."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from ..contract import FeatureSetDeclaration, FeatureSets, Manifest, read_feature_sets, read_manifest, write_feature_set
from ..filesystem import remove_tree

_PLACEHOLDER = re.compile(r"\{\{\s*([a-z][a-z0-9_.-]*)\s*\}\}")


def language_template_values(configuration: dict[str, object]) -> dict[str, str]:
    """Flatten concrete Keyso values into dotted command-template placeholders."""

    result: dict[str, str] = {}

    def visit(path: str, value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", key):
                    raise RuntimeError(f"cpdocs.yml: invalid language property {key!r}")
                visit(f"{path}.{key}" if path else key, child)
        elif isinstance(value, (str, int, float, bool)) and not isinstance(value, complex):
            if not path:
                raise RuntimeError("cpdocs.yml: language configuration needs a property name")
            if path in {"source", "tmpdir", "output-file", "feature-set", "python"}:
                raise RuntimeError(f"cpdocs.yml: language property {path!r} is reserved")
            result[path] = str(value).lower() if isinstance(value, bool) else str(value)
        else:
            raise RuntimeError(f"cpdocs.yml: language property {path!r} must be a scalar value")

    visit("", configuration)
    return result


def placeholder_variable(name: str) -> str:
    """The environment variable that carries a placeholder's value to a build command.

    ``{{output-file}}`` becomes ``CPDOCS_ARG_OUTPUT_FILE`` and ``{{cxx.standard}}`` becomes
    ``CPDOCS_ARG_CXX_STANDARD``.
    """

    return "CPDOCS_ARG_" + re.sub(r"[.-]", "_", name).upper()


def _expand(command: str, values: dict[str, str], *, allowed: set[str], name: str) -> tuple[str, dict[str, str]]:
    """Replace placeholders by references to environment variables that hold their values.

    Substituting values into the command text would let the shell parse them: a checkout path or
    a language value containing ``$(...)``, a backtick or a quote would run as a command even
    inside the double quotes the examples use. A variable reference is expanded by the shell
    after parsing, so its value stays data; ``"{{source}}"`` still yields one word.
    """

    placeholders = set(_PLACEHOLDER.findall(command))
    unknown = sorted(placeholders - allowed)
    if unknown:
        raise RuntimeError(f"cpdocs.yml: build.{name} uses unknown placeholders: {', '.join(unknown)}")
    variables: dict[str, str] = {}
    for key in sorted(values):
        variable = placeholder_variable(key)
        if variable in variables:
            raise RuntimeError(
                f"cpdocs.yml: placeholders {variables[variable]!r} and {key!r} both map to the "
                f"environment variable {variable}; rename one of them"
            )
        variables[variable] = key
    expanded = _PLACEHOLDER.sub(lambda match: "${" + placeholder_variable(match.group(1)) + "}", command)
    return expanded, {variable: values[key] for variable, key in variables.items()}


def _run_command(
    command: str, *, source: Path, values: dict[str, str], allowed: set[str], name: str, log: Path
) -> None:
    """Run one build-system command in ``source`` and record its output in ``log``.

    A non-zero exit status raises with the command, its placeholder values and its output.
    """

    expanded, variables = _expand(command, values, allowed=allowed, name=name)
    environment = dict(os.environ)
    environment.update(variables)
    package_root = str(Path(__file__).resolve().parents[2])
    pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = package_root + (os.pathsep + pythonpath if pythonpath else "")
    # The log shows the values the command saw, quoted the way a shell would need them.
    shown = "".join(f"{variable}={shlex.quote(value)}\n" for variable, value in sorted(variables.items()))
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        stream.write(shown + "$ " + expanded + "\n")
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
            f"build-system command failed (build.{name}):\n  {expanded}\n"
            + "".join(f"  {line}\n" for line in shown.splitlines())
            + "\n"
            + result.stdout.rstrip()
        )


def discover_feature_sets(
    command: str, *, source: Path, work: Path, template_values: dict[str, str] | None = None
) -> FeatureSets:
    """Run ``build.feature-sets`` and read ``feature-sets.json``."""

    directory = work / "feature-sets"
    remove_tree(directory, owner=work)
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
            **(template_values or {}),
        },
        allowed={"source", "tmpdir", "output-file", "python"} | set(template_values or {}),
        name="feature-sets",
        log=directory / "log.txt",
    )
    return read_feature_sets(output)


def resolve_manifest(
    command: str,
    feature_set: FeatureSetDeclaration,
    *,
    source: Path,
    work: Path,
    template_values: dict[str, str] | None = None,
) -> Manifest:
    """Run ``build.build`` for one feature set and read ``manifest.json``."""

    directory = work / "feature-sets" / feature_set.key
    remove_tree(directory, owner=work)
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
            **(template_values or {}),
        },
        allowed={"source", "tmpdir", "feature-set", "output-file", "python"} | set(template_values or {}),
        name="build",
        log=directory / "log.txt",
    )
    return read_manifest(output, source=source.resolve())


__all__ = ["discover_feature_sets", "resolve_manifest"]
