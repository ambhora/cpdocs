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

from ..kinds import FUNCTIONS, TYPES, EntityKind, EntityKinds, Role

ENTITY_KINDS = EntityKinds(
    "fortran",
    (
        EntityKind("module", "module", "M", 1, roles=Role.CONTAINER),
        EntityKind("derived_type", "derived type", "T", 2, TYPES, Role.TYPE_PAGE | Role.CLASS_LIKE | Role.TYPE),
        EntityKind("function", "function", "F", 6, FUNCTIONS, Role.CALLABLE),
        EntityKind("subroutine", "subroutine", "F", 6, FUNCTIONS, Role.CALLABLE),
    ),
)

__all__ = ["ENTITY_KINDS"]
