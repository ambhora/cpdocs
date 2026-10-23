# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Where cpdocs may write and delete.

cpdocs writes and deletes only below directories it owns, and names inside them often come from
documented code or from the build system: unit identifiers, symbol names, source paths. These
helpers turn such names into paths that cannot leave the owning directory and delete only what
cpdocs created rather than the target of a symbolic link placed in its way.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

_SAFE_COMPONENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*")


def contained_path(root: Path, relative: Path) -> Path:
    """Return ``root / relative``, refusing any result that is not below ``root``.

    ``relative`` must be relative and free of ``..``. The joined path must also stay below the
    resolved root, so a symbolic link inside the tree cannot redirect it either.
    """

    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise RuntimeError(f"cpdocs refuses the output path {relative.as_posix()!r} below {root}")
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise RuntimeError(f"cpdocs refuses to write outside {root}: {path}")
    return path


def path_component(value: str) -> str:
    """One path component for an identifier chosen by a build system or by documented code.

    An identifier that already is a safe component is kept unchanged, so ordinary names keep their
    paths. Any other identifier is reduced to safe characters and given a digest of the original,
    so distinct identifiers stay distinct.
    """

    if _SAFE_COMPONENT.fullmatch(value):
        return value
    slug = re.sub(r"[^A-Za-z0-9_.+-]+", "-", value).strip("-.") or "id"
    return f"{slug}-{hashlib.sha1(value.encode('utf-8')).hexdigest()[:8]}"


def remove_tree(path: Path, *, owner: Path) -> None:
    """Delete the directory ``path`` below ``owner`` if it exists.

    ``owner`` is a directory the caller chose, such as the output root, and may itself be reached
    through symbolic links. Below it, cpdocs deletes only what it created: neither ``path`` nor any
    directory between ``owner`` and ``path`` may be a symbolic link. Python's ``shutil.rmtree``
    refuses a link itself, but resolving the path first, or ignoring that error and writing into the
    same path afterwards, would turn a link into a redirection of cpdocs's output.
    """

    current = owner
    for part in path.relative_to(owner).parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError(
                f"cpdocs refuses to replace {path}: {current} is a symbolic link; remove the link "
                "or choose another output directory"
            )
    if path.exists():
        shutil.rmtree(path)


__all__ = ["contained_path", "path_component", "remove_tree"]
