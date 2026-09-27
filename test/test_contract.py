# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cpdocs.contract import (
    ContractError,
    Request,
    check_variant,
    read_description,
    read_request,
    read_variant_manifest,
)


def _describe(**overrides: object) -> dict[str, object]:
    manifest: dict[str, object] = {
        "cpdocs-manifest": 1,
        "kind": "describe",
        "project": {"name": "demo", "version": "1.0"},
        "features": {"PROJECT_FEATURES": {"values": ["mpi", "cuda"]}},
        "units": [{"id": "core", "language": "cpp"}],
        "variants": [
            {
                "name": "serial",
                "primary": True,
                "features": {"PROJECT_FEATURES": []},
                "commands": [["true"]],
            },
            {
                "name": "full",
                "features": {"PROJECT_FEATURES": ["mpi", "cuda"]},
                "commands": [["true"]],
            },
        ],
    }
    manifest.update(overrides)
    return manifest


def _variant(**overrides: object) -> dict[str, object]:
    manifest: dict[str, object] = {
        "cpdocs-manifest": 1,
        "kind": "variant",
        "variant": "full",
        "features": {"PROJECT_FEATURES": ["cuda", "mpi"]},
        "units": [
            {
                "id": "core",
                "language": "cpp",
                "api": [{"path": "include"}, {"path": "/abs/generated", "generated": True}],
                "parse": {"standard": "c++20", "define": ["A=1"]},
            }
        ],
    }
    manifest.update(overrides)
    return manifest


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_request_round_trip(tmp_path: Path) -> None:
    request = Request(
        phase="variant",
        ref="v1.0",
        ref_kind="tag",
        source=tmp_path,
        build=tmp_path / "build",
        manifest=tmp_path / "manifest.json",
        variant="full",
    )
    request.write(tmp_path / "request.json")
    assert read_request(tmp_path / "request.json") == request


def test_describe_manifest_is_read(tmp_path: Path) -> None:
    description = read_description(_write(tmp_path / "m.json", _describe()))
    assert description.project == "demo"
    assert description.primary.name == "serial"
    assert description.variant("full").features == {"PROJECT_FEATURES": ("mpi", "cuda")}
    assert description.features[0].values == ("mpi", "cuda")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"kind": "variant"}, "expected a 'describe' manifest"),
        ({"cpdocs-manifest": 2}, "unsupported cpdocs-manifest"),
        ({"units": []}, "units must be a non-empty list"),
        ({"units": [{"id": "x", "language": "fortran"}]}, "language must be one of"),
        (
            {"variants": [{"name": "a", "commands": []}]},
            "exactly one variant must be primary",
        ),
        (
            {
                "variants": [
                    {"name": "a", "primary": True, "features": {"OTHER": []}, "commands": []}
                ]
            },
            "undeclared feature axis",
        ),
        (
            {
                "variants": [
                    {
                        "name": "a",
                        "primary": True,
                        "features": {"PROJECT_FEATURES": ["hip"]},
                        "commands": [],
                    }
                ]
            },
            "unknown PROJECT_FEATURES values: hip",
        ),
    ],
)
def test_invalid_describe_manifests(
    tmp_path: Path, overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ContractError, match=message):
        read_description(_write(tmp_path / "m.json", _describe(**overrides)))


def test_variant_manifest_resolves_paths_against_source(tmp_path: Path) -> None:
    manifest = read_variant_manifest(_write(tmp_path / "m.json", _variant()), source=tmp_path)
    unit = manifest.units[0]
    assert unit.api[0].path == tmp_path / "include"
    assert unit.api[1].generated is True
    assert unit.parse is not None and unit.parse.define == ("A=1",)
    description = read_description(_write(tmp_path / "d.json", _describe()))
    check_variant(manifest, description=description, requested="full", path=tmp_path / "m.json")


def test_variant_must_echo_the_described_features(tmp_path: Path) -> None:
    description = read_description(_write(tmp_path / "d.json", _describe()))
    manifest = read_variant_manifest(
        _write(tmp_path / "m.json", _variant(features={"PROJECT_FEATURES": ["mpi"]})),
        source=tmp_path,
    )
    with pytest.raises(ContractError, match="configured with features"):
        check_variant(manifest, description=description, requested="full", path=tmp_path / "m.json")


def test_variant_must_answer_the_requested_variant(tmp_path: Path) -> None:
    description = read_description(_write(tmp_path / "d.json", _describe()))
    manifest = read_variant_manifest(_write(tmp_path / "m.json", _variant()), source=tmp_path)
    with pytest.raises(ContractError, match="answered for variant 'full'"):
        check_variant(
            manifest, description=description, requested="serial", path=tmp_path / "m.json"
        )


def test_python_unit_needs_exactly_one_root(tmp_path: Path) -> None:
    value = {
        "cpdocs-manifest": 1,
        "kind": "variant",
        "variant": "default",
        "features": {},
        "units": [{"id": "p", "language": "python", "package": "p", "api": []}],
    }
    with pytest.raises(ContractError, match="exactly one API root"):
        read_variant_manifest(_write(tmp_path / "m.json", value), source=tmp_path)
