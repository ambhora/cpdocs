# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""The repository's own workflows keep their hardening."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from conftest import REPOSITORY

WORKFLOWS = sorted((REPOSITORY / ".github" / "workflows").glob("*.yml"))


def _steps(workflow: dict[str, object]) -> list[dict[str, object]]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    return [step for job in jobs.values() for step in job.get("steps", [])]


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_workflow_permissions_are_explicit(path: Path) -> None:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "permissions" in workflow


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_actions_are_pinned_to_commits(path: Path) -> None:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    for step in _steps(workflow):
        uses = step.get("uses")
        if isinstance(uses, str):
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", uses), uses


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_checkouts_do_not_persist_credentials(path: Path) -> None:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    for step in _steps(workflow):
        uses = step.get("uses")
        if isinstance(uses, str) and uses.startswith("actions/checkout@"):
            assert step.get("with", {}).get("persist-credentials") is False


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_run_steps_do_not_inline_expressions(path: Path) -> None:
    # Values reach scripts through env, never by text substitution into the script.
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    for step in _steps(workflow):
        run = step.get("run")
        if isinstance(run, str):
            assert "${{" not in run, run
