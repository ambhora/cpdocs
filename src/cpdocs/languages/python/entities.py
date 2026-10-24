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

import cpdocs.languages.kinds

_CLASS = (
    cpdocs.languages.kinds.Role.TYPE_PAGE | cpdocs.languages.kinds.Role.CLASS_LIKE | cpdocs.languages.kinds.Role.TYPE
)

ENTITY_KINDS = cpdocs.languages.kinds.EntityKinds(
    "python",
    (
        cpdocs.languages.kinds.EntityKind("package", "package", "P", 0, roles=cpdocs.languages.kinds.Role.CONTAINER),
        cpdocs.languages.kinds.EntityKind("module", "module", "M", 1, roles=cpdocs.languages.kinds.Role.CONTAINER),
        cpdocs.languages.kinds.EntityKind("class", "class", "C", 2, cpdocs.languages.kinds.TYPES, _CLASS),
        cpdocs.languages.kinds.EntityKind("protocol", "protocol", "P", 2, cpdocs.languages.kinds.TYPES, _CLASS),
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
            "constructor", "constructor", "F", 5, cpdocs.languages.kinds.FUNCTIONS, cpdocs.languages.kinds.Role.CALLABLE
        ),
        cpdocs.languages.kinds.EntityKind(
            "function", "function", "F", 6, cpdocs.languages.kinds.FUNCTIONS, cpdocs.languages.kinds.Role.CALLABLE
        ),
        cpdocs.languages.kinds.EntityKind(
            "method", "method", "F", 6, cpdocs.languages.kinds.FUNCTIONS, cpdocs.languages.kinds.Role.CALLABLE
        ),
        cpdocs.languages.kinds.EntityKind(
            "property", "property", "P", 7, cpdocs.languages.kinds.MEMBERS, cpdocs.languages.kinds.Role.VALUE
        ),
        cpdocs.languages.kinds.EntityKind(
            "attribute", "attribute", "A", 8, cpdocs.languages.kinds.MEMBERS, cpdocs.languages.kinds.Role.VALUE
        ),
        cpdocs.languages.kinds.EntityKind(
            "constant", "constant", "C", 8, cpdocs.languages.kinds.MEMBERS, cpdocs.languages.kinds.Role.VALUE
        ),
    ),
)

__all__ = ["ENTITY_KINDS"]
