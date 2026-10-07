# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Built-in Cargo/rustdoc provider for the cpdocs build-system contract."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from ..contract import CONTRACT_VERSION, read_feature_set


def _cargo_command(toolchain: str | None) -> list[str]:
    cargo = os.environ.get("CPDOCS_CARGO", "cargo")
    command = [cargo]
    if toolchain:
        command.append(f"+{toolchain}")
    return command


def _run_cargo(
    source: Path, arguments: list[str], *, toolchain: str | None
) -> subprocess.CompletedProcess[str]:
    command = [*_cargo_command(toolchain), *arguments]
    try:
        return subprocess.run(
            command,
            cwd=source,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            "cpdocs rust: cargo is not available; install Rust/Cargo or set CPDOCS_CARGO"
        ) from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"cpdocs rust: cargo command failed{suffix}") from error


def _metadata(source: Path, *, toolchain: str | None) -> dict[str, Any]:
    manifest = source / "Cargo.toml"
    if not manifest.is_file():
        raise RuntimeError(f"cpdocs rust: {manifest} does not exist")
    result = _run_cargo(
        source,
        [
            "metadata",
            "--format-version=1",
            "--no-deps",
            "--manifest-path",
            str(manifest),
        ],
        toolchain=toolchain,
    )
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"cpdocs rust: cargo metadata returned invalid JSON: {error}") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("packages"), list):
        raise RuntimeError("cpdocs rust: cargo metadata did not return a packages list")
    return raw


def _package(metadata: dict[str, Any], source: Path, package: str | None) -> dict[str, Any]:
    packages = [item for item in metadata["packages"] if isinstance(item, dict)]
    if package:
        matches = [item for item in packages if item.get("name") == package]
        if len(matches) != 1:
            raise RuntimeError(f"cpdocs rust: Cargo package {package!r} is not unique in the workspace")
        return matches[0]

    root_manifest = (source / "Cargo.toml").resolve()
    matches = []
    for item in packages:
        manifest_path = item.get("manifest_path")
        if isinstance(manifest_path, str):
            try:
                if Path(manifest_path).resolve() == root_manifest:
                    matches.append(item)
            except OSError:
                pass
    if len(matches) == 1:
        return matches[0]
    if len(packages) == 1:
        return packages[0]
    raise RuntimeError(
        "cpdocs rust: Cargo workspace contains multiple packages; pass --package explicitly"
    )


def _library_target(package: dict[str, Any]) -> dict[str, Any]:
    targets = package.get("targets")
    if not isinstance(targets, list):
        raise RuntimeError("cpdocs rust: cargo metadata package has no targets list")
    libraries: list[dict[str, Any]] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        kinds = target.get("kind")
        if isinstance(kinds, list) and any(kind in {"lib", "proc-macro"} for kind in kinds):
            libraries.append(target)
    if len(libraries) != 1:
        raise RuntimeError(
            "cpdocs rust: package must expose exactly one library target for rustdoc JSON"
        )
    return libraries[0]


def _feature_sets(package: dict[str, Any]) -> list[list[str]]:
    declared = package.get("features")
    declared_features = set(declared) if isinstance(declared, dict) else set()
    metadata = package.get("metadata")
    cpdocs = metadata.get("cpdocs") if isinstance(metadata, dict) else None
    configured = cpdocs.get("feature-sets") if isinstance(cpdocs, dict) else None

    if configured is None:
        # Cargo itself tells us which features exist, but not which combinations a project wants to
        # document.  The useful generic default is therefore deliberately conservative: treat every
        # declared feature as an independent configuration and exercise it exactly once.  Projects
        # with coupled/meaningful combinations can override this through package.metadata.cpdocs.
        if declared_features:
            return [[feature] for feature in sorted(declared_features)]
        return [[]]
    if not isinstance(configured, list) or not configured:
        raise RuntimeError(
            "cpdocs rust: package.metadata.cpdocs.feature-sets must be a non-empty array"
        )

    result: list[list[str]] = []
    identities: set[tuple[str, ...]] = set()
    for index, value in enumerate(configured):
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise RuntimeError(
                "cpdocs rust: package.metadata.cpdocs.feature-sets entries must be arrays of strings"
            )
        if len(set(value)) != len(value):
            raise RuntimeError(
                f"cpdocs rust: feature set {index + 1} contains duplicate Cargo features"
            )
        unknown = [feature for feature in value if feature not in declared_features]
        if unknown:
            raise RuntimeError(
                "cpdocs rust: feature set references undeclared Cargo feature(s): "
                + ", ".join(unknown)
            )
        identity = tuple(sorted(value))
        if identity in identities:
            raise RuntimeError("cpdocs rust: feature-sets must not contain duplicates")
        identities.add(identity)
        result.append(list(value))
    return result


def _relative_or_absolute(path: Path, source: Path) -> str:
    try:
        return path.resolve().relative_to(source.resolve()).as_posix()
    except (OSError, ValueError):
        return str(path.resolve())


def _browse_roots(source: Path, package: dict[str, Any], target: dict[str, Any]) -> list[str]:
    roots: list[Path] = []
    manifest_path = Path(str(package["manifest_path"]))
    package_root = manifest_path.parent
    for candidate in (
        source / "Cargo.toml",
        source / "Cargo.lock",
        source / "rust-toolchain.toml",
        source / "rust-toolchain",
        package_root / "Cargo.toml",
        package_root / "build.rs",
        package_root / "src",
    ):
        if candidate.exists() and candidate not in roots:
            roots.append(candidate)

    src_path = target.get("src_path")
    if isinstance(src_path, str):
        src = Path(src_path)
        if src.exists() and src not in roots and not any(
            root.is_dir() and root in src.parents for root in roots
        ):
            roots.append(src)
    return [_relative_or_absolute(root, source) for root in roots]


def write_feature_sets(
    source: Path,
    output: Path,
    *,
    package: str | None = None,
    toolchain: str | None = None,
) -> Path:
    metadata = _metadata(source, toolchain=toolchain)
    selected = _package(metadata, source, package)
    manifest = {
        "cpdocs-feature-sets": CONTRACT_VERSION,
        "generator": "cpdocs rust",
        "project": {
            "name": str(selected.get("name") or ""),
            "version": str(selected.get("version") or ""),
        },
        "feature-sets": [{"features": features} for features in _feature_sets(selected)],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output


def write_manifest(
    source: Path,
    feature_set_file: Path,
    output: Path,
    *,
    package: str | None = None,
    toolchain: str | None = None,
) -> Path:
    feature_set = read_feature_set(feature_set_file)
    metadata = _metadata(source, toolchain=toolchain)
    selected = _package(metadata, source, package)
    target = _library_target(selected)
    declared = selected.get("features")
    declared_features = set(declared) if isinstance(declared, dict) else set()
    unknown = [feature for feature in feature_set.features if feature not in declared_features]
    if unknown:
        raise RuntimeError(
            "cpdocs rust: selected feature set contains undeclared Cargo feature(s): "
            + ", ".join(unknown)
        )

    target_dir = output.parent / "cargo-target"
    arguments = [
        "rustdoc",
        "--manifest-path",
        str(source / "Cargo.toml"),
        "--package",
        str(selected["name"]),
        "--lib",
        "--target-dir",
        str(target_dir),
        "-Z",
        "unstable-options",
        "--output-format",
        "json",
        "--no-default-features",
    ]
    if feature_set.features:
        arguments.extend(["--features", ",".join(feature_set.features)])
    _run_cargo(source, arguments, toolchain=toolchain)

    target_name = str(target.get("name") or "").replace("-", "_")
    rustdoc_json = target_dir / "doc" / f"{target_name}.json"
    if not rustdoc_json.is_file():
        raise RuntimeError(
            "cpdocs rust: cargo rustdoc succeeded but did not produce " f"{rustdoc_json}"
        )

    manifest = {
        "cpdocs-manifest": CONTRACT_VERSION,
        "units": [
            {
                "id": target_name,
                "language": "rust",
                "rustdoc-json": str(rustdoc_json.resolve()),
                "sources": _browse_roots(source, selected, target),
            }
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output


__all__ = ["write_feature_sets", "write_manifest"]
