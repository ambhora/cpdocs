# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Read shared cpdocs assets from the distribution-level ``share`` directory."""

from __future__ import annotations

import functools
import pathlib
import string


def resource(*parts: str) -> pathlib.Path:
    """Locate shared assets in either the source tree or an installed wheel.

    The repository stores assets in ``share/cpdocs``; Hatch installs them at
    ``site-packages/share/cpdocs``. Do not use ``resources.files("share")``:
    ``share`` is a namespace shared with other directories (including
    ``test/share``), and its ``MultiplexedPath`` may resolve the wrong root.
    """
    package = pathlib.Path(__file__).resolve()
    for parent in (package.parents[1], package.parents[2]):
        root = parent / "share" / "cpdocs"
        if root.is_dir():
            return root.joinpath(*parts)
    raise FileNotFoundError("cpdocs shared resources are missing from share/cpdocs")


@functools.cache
def shared_text(path: str) -> str:
    return resource(*path.split("/")).read_text(encoding="utf-8")


@functools.cache
def shared_template(path: str) -> string.Template:
    return string.Template(shared_text(path))
