# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Read shared cpdocs assets from the distribution-level ``share`` directory."""

from __future__ import annotations

import functools
from importlib import resources
from pathlib import Path
from string import Template


def resource(*parts: str):
    """Return a resource from the shared, cross-program resource namespace.

    The project root contains ``share/cpdocs``. Hatch installs that directory
    under the same relative path, so source and wheel layouts agree.
    """
    try:
        root = resources.files("share")
    except ModuleNotFoundError:
        # Editable/source-only usage with PYTHONPATH pointing at src/, but not
        # the repository root. Installed wheels resolve the shared namespace.
        root = Path(__file__).resolve().parents[2] / "share"
    return root.joinpath("cpdocs", *parts)


@functools.cache
def shared_text(path: str) -> str:
    return resource(*path.split("/")).read_text(encoding="utf-8")


@functools.cache
def shared_template(path: str) -> Template:
    return Template(shared_text(path))
