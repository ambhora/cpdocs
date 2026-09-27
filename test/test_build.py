# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Build orchestration against a scripted build system (no CMake or Clang needed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import fake_project, git, init_repository
from cpdocs.build import build_current, build_versions
from cpdocs.cli import main
from cpdocs.config import load_config
from cpdocs.contract import ContractError
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


def test_build_runs_describe_then_every_variant(tmp_path: Path) -> None:
    project = fake_project(
        tmp_path / "p",
        features={"F": ["a", "b"]},
        variants={"none": {"F": []}, "both": {"F": ["a", "b"]}},
    )
    config = load_config(project / "docs" / "cpdocs.yml")
    graph = build_current(config, output=project / "build")

    work = project / "build" / "cpdocs" / "work" / "current"
    request = json.loads((work / "describe" / "request.json").read_text(encoding="utf-8"))
    assert request["phase"] == "describe" and request["ref-kind"] == "worktree"
    assert (work / "variants" / "both" / "manifest.json").is_file()

    assert graph.project == "fake"
    assert set(graph.variants) == {"none", "both"}
    assert graph.variants["none"]["primary"] is True
    assert graph.variants["both"]["features"] == {"F": ["a", "b"]}
    answer = graph.entities[stable_entity_id("python", "function", "pkg.answer")]
    assert set(answer.variants) == {"none", "both"}
    assert (project / "build" / "cpdocs" / "current" / "api-variants" / "index.html").is_file()


def test_primary_policy_builds_one_variant(tmp_path: Path) -> None:
    project = fake_project(
        tmp_path / "p", features={"F": ["a"]}, variants={"x": {"F": []}, "y": {"F": ["a"]}}
    )
    graph = build_current(
        load_config(project / "docs" / "cpdocs.yml"), output=project / "build", variants="primary"
    )
    assert list(graph.variants) == ["x"]
    assert not (project / "build" / "cpdocs" / "work" / "current" / "variants" / "y").exists()


def test_feature_mismatch_is_rejected(tmp_path: Path) -> None:
    project = fake_project(
        tmp_path / "p",
        features={"F": ["a"]},
        variants={"with-a": {"F": ["a"]}},
        echo={"with-a": {"F": []}},
    )
    with pytest.raises(ContractError, match="configured with features"):
        build_current(load_config(project / "docs" / "cpdocs.yml"), output=project / "build")


def test_failing_build_command_reports_its_output(tmp_path: Path) -> None:
    project = fake_project(tmp_path / "p")
    (project / "docs" / "cpdocs.yml").write_text(
        'contract: 1\nbuild:\n  describe: [["{python}", -c, "import sys; print(\'boom\'); sys.exit(3)"]]\n',
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="boom"):
        build_current(load_config(project / "docs" / "cpdocs.yml"), output=project / "build")


def test_undocumented_check_can_fail_the_build(tmp_path: Path) -> None:
    project = fake_project(tmp_path / "p", config="checks:\n  undocumented: fail\n")
    (project / "src" / "pkg" / "__init__.py").write_text("def silent(): pass\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="pkg.silent"):
        build_current(load_config(project / "docs" / "cpdocs.yml"), output=project / "build")


def test_versions_use_worktrees_policies_and_aliases(tmp_path: Path) -> None:
    project = fake_project(
        tmp_path / "p",
        features={"F": ["a"]},
        variants={"base": {"F": []}, "extra": {"F": ["a"]}},
        config=(
            "versions:\n"
            "  branches: {include: [main], variants: primary}\n"
            "  tags: {select: all, variants: all}\n"
            "  aliases: {stable: latest-tag, dev: main}\n"
        ),
    )
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
    assert metadata["default"] == "1.1"
    assert metadata["aliases"] == {"stable": "1.1", "dev": "main"}
    assert [entry["kind"] for entry in metadata["versions"]] == ["branch", "tag", "tag"]
    assert "1.1/" in (versions / "stable" / "index.html").read_text(encoding="utf-8")

    def graph(ref: str) -> dict:
        path = project / "build" / "cpdocs" / "work" / ref / "render" / "api-graph.json"
        return json.loads(path.read_text(encoding="utf-8"))

    assert set(graph("main")["variants"]) == {"base"}
    assert set(graph("1.0")["variants"]) == {"base", "extra"}
    assert "python:module:pkg.uncommitted" in graph("main")["entities"]
    assert "python:module:pkg.later" in graph("1.1")["entities"]
    assert "python:module:pkg.later" not in graph("1.0")["entities"]
    assert git(project, "worktree", "list").count("\n") == 1


def test_failure_policy_skip_keeps_going(tmp_path: Path) -> None:
    project = fake_project(tmp_path / "p", config="versions:\n  failure: skip\n")
    init_repository(project)
    git(project, "tag", "0.1")
    (project / "fake_build.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
    git(project, "commit", "-qam", "break the build")
    # main (the working tree) no longer builds; the tag still does.
    built = build_versions(load_config(project / "docs" / "cpdocs.yml"), output=project / "build")
    assert built == ["0.1"]


def test_cli_build_and_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = fake_project(tmp_path / "p")
    monkeypatch.chdir(project)
    assert main(["build", "--output", "out"]) == 0
    assert (project / "out" / "cpdocs" / "current" / "index.html").is_file()


def test_cli_prints_cmake_module(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["cmake-module"]) == 0
    path = Path(capsys.readouterr().out.strip())
    assert path.name == "cpdocs.cmake" and path.is_file()
