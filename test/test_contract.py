# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cpdocs.contract import (
    ContractError,
    read_feature_set,
    read_feature_sets,
    read_manifest,
    write_feature_set,
)


def _feature_sets(**overrides: object) -> dict[str, object]:
    manifest: dict[str, object] = {
        "cpdocs-feature-sets": 1,
        "project": {"name": "demo", "version": "1.0"},
        "feature-sets": [
            {"features": []},
            {"features": ["gpu"], "build-option": "CUDA"},
        ],
    }
    manifest.update(overrides)
    return manifest


def _manifest(**overrides: object) -> dict[str, object]:
    manifest: dict[str, object] = {
        "cpdocs-manifest": 1,
        "units": [
            {
                "id": "core",
                "language": "cpp",
                "api": [{"path": "include"}, {"path": "/abs/generated", "generated": True}],
                "parse": {
                    "language": "cpp",
                    "compile-database": "build/compile_commands.json",
                    "standard": "c++20",
                    "define": ["A=1"],
                },
            }
        ],
    }
    manifest.update(overrides)
    return manifest


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_feature_sets_are_unnamed_but_keep_build_system_fields(tmp_path: Path) -> None:
    feature_sets = read_feature_sets(_write(tmp_path / "m.json", _feature_sets()))
    assert feature_sets.project == "demo"
    assert [feature_set.features for feature_set in feature_sets.feature_sets] == [(), ("gpu",)]
    assert [feature_set.key for feature_set in feature_sets.feature_sets] == [
        "feature-set-001",
        "feature-set-002",
    ]
    assert feature_sets.feature_sets[1].selection == {
        "features": ["gpu"],
        "build-option": "CUDA",
    }


def test_selected_feature_set_round_trip_preserves_build_system_fields(tmp_path: Path) -> None:
    feature_sets = read_feature_sets(_write(tmp_path / "all.json", _feature_sets()))
    path = tmp_path / "feature-set.json"
    write_feature_set(path, feature_sets.feature_sets[1])
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw == {
        "cpdocs-feature-set": 1,
        "features": ["gpu"],
        "build-option": "CUDA",
    }
    selected = read_feature_set(path)
    assert selected.features == ("gpu",)
    assert selected.selection == {
        "features": ["gpu"],
        "build-option": "CUDA",
    }


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"cpdocs-feature-sets": 2}, "unsupported cpdocs-feature-sets"),
        ({"feature-sets": []}, "feature-sets must be a non-empty list"),
        (
            {"feature-sets": [{"features": ["gpu", "mpi"]}, {"features": ["mpi", "gpu"]}]},
            "duplicate feature sets",
        ),
        ({"feature-sets": [{"features": ["gpu", "gpu"]}]}, "must not contain duplicates"),
    ],
)
def test_invalid_feature_sets(tmp_path: Path, overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ContractError, match=message):
        read_feature_sets(_write(tmp_path / "m.json", _feature_sets(**overrides)))


def test_manifest_separates_semantic_and_parser_language(tmp_path: Path) -> None:
    value = _manifest()
    value["units"] = [
        {
            "id": "device",
            "language": "cuda",
            "api": [{"path": "include"}],
            "parse": {"language": "cpp", "standard": "c++20"},
        }
    ]
    manifest = read_manifest(_write(tmp_path / "m.json", value), source=tmp_path)
    unit = manifest.units[0]
    assert unit.language == "cuda"
    assert unit.parse is not None and unit.parse.language == "cpp"


def test_manifest_only_describes_outputs(tmp_path: Path) -> None:
    manifest = read_manifest(_write(tmp_path / "m.json", _manifest()), source=tmp_path)
    unit = manifest.units[0]
    assert unit.api[0].path == tmp_path / "include"
    assert unit.api[1].generated is True
    assert unit.parse is not None and unit.parse.define == ("A=1",)
    assert unit.parse.compile_database == tmp_path / "build" / "compile_commands.json"


def test_manifest_does_not_have_to_echo_the_feature_set(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["feature-set"] = "ignored-old-field"
    manifest["features"] = {"anything": ["ignored"]}
    assert read_manifest(_write(tmp_path / "m.json", manifest), source=tmp_path).units


def test_python_unit_needs_exactly_one_root(tmp_path: Path) -> None:
    value = {
        "cpdocs-manifest": 1,
        "units": [{"id": "p", "language": "python", "package": "p", "api": []}],
    }
    with pytest.raises(ContractError, match="exactly one API root"):
        read_manifest(_write(tmp_path / "m.json", value), source=tmp_path)


def test_fortran_modules_are_api_sources_and_layout_roots_are_preserved(tmp_path: Path) -> None:
    value = {
        "cpdocs-manifest": 1,
        "units": [
            {
                "id": "geometry",
                "language": "fortran",
                "generated": False,
                "api": [],
                "headers": [],
                "sources": ["lib"],
                "modules": ["mod"],
                "executables": [],
            }
        ],
    }
    unit = read_manifest(_write(tmp_path / "m.json", value), source=tmp_path).units[0]
    assert unit.language == "fortran"
    assert unit.modules == (tmp_path / "mod",)
    assert unit.sources == (tmp_path / "lib",)


def test_browse_only_unit_may_have_no_language(tmp_path: Path) -> None:
    value = {
        "cpdocs-manifest": 1,
        "units": [
            {
                "id": "tools",
                "language": None,
                "api": [],
                "sources": ["bin"],
                "executables": ["bin/tool.cpp"],
            }
        ],
    }
    unit = read_manifest(_write(tmp_path / "m.json", value), source=tmp_path).units[0]
    assert unit.language is None
    assert unit.sources == (tmp_path / "bin",)
