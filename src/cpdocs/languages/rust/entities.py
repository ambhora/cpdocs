# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""The entity kinds of Rust APIs, as read from rustdoc JSON.

| Kind | Declaration |
| --- | --- |
| ``module`` | a module, the crate root included |
| ``struct``, ``union`` | a struct or union |
| ``enum`` | an enumeration; its variants are ``enum_value`` members |
| ``trait`` | a trait |
| ``trait_alias`` | a trait alias |
| ``type_alias`` | a type alias or an associated type |
| ``function`` | a free function |
| ``method`` | a function of an inherent ``impl`` block |
| ``field`` | a field of a struct |
| ``enum_value`` | a variant of an enumeration |
| ``variable`` | a ``static`` item |
| ``constant`` | a ``const`` item or an associated constant |
| ``macro`` | a ``macro_rules!`` macro or a procedural macro |
"""

from __future__ import annotations

import cpdocs.languages.kinds

_RECORD = (
    cpdocs.languages.kinds.Role.TYPE_PAGE | cpdocs.languages.kinds.Role.CLASS_LIKE | cpdocs.languages.kinds.Role.TYPE
)

ENTITY_KINDS = cpdocs.languages.kinds.EntityKinds(
    "rust",
    (
        cpdocs.languages.kinds.EntityKind("module", "module", "M", 1, roles=cpdocs.languages.kinds.Role.CONTAINER),
        cpdocs.languages.kinds.EntityKind("struct", "struct", "S", 2, cpdocs.languages.kinds.TYPES, _RECORD),
        cpdocs.languages.kinds.EntityKind("union", "union", "U", 2, cpdocs.languages.kinds.TYPES, _RECORD),
        cpdocs.languages.kinds.EntityKind("trait", "trait", "T", 2, cpdocs.languages.kinds.TYPES, _RECORD),
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
            "function", "function", "F", 6, cpdocs.languages.kinds.FUNCTIONS, cpdocs.languages.kinds.Role.CALLABLE
        ),
        cpdocs.languages.kinds.EntityKind(
            "method", "method", "F", 6, cpdocs.languages.kinds.FUNCTIONS, cpdocs.languages.kinds.Role.CALLABLE
        ),
        cpdocs.languages.kinds.EntityKind(
            "variable", "variable", "V", 8, cpdocs.languages.kinds.MEMBERS, cpdocs.languages.kinds.Role.VALUE
        ),
        cpdocs.languages.kinds.EntityKind(
            "constant", "constant", "C", 8, cpdocs.languages.kinds.MEMBERS, cpdocs.languages.kinds.Role.VALUE
        ),
        cpdocs.languages.kinds.EntityKind("macro", "macro", "D", 9),
        cpdocs.languages.kinds.EntityKind("field", "field", "·", 10),
        cpdocs.languages.kinds.EntityKind("enum_value", "enum value", "·", 10),
        cpdocs.languages.kinds.EntityKind("trait_alias", "trait alias", "·", 10),
    ),
)

__all__ = ["ENTITY_KINDS"]
