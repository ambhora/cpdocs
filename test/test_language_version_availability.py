# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Language-standard availability is inferred from extracted per-build API graphs."""

from __future__ import annotations

import dataclasses
import shlex
import shutil
import sys
from pathlib import Path

import pytest

from conftest import fake_project, fixture_text
from cpdocs.build import build_current
from cpdocs.config import load_config
from cpdocs.languages.python.extract import build_python_graph
from cpdocs.model import stable_entity_id
from cpdocs.rendering.common import _feature_set_anchor, entity_document


def _page(site: Path, entity) -> str:
    path = entity_document(entity)
    file = site / path.parent / "index.html" if path.name == "index.md" else site / path.with_suffix("") / "index.html"
    return file.read_text(encoding="utf-8")


def test_python_version_guard_static_extraction_and_nested_classes(tmp_path: Path) -> None:
    package = tmp_path / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        fixture_text("python-version-guards.py"), encoding="utf-8"
    )
    older = build_python_graph(
        project_root=tmp_path, package_root=package, package="pkg", python_version=(3, 11)
    )
    newer = build_python_graph(
        project_root=tmp_path, package_root=package, package="pkg", python_version=(3, 12)
    )
    name = lambda kind, value: stable_entity_id("python", kind, "pkg." + value)
    assert name("function", "old_api") in older.entities
    assert name("function", "old_api") not in newer.entities
    assert name("function", "new_api") in newer.entities
    assert name("function", "new_api") not in older.entities
    assert name("constant", "LEGACY") in older.entities
    assert name("constant", "LEGACY") not in newer.entities
    assert name("function", "undecidable") not in newer.entities
    assert older.entities[name("method", "Service.run")].signatures[0].parameters[0].type == "int"
    assert newer.entities[name("method", "Service.run")].signatures[0].parameters[0].type == "str"


def test_python_build_matrix_displays_availability_per_signature(tmp_path: Path) -> None:
    project = fake_project(tmp_path / "project", feature_sets=[[], ["mpi"]])
    (project / "src/pkg/__init__.py").write_text(
        '''import sys

if sys.version_info >= (3, 12):
    def shared(value: str): ...
    def modern(): ...
else:
    def shared(value: int): ...
''', encoding="utf-8"
    )
    config = dataclasses.replace(
        load_config(project / "docs/cpdocs.yml"),
        language_configurations=(
            {"python": {"version": "3.11"}},
            {"python": {"version": "3.12"}},
        ),
    )
    graph = build_current(config, output=project / "build")
    shared = graph.entities[stable_entity_id("python", "function", "pkg.shared")]
    signatures = {s.parameters[0].type: set(sets) for s, sets in
                  zip(shared.signatures, shared.signature_feature_sets, strict=True)}
    assert {"int", "str"} == set(signatures)
    assert {"language-001--feature-set-001", "language-001--feature-set-002"} == signatures["int"]
    assert {"language-002--feature-set-001", "language-002--feature-set-002"} == signatures["str"]
    site = project / "build/cpdocs/current"
    page = _page(site, shared)
    assert page.count("Language versions / standards") == 2
    assert "Python 3.11" in page and "Python 3.12" in page
    assert "Available in feature sets" in page
    # No guessed open-ended version interval, and precise combination links are retained.
    assert "Python 3.12+" not in page
    assert _feature_set_anchor("language-002--feature-set-002") in page
    modern = graph.entities[stable_entity_id("python", "function", "pkg.modern")]
    assert "Python 3.11" not in _page(site, modern)


CPP_PROVIDER = fixture_text("cpp-version-provider.py")


def test_cpp_standard_and_feature_intersection_for_overloads(tmp_path: Path) -> None:
    if shutil.which("clang++") is None:
        pytest.skip("clang++ required")
    project = tmp_path / "project"
    include = project / "include"
    include.mkdir(parents=True)
    (include / "demo.hpp").write_text(
        '''#pragma once
namespace demo {
void stable(int);
#if __cplusplus >= 202002L
void stable(double);
void modern();
#if defined(MPI_ENABLED)
void mpi_only();
#endif
#endif
}
''', encoding="utf-8"
    )
    (project / "provider.py").write_text(CPP_PROVIDER, encoding="utf-8")
    (project / "docs").mkdir()
    python = shlex.quote(sys.executable)
    (project / "docs/cpdocs.yml").write_text(
        "contract: 3\nbuild:\n"
        f'  feature-sets: {python} provider.py discover "{{{{cxx.standard}}}}" "{{{{output-file}}}}"\n'
        f'  build: {python} provider.py build "{{{{cxx.standard}}}}" "{{{{output-file}}}}" "{{{{feature-set}}}}"\n',
        encoding="utf-8",
    )
    config = dataclasses.replace(
        load_config(project / "docs/cpdocs.yml"),
        language_configurations=({"cxx": {"standard": 17}}, {"cxx": {"standard": 20}}),
    )
    graph = build_current(config, output=project / "site")
    stable = graph.entities[stable_entity_id("cpp", "function", "demo::stable")]
    signatures = {s.compact: set(ids) for s, ids in
                  zip(stable.signatures, stable.signature_feature_sets, strict=True)}
    assert len(signatures["(int)"]) == 4
    assert signatures["(double)"] == {
        "language-002--feature-set-001", "language-002--feature-set-002"
    }
    mpi = graph.entities[stable_entity_id("cpp", "function", "demo::mpi_only")]
    assert mpi.feature_sets == ["language-002--feature-set-002"]
    page = _page(project / "site/cpdocs/current", mpi)
    assert "C++20" in page and "C++17" not in page
    assert "mpi" in page
    assert "Language versions / standards" in page
