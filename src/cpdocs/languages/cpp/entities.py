# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""The entity kinds of C, C++, CUDA and HIP APIs.

| Kind | Declaration |
| --- | --- |
| ``namespace`` | a namespace |
| ``class``, ``struct``, ``union`` | a record, including class templates and their specializations |
| ``enum`` | an enumeration; its enumerators are ``constant`` members |
| ``type_alias`` | a ``typedef`` or ``using`` alias |
| ``concept`` | a C++20 concept |
| ``constructor`` | a constructor of a record |
| ``deduction_guide`` | a class template argument deduction guide |
| ``function`` | a free function, including function templates |
| ``method`` | a member function, destructor or conversion function |
| ``attribute`` | a data member of a record |
| ``variable`` | a variable at namespace scope or a static data member |
| ``constant`` | an enumerator |
| ``macro`` | a function-like or object-like macro defined in a public header |
"""

from __future__ import annotations

from ..kinds import FUNCTIONS, MEMBERS, TYPES, EntityKind, EntityKinds, Role

_RECORD = Role.TYPE_PAGE | Role.CLASS_LIKE | Role.TYPE

ENTITY_KINDS = EntityKinds(
    "cpp",
    (
        EntityKind("namespace", "namespace", "N", 1, roles=Role.CONTAINER),
        EntityKind("class", "class", "C", 2, TYPES, _RECORD),
        EntityKind("struct", "struct", "S", 2, TYPES, _RECORD),
        EntityKind("union", "union", "U", 2, TYPES, _RECORD),
        EntityKind("enum", "enum", "E", 3, TYPES, Role.TYPE_PAGE | Role.TYPE),
        EntityKind("type_alias", "type alias", "T", 4, TYPES, Role.TYPE),
        EntityKind("concept", "concept", "K", 4, TYPES, Role.TYPE),
        EntityKind("constructor", "constructor", "F", 5, FUNCTIONS, Role.CALLABLE),
        EntityKind("deduction_guide", "deduction guide", "G", 5, "Deduction Guides", Role.CALLABLE),
        EntityKind("function", "function", "F", 6, FUNCTIONS, Role.CALLABLE),
        EntityKind("method", "method", "F", 6, FUNCTIONS, Role.CALLABLE),
        EntityKind("attribute", "attribute", "A", 8, MEMBERS, Role.VALUE),
        EntityKind("variable", "variable", "V", 8, MEMBERS, Role.VALUE),
        EntityKind("constant", "constant", "C", 8, MEMBERS, Role.VALUE),
        EntityKind("macro", "macro", "D", 9),
    ),
)

__all__ = ["ENTITY_KINDS"]
