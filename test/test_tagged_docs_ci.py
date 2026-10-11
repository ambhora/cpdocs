# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Ensure historical tag documentation is built by current tooling."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

from conftest import git, init_repository
from cpdocs.config import load_config

REPOSITORY = Path(__file__).resolve().parents[1]


def test_historical_tags_are_in_documented_versions() -> None:
    config = load_config(REPOSITORY / "docs" / "cpdocs.yml")
    assert config.versions[0] == "main"
    assert "0.0.1" in config.versions
    assert "0.3.7" in config.versions


def test_legacy_tag_rebuild_stays_on_default_branch() -> None:
    workflow = yaml.safe_load(
        (REPOSITORY / ".github" / "workflows" / "docs-tag-rebuild.yml").read_text(encoding="utf-8")
    )
    jobs = workflow["jobs"]["rebuild"]
    assert jobs["if"] == "github.event.workflow_run.event == 'push'"
    steps = jobs["steps"]
    checkout = steps[0]["with"]
    assert "github.event.repository.default_branch" in checkout["ref"]
    detect = next(step for step in steps if step.get("id") == "legacy")
    assert 'git tag --points-at "$HEAD_SHA"' in detect["run"]
    assert "rebuild-for-tag:" in detect["run"]
    assert "gh workflow run docs.yml" in steps[-1]["run"]


def test_tag_detection_handles_legacy_and_current_tags(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    workflow_file = repository / ".github" / "workflows" / "docs.yml"
    workflow_file.parent.mkdir(parents=True)
    workflow_file.write_text("name: documentation\njobs:\n  build:\n", encoding="utf-8")
    init_repository(repository)
    git(repository, "tag", "0.0.1")
    old_commit = git(repository, "rev-parse", "HEAD").strip()

    workflow_file.write_text("name: documentation\njobs:\n  rebuild-for-tag:\n", encoding="utf-8")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "relay tagged documentation")
    git(repository, "tag", "0.3.7")
    new_commit = git(repository, "rev-parse", "HEAD").strip()

    workflow = yaml.safe_load(
        (REPOSITORY / ".github" / "workflows" / "docs-tag-rebuild.yml").read_text(encoding="utf-8")
    )
    detect = next(
        step for step in workflow["jobs"]["rebuild"]["steps"] if step.get("id") == "legacy"
    )
    for commit, should_rebuild in ((old_commit, True), (new_commit, False)):
        output = tmp_path / "result.txt"
        output.write_text("", encoding="utf-8")
        result = subprocess.run(
            ["bash", "-eo", "pipefail", "-c", detect["run"]],
            cwd=repository,
            env={**os.environ, "HEAD_SHA": commit, "GITHUB_OUTPUT": str(output)},
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert ("rebuild=true" in output.read_text(encoding="utf-8")) == should_rebuild
