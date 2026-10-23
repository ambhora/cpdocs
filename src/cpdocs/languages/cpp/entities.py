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

import cpdocs.languages.kinds

_RECORD = (
    cpdocs.languages.kinds.Role.TYPE_PAGE | cpdocs.languages.kinds.Role.CLASS_LIKE | cpdocs.languages.kinds.Role.TYPE
)

ENTITY_KINDS = cpdocs.languages.kinds.EntityKinds(
    "cpp",
    (
        cpdocs.languages.kinds.EntityKind(
            "namespace", "namespace", "N", 1, roles=cpdocs.languages.kinds.Role.CONTAINER
        ),
        cpdocs.languages.kinds.EntityKind("class", "class", "C", 2, cpdocs.languages.kinds.TYPES, _RECORD),
        cpdocs.languages.kinds.EntityKind("struct", "struct", "S", 2, cpdocs.languages.kinds.TYPES, _RECORD),
        cpdocs.languages.kinds.EntityKind("union", "union", "U", 2, cpdocs.languages.kinds.TYPES, _RECORD),
        cpdocs.languages.kinds.EntityKind(
            "enum",
            "enum",
            "E",
            3,
            cpdocs.languages.kinds.TYPES,
            cpdocs.languages.kinds.Role.TYPE_PAGE | cpdocs.languages.kinds.Role.TYPE,
        ),
        cpdocs.languages.kinds.EntityKind(
            "type_alias", "type alias", "T", 4, cpdocs.languages.kinds.TYPES, cpdocs.languages.kinds.Role.TYPE
        ),
        cpdocs.languages.kinds.EntityKind(
            "concept", "concept", "K", 4, cpdocs.languages.kinds.TYPES, cpdocs.languages.kinds.Role.TYPE
        ),
        cpdocs.languages.kinds.EntityKind(
            "constructor", "constructor", "F", 5, cpdocs.languages.kinds.FUNCTIONS, cpdocs.languages.kinds.Role.CALLABLE
        ),
        cpdocs.languages.kinds.EntityKind(
            "deduction_guide", "deduction guide", "G", 5, "Deduction Guides", cpdocs.languages.kinds.Role.CALLABLE
        ),
        cpdocs.languages.kinds.EntityKind(
            "function", "function", "F", 6, cpdocs.languages.kinds.FUNCTIONS, cpdocs.languages.kinds.Role.CALLABLE
        ),
        cpdocs.languages.kinds.EntityKind(
            "method", "method", "F", 6, cpdocs.languages.kinds.FUNCTIONS, cpdocs.languages.kinds.Role.CALLABLE
        ),
        cpdocs.languages.kinds.EntityKind(
            "attribute", "attribute", "A", 8, cpdocs.languages.kinds.MEMBERS, cpdocs.languages.kinds.Role.VALUE
        ),
        cpdocs.languages.kinds.EntityKind(
            "variable", "variable", "V", 8, cpdocs.languages.kinds.MEMBERS, cpdocs.languages.kinds.Role.VALUE
        ),
        cpdocs.languages.kinds.EntityKind(
            "constant", "constant", "C", 8, cpdocs.languages.kinds.MEMBERS, cpdocs.languages.kinds.Role.VALUE
        ),
        cpdocs.languages.kinds.EntityKind("macro", "macro", "D", 9),
    ),
)

__all__ = ["ENTITY_KINDS"]
