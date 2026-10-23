# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""The checked-in Rust example, built through Cargo and rustdoc JSON."""

from __future__ import annotations

import pathlib
import subprocess

import pytest

import conftest
import cpdocs.build
import cpdocs.config
import cpdocs.model


def _rust_toolchain() -> None:
    conftest.require("cargo", "rustup")
    installed = subprocess.run(
        ["rustup", "toolchain", "list"], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout
    if "nightly-2026-10-01" not in installed:
        pytest.skip("nightly-2026-10-01 Rust toolchain is required")


def test_rust_example_uses_disjoint_cargo_features_and_rustdoc_json(tmp_path: pathlib.Path) -> None:
    _rust_toolchain()
    project = conftest.copy_example(tmp_path, "rust-basic")
    graph = cpdocs.build.build_current(
        cpdocs.config.load_config(project / "docs" / "cpdocs.yml"), output=project / "build"
    )

    assert graph.language == "rust"
    assert [value["features"] for value in graph.feature_sets.values()] == [["batch"], ["checked"]]

    vector = graph.entities[cpdocs.model.stable_entity_id("rust", "struct", "rust_geometry::geometry::Vector3")]
    assert vector.documentation == "A three-dimensional vector."
    dot = graph.entities[cpdocs.model.stable_entity_id("rust", "function", "rust_geometry::geometry::dot")]
    assert dot.documentation == "Return the dot product of two vectors."

    dot_many = graph.entities[cpdocs.model.stable_entity_id("rust", "function", "rust_geometry::geometry::dot_many")]
    assert {tuple(graph.feature_sets[key]["features"]) for key in dot_many.feature_sets} == {("batch",)}
    checked_dot = graph.entities[
        cpdocs.model.stable_entity_id("rust", "function", "rust_geometry::geometry::checked_dot")
    ]
    assert {tuple(graph.feature_sets[key]["features"]) for key in checked_dot.feature_sets} == {("checked",)}

    assert "src/internal.rs" in graph.files
    assert not any(entity.name == "norm_squared" for entity in graph.entities.values())
    source_page = project / "build" / "cpdocs" / "current" / "_sources" / "src" / "internal.rs" / "index.html"
    assert source_page.is_file()
    assert "norm_squared" in source_page.read_text(encoding="utf-8")
