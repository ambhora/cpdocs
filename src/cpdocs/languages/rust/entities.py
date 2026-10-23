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

from ..kinds import FUNCTIONS, MEMBERS, TYPES, EntityKind, EntityKinds, Role

_RECORD = Role.TYPE_PAGE | Role.CLASS_LIKE | Role.TYPE

ENTITY_KINDS = EntityKinds(
    "rust",
    (
        EntityKind("module", "module", "M", 1, roles=Role.CONTAINER),
        EntityKind("struct", "struct", "S", 2, TYPES, _RECORD),
        EntityKind("union", "union", "U", 2, TYPES, _RECORD),
        EntityKind("trait", "trait", "T", 2, TYPES, _RECORD),
        EntityKind("enum", "enum", "E", 3, TYPES, Role.TYPE_PAGE | Role.TYPE),
        EntityKind("type_alias", "type alias", "T", 4, TYPES, Role.TYPE),
        EntityKind("function", "function", "F", 6, FUNCTIONS, Role.CALLABLE),
        EntityKind("method", "method", "F", 6, FUNCTIONS, Role.CALLABLE),
        EntityKind("variable", "variable", "V", 8, MEMBERS, Role.VALUE),
        EntityKind("constant", "constant", "C", 8, MEMBERS, Role.VALUE),
        EntityKind("macro", "macro", "D", 9),
        EntityKind("field", "field", "·", 10),
        EntityKind("enum_value", "enum value", "·", 10),
        EntityKind("trait_alias", "trait alias", "·", 10),
    ),
)

__all__ = ["ENTITY_KINDS"]
