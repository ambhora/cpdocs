# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""The entity kinds of Fortran APIs.

| Kind | Declaration |
| --- | --- |
| ``module`` | a module |
| ``derived_type`` | a derived type, ``type :: name`` |
| ``function`` | a function of a module |
| ``subroutine`` | a subroutine of a module |
"""

from __future__ import annotations

import cpdocs.languages.kinds

ENTITY_KINDS = cpdocs.languages.kinds.EntityKinds(
    "fortran",
    (
        cpdocs.languages.kinds.EntityKind("module", "module", "M", 1, roles=cpdocs.languages.kinds.Role.CONTAINER),
        cpdocs.languages.kinds.EntityKind(
            "derived_type",
            "derived type",
            "T",
            2,
            cpdocs.languages.kinds.TYPES,
            cpdocs.languages.kinds.Role.TYPE_PAGE
            | cpdocs.languages.kinds.Role.CLASS_LIKE
            | cpdocs.languages.kinds.Role.TYPE,
        ),
        cpdocs.languages.kinds.EntityKind(
            "function", "function", "F", 6, cpdocs.languages.kinds.FUNCTIONS, cpdocs.languages.kinds.Role.CALLABLE
        ),
        cpdocs.languages.kinds.EntityKind(
            "subroutine", "subroutine", "F", 6, cpdocs.languages.kinds.FUNCTIONS, cpdocs.languages.kinds.Role.CALLABLE
        ),
    ),
)

__all__ = ["ENTITY_KINDS"]
