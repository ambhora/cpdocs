# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Read version-independent cpdocs templates and assets from packaged ``share`` files."""

from __future__ import annotations

import functools
from importlib import resources
from string import Template


def resource(*parts: str):
    """Return a packaged resource without requiring a source checkout or filesystem path."""
    return resources.files("cpdocs").joinpath("share", *parts)


@functools.cache
def shared_text(path: str) -> str:
    return resource(*path.split("/")).read_text(encoding="utf-8")


@functools.cache
def shared_template(path: str) -> Template:
    return Template(shared_text(path))
