# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""The repository's own workflows keep their hardening."""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

import conftest

WORKFLOWS = sorted((conftest.REPOSITORY / ".github" / "workflows").glob("*.yml"))


def _steps(workflow: dict[str, object]) -> list[dict[str, object]]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    return [step for job in jobs.values() for step in job.get("steps", [])]


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_workflow_permissions_are_explicit(path: pathlib.Path) -> None:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "permissions" in workflow


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_actions_are_pinned_to_commits(path: pathlib.Path) -> None:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    for step in _steps(workflow):
        uses = step.get("uses")
        if isinstance(uses, str):
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", uses), uses


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_pins_name_their_release_on_their_own_line(path: pathlib.Path) -> None:
    # Dependabot updates a version comment only on the line of the pin; one on the line above would
    # keep naming the old release.
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        assert not re.fullmatch(r"\s*# v\d+(\.\d+)*", line), line
        if re.search(r"uses: \S+@[0-9a-f]{40}", line):
            assert re.search(r"@[0-9a-f]{40} # v\d+\.\d+\.\d+$", line), line


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_checkouts_do_not_persist_credentials(path: pathlib.Path) -> None:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    for step in _steps(workflow):
        uses = step.get("uses")
        if isinstance(uses, str) and uses.startswith("actions/checkout@"):
            assert step.get("with", {}).get("persist-credentials") is False


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_run_steps_do_not_inline_expressions(path: pathlib.Path) -> None:
    # Values reach scripts through env, never by text substitution into the script.
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    for step in _steps(workflow):
        run = step.get("run")
        if isinstance(run, str):
            assert "${{" not in run, run
