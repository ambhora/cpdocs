# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""The entity kinds of Python APIs.

| Kind | Declaration |
| --- | --- |
| ``package`` | a package, a directory with ``__init__.py`` |
| ``module`` | a module, one ``.py`` or ``.pyi`` file |
| ``class`` | a class |
| ``protocol`` | a class deriving from ``typing.Protocol`` |
| ``enum`` | a class deriving from ``enum.Enum``; its members are ``constant`` members |
| ``type_alias`` | a type alias, such as ``Vector = list[float]`` or a ``type`` statement |
| ``constructor`` | the ``__init__`` method of a class |
| ``function`` | a function of a module |
| ``method`` | a function of a class |
| ``property`` | a ``@property`` of a class |
| ``attribute`` | an annotated or assigned name of a module or class |
| ``constant`` | an upper-case module-level name or an enumeration member |
"""

from __future__ import annotations

from ..kinds import FUNCTIONS, MEMBERS, TYPES, EntityKind, EntityKinds, Role

_CLASS = Role.TYPE_PAGE | Role.CLASS_LIKE | Role.TYPE

ENTITY_KINDS = EntityKinds(
    "python",
    (
        EntityKind("package", "package", "P", 0, roles=Role.CONTAINER),
        EntityKind("module", "module", "M", 1, roles=Role.CONTAINER),
        EntityKind("class", "class", "C", 2, TYPES, _CLASS),
        EntityKind("protocol", "protocol", "P", 2, TYPES, _CLASS),
        EntityKind("enum", "enum", "E", 3),
        EntityKind("type_alias", "type alias", "T", 4, TYPES, Role.TYPE),
        EntityKind("constructor", "constructor", "F", 5, FUNCTIONS, Role.CALLABLE),
        EntityKind("function", "function", "F", 6, FUNCTIONS, Role.CALLABLE),
        EntityKind("method", "method", "F", 6, FUNCTIONS, Role.CALLABLE),
        EntityKind("property", "property", "P", 7, MEMBERS, Role.VALUE),
        EntityKind("attribute", "attribute", "A", 8, MEMBERS, Role.VALUE),
        EntityKind("constant", "constant", "C", 8, MEMBERS, Role.VALUE),
    ),
)

__all__ = ["ENTITY_KINDS"]
