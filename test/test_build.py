# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Build orchestration against a scripted build system."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import fake_project, git, init_repository
from cpdocs.build import build_current, build_versions
from cpdocs.cli import main
from cpdocs.config import load_config
from cpdocs.model import stable_entity_id


@pytest.fixture(autouse=True)
def _no_ci_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (
        "CPDOCS_CURRENT_BRANCH",
        "GITHUB_HEAD_REF",
        "CI_COMMIT_BRANCH",
        "GITHUB_REF_TYPE",
    ):
        monkeypatch.delenv(variable, raising=False)


def test_build_runs_feature_sets_once_then_build_once_per_feature_set(tmp_path: Path) -> None:
    project = fake_project(
        tmp_path / "p",
        feature_sets=[[], ["a", "b"]],
    )
    graph = build_current(load_config(project / "docs" / "cpdocs.yml"), output=project / "build")

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
    answer = graph.entities[stable_entity_id("python", "function", "pkg.answer")]
    assert set(answer.feature_sets) == {"feature-set-001", "feature-set-002"}


def test_manifest_does_not_need_to_echo_the_selected_feature_set(tmp_path: Path) -> None:
    project = fake_project(tmp_path / "p", feature_sets=[["a"]])
    graph = build_current(load_config(project / "docs" / "cpdocs.yml"), output=project / "build")
    assert list(graph.feature_sets) == ["feature-set-001"]
    assert graph.feature_sets["feature-set-001"]["features"] == ["a"]


def test_failing_build_command_reports_its_output(tmp_path: Path) -> None:
    project = fake_project(tmp_path / "p")
    (project / "docs" / "cpdocs.yml").write_text(
        "contract: 3\nbuild:\n"
        "  feature-sets: >-\n    python -c \"import sys; print('boom'); sys.exit(3)\"\n"
        "  build: \"true\"\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="boom"):
        build_current(load_config(project / "docs" / "cpdocs.yml"), output=project / "build")


def test_undocumented_check_can_fail_the_build(tmp_path: Path) -> None:
    project = fake_project(tmp_path / "p", config="checks:\n  undocumented: fail\n")
    (project / "src" / "pkg" / "__init__.py").write_text("def silent(): pass\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="pkg.silent"):
        build_current(load_config(project / "docs" / "cpdocs.yml"), output=project / "build")


def test_versions_are_built_in_exact_configured_order(tmp_path: Path) -> None:
    project = fake_project(tmp_path / "p", config="versions: [main, '1.1', '1.0']\n")
    init_repository(project)
    git(project, "tag", "1.0")
    (project / "src" / "pkg" / "later.py").write_text('"""Added after 1.0."""\n', encoding="utf-8")
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "later")
    git(project, "tag", "1.1")
    (project / "src" / "pkg" / "uncommitted.py").write_text(
        '"""Only in the working tree."""\n', encoding="utf-8"
    )

    built = build_versions(load_config(project / "docs" / "cpdocs.yml"), output=project / "build")
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
    assert git(project, "worktree", "list").count("\n") == 1


def test_versions_include_working_tree_for_local_preview(tmp_path: Path) -> None:
    project = fake_project(tmp_path / "p", config="versions: [main]\n")
    init_repository(project)
    git(project, "checkout", "-q", "-b", "topic")
    (project / "src" / "pkg" / "local.py").write_text(
        '"""Only in the local working tree."""\n', encoding="utf-8"
    )

    built = build_versions(
        load_config(project / "docs" / "cpdocs.yml"),
        output=project / "build",
        include_working_tree=True,
    )
    assert built == ["topic", "main"]
    metadata = json.loads(
        (project / "build" / "cpdocs" / "versions" / "versions.json").read_text(encoding="utf-8")
    )
    assert metadata["default"] == "topic"
    assert [entry["kind"] for entry in metadata["versions"]] == ["worktree", "branch"]


def test_unknown_configured_version_fails(tmp_path: Path) -> None:
    project = fake_project(tmp_path / "p", config="versions: [main, missing]\n")
    init_repository(project)
    with pytest.raises(RuntimeError, match="missing"):
        build_versions(load_config(project / "docs" / "cpdocs.yml"), output=project / "build")


def test_cli_build_and_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = fake_project(tmp_path / "p")
    monkeypatch.chdir(project)
    assert main(["build", "--output", "out"]) == 0
    assert (project / "out" / "cpdocs" / "current" / "index.html").is_file()


def test_obsolete_cpdocs_cmake_placeholder_is_rejected(tmp_path: Path) -> None:
    project = fake_project(tmp_path / "p")
    config = project / "docs" / "cpdocs.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            '"{{output-file}}"', '"{{output-file}}" "{{cpdocs-cmake}}"', 1
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="cpdocs-cmake"):
        build_current(load_config(config), output=project / "build")


def test_tmp_directory_separates_work_from_output(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    config_file = project / "cpdocs.yml"
    config_file.write_text(
        "contract: 3\nproject: demo\nlanguages: [python]\n"
        "build:\n"
        "  feature-sets: >-\n"
        "    python -c \"import pathlib; pathlib.Path(r'{{output-file}}').write_text('[]')\"\n"
        "  build: >-\n"
        "    python -c \"import pathlib; pathlib.Path(r'{{output-file}}').write_text('[]')\"\n",
        encoding="utf-8",
    )
    # Layout behavior is the contract under test; avoid coupling this regression to providers.
    from cpdocs.build import Layout

    layout = Layout.for_output(project / "build", tmp_directory=tmp_path / "scratch")
    assert layout.root == (project / "build" / "cpdocs").resolve()
    assert layout.work("main") == (tmp_path / "scratch" / "cpdocs" / "work" / "main").resolve()
