# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Build orchestration against a scripted build system."""

from __future__ import annotations

import json
import pathlib

import pytest

import conftest
import cpdocs.build
import cpdocs.cli
import cpdocs.config
import cpdocs.model


@pytest.fixture(autouse=True)
def _no_ci_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("CPDOCS_CURRENT_BRANCH", "GITHUB_HEAD_REF", "CI_COMMIT_BRANCH", "GITHUB_REF_TYPE"):
        monkeypatch.delenv(variable, raising=False)


def test_semantic_file_layout_flattens_manifest_roots(tmp_path: pathlib.Path) -> None:
    include = tmp_path / "src" / "cuda" / "include"
    library = tmp_path / "src" / "cuda" / "lib"
    header = include / "kprof" / "cuda.hpp"
    source = library / "kprof" / "synchronize.cu"
    header.parent.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    header.write_text("#pragma once\n", encoding="utf-8")
    source.write_text("// source\n", encoding="utf-8")

    assert cpdocs.build._semantic_display_path(header, root=include, generated=False) == "include/kprof/cuda.hpp"
    assert cpdocs.build._semantic_display_path(source, root=library, generated=False) == "lib/kprof/synchronize.cu"
    assert (
        cpdocs.build._semantic_display_path(header, root=include, generated=True) == "_generated/include/kprof/cuda.hpp"
    )
    assert (
        cpdocs.build._semantic_display_path(source, root=library, generated=True)
        == "_generated/lib/kprof/synchronize.cu"
    )


def test_build_runs_feature_sets_once_then_build_once_per_feature_set(tmp_path: pathlib.Path) -> None:
    project = conftest.fake_project(tmp_path / "p", feature_sets=[[], ["a", "b"]])
    graph = cpdocs.build.build_current(
        cpdocs.config.load_config(project / "docs" / "cpdocs.yml"), output=project / "build"
    )

    work = project / "build" / "cpdocs" / "work" / "current" / "feature-sets"
    discovered = json.loads((work / "feature-sets.json").read_text(encoding="utf-8"))
    assert discovered["feature-sets"] == [{"features": []}, {"features": ["a", "b"]}]
    for key in ("feature-set-001", "feature-set-002"):
        assert (work / key / "feature-set.json").is_file()
        assert (work / key / "manifest.json").is_file()
        assert (work / key / "log.txt").is_file()

    assert graph.project == "fake"
    assert list(graph.feature_sets) == ["feature-set-001", "feature-set-002"]
    assert graph.feature_sets["feature-set-001"]["features"] == []
    assert graph.feature_sets["feature-set-002"]["features"] == ["a", "b"]
    answer = graph.entities[cpdocs.model.stable_entity_id("python", "function", "pkg.answer")]
    assert set(answer.feature_sets) == {"feature-set-001", "feature-set-002"}


def test_manifest_does_not_need_to_echo_the_selected_feature_set(tmp_path: pathlib.Path) -> None:
    project = conftest.fake_project(tmp_path / "p", feature_sets=[["a"]])
    graph = cpdocs.build.build_current(
        cpdocs.config.load_config(project / "docs" / "cpdocs.yml"), output=project / "build"
    )
    assert list(graph.feature_sets) == ["feature-set-001"]
    assert graph.feature_sets["feature-set-001"]["features"] == ["a"]


def test_failing_build_command_reports_its_output(tmp_path: pathlib.Path) -> None:
    project = conftest.fake_project(tmp_path / "p")
    (project / "docs" / "cpdocs.yml").write_text(
        "contract: 3\nbuild:\n"
        "  feature-sets: >\n    python -c \"import sys; print('boom'); sys.exit(3)\"\n"
        '  build: "true"\n',
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="boom"):
        cpdocs.build.build_current(cpdocs.config.load_config(project / "docs" / "cpdocs.yml"), output=project / "build")


def test_undocumented_check_can_fail_the_build(tmp_path: pathlib.Path) -> None:
    project = conftest.fake_project(tmp_path / "p", config="checks:\n  undocumented: fail\n")
    (project / "src" / "pkg" / "__init__.py").write_text("def silent(): pass\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="pkg.silent"):
        cpdocs.build.build_current(cpdocs.config.load_config(project / "docs" / "cpdocs.yml"), output=project / "build")


def test_versions_are_built_in_exact_configured_order(tmp_path: pathlib.Path) -> None:
    project = conftest.fake_project(tmp_path / "p", config="versions: [main, '1.1', '1.0']\n")
    conftest.init_repository(project)
    conftest.git(project, "tag", "1.0")
    (project / "src" / "pkg" / "later.py").write_text('"""Added after 1.0."""\n', encoding="utf-8")
    conftest.git(project, "add", "-A")
    conftest.git(project, "commit", "-q", "-m", "later")
    conftest.git(project, "tag", "1.1")
    (project / "src" / "pkg" / "uncommitted.py").write_text('"""Only in the working tree."""\n', encoding="utf-8")

    built = cpdocs.build.build_versions(
        cpdocs.config.load_config(project / "docs" / "cpdocs.yml"), output=project / "build"
    )
    assert built == ["main", "1.1", "1.0"]

    versions = project / "build" / "cpdocs" / "versions"
    metadata = json.loads((versions / "versions.json").read_text(encoding="utf-8"))
    assert metadata["default"] == "main"
    assert [entry["name"] for entry in metadata["versions"]] == ["main", "1.1", "1.0"]
    assert "aliases" not in metadata

    def graph(ref: str) -> dict:
        path = project / "build" / "cpdocs" / "work" / ref / "render" / "api-graph.json"
        return json.loads(path.read_text(encoding="utf-8"))

    assert "python:module:pkg.uncommitted" in graph("main")["entities"]
    assert "python:module:pkg.later" in graph("1.1")["entities"]
    assert "python:module:pkg.later" not in graph("1.0")["entities"]
    assert conftest.git(project, "worktree", "list").count("\n") == 1


def test_versions_include_working_tree_for_local_preview(tmp_path: pathlib.Path) -> None:
    project = conftest.fake_project(tmp_path / "p", config="versions: [main]\n")
    conftest.init_repository(project)
    conftest.git(project, "checkout", "-q", "-b", "topic")
    (project / "src" / "pkg" / "local.py").write_text('"""Only in the local working tree."""\n', encoding="utf-8")

    built = cpdocs.build.build_versions(
        cpdocs.config.load_config(project / "docs" / "cpdocs.yml"), output=project / "build", include_working_tree=True
    )
    assert built == ["topic", "main"]
    metadata = json.loads((project / "build" / "cpdocs" / "versions" / "versions.json").read_text(encoding="utf-8"))
    assert metadata["default"] == "topic"
    assert [entry["kind"] for entry in metadata["versions"]] == ["worktree", "branch"]


def test_unknown_configured_version_fails(tmp_path: pathlib.Path) -> None:
    project = conftest.fake_project(tmp_path / "p", config="versions: [main, missing]\n")
    conftest.init_repository(project)
    with pytest.raises(RuntimeError, match="missing"):
        cpdocs.build.build_versions(
            cpdocs.config.load_config(project / "docs" / "cpdocs.yml"), output=project / "build"
        )


def test_cli_build_and_output(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = conftest.fake_project(tmp_path / "p")
    monkeypatch.chdir(project)
    assert cpdocs.cli.main(["build", "--output", "out"]) == 0
    assert (project / "out" / "cpdocs" / "current" / "index.html").is_file()


def test_obsolete_cpdocs_cmake_placeholder_is_rejected(tmp_path: pathlib.Path) -> None:
    project = conftest.fake_project(tmp_path / "p")
    config = project / "docs" / "cpdocs.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace('"{{output-file}}"', '"{{output-file}}" "{{cpdocs-cmake}}"', 1),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="cpdocs-cmake"):
        cpdocs.build.build_current(cpdocs.config.load_config(config), output=project / "build")


def test_tmp_directory_separates_work_from_output(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    config_file = project / "cpdocs.yml"
    config_file.write_text(
        "contract: 3\nproject: demo\nlanguages: [python]\n"
        "build:\n"
        "  feature-sets: >\n"
        "    python -c \"import pathlib; pathlib.Path(r'{{output-file}}').write_text('[]')\"\n"
        "  build: >\n"
        "    python -c \"import pathlib; pathlib.Path(r'{{output-file}}').write_text('[]')\"\n",
        encoding="utf-8",
    )
    # Layout behavior is the contract under test; avoid coupling this regression to providers.
    import cpdocs.build

    layout = cpdocs.build.Layout.for_output(project / "build", tmp_directory=tmp_path / "scratch")
    assert layout.root == (project / "build" / "cpdocs").resolve()
    assert layout.work("main") == (tmp_path / "scratch" / "cpdocs" / "work" / "main").resolve()
