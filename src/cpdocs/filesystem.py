# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Where cpdocs may write.

cpdocs writes only below directories it owns, and names inside them often come from documented
code or from the build system: unit identifiers, symbol names, source paths. These helpers turn
such names into paths that cannot leave the owning directory.
"""

from __future__ import annotations

import hashlib
import re
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


__all__ = ["contained_path", "path_component"]
