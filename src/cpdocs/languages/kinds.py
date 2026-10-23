# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""The entity kinds a language defines, and what the renderer does with each of them.

Every API entity has a kind, such as ``struct`` or ``function``. Kinds belong to a language: each
language package declares the complete list of kinds its extractor produces in its ``entities``
module, and an entity whose kind its language does not declare is rejected when it is created.

A kind declares everything presentation needs to know about it: its label and one-letter marker,
its position in member lists, the heading it is listed under on a type's page, and its roles. Adding
a kind to a language is therefore one entry in that language's table.
"""

from __future__ import annotations

import enum
from collections.abc import Iterator
from dataclasses import dataclass


class Role(enum.Flag):
    """What a kind is, as far as page layout is concerned.

    ``CONTAINER`` kinds, such as namespaces and modules, get a page listing their members.
    ``TYPE_PAGE`` kinds get a page of their own with their members grouped under headings, and
    ``CLASS_LIKE`` kinds among them can have bases and specializations. ``TYPE`` kinds name types and
    are linked from declarations. ``CALLABLE`` kinds have signatures, one card per overload. ``VALUE``
    kinds are data members, shown with their type and value.
    """

    NONE = 0
    CONTAINER = enum.auto()
    TYPE_PAGE = enum.auto()
    CLASS_LIKE = enum.auto()
    TYPE = enum.auto()
    CALLABLE = enum.auto()
    VALUE = enum.auto()


@dataclass(frozen=True)
class EntityKind:
    """One kind of entity of a language.

    ``name`` is the identifier in the API graph, ``label`` what readers see and ``marker`` the
    letter of its badge. Members are listed by ``order`` and then by name, so kinds with equal order
    are listed together. ``group`` is the heading the kind is listed under on the page of a type,
    or ``None`` if it is not listed there.
    """

    name: str
    label: str
    marker: str
    order: int
    group: str | None = None
    roles: Role = Role.NONE


class EntityKinds:
    """The kinds of one language, in declaration order."""

    def __init__(self, language: str, kinds: tuple[EntityKind, ...]) -> None:
        names = [kind.name for kind in kinds]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"{language} declares the entity kinds {', '.join(duplicates)} twice")
        self.language = language
        self._kinds = {kind.name: kind for kind in kinds}

    def __getitem__(self, name: str) -> EntityKind:
        try:
            return self._kinds[name]
        except KeyError:
            raise KeyError(
                f"{self.language} has no entity kind {name!r}; its kinds are {', '.join(self._kinds)}"
            ) from None

    def __contains__(self, name: object) -> bool:
        return name in self._kinds

    def __iter__(self) -> Iterator[EntityKind]:
        return iter(self._kinds.values())

    def with_role(self, role: Role) -> frozenset[str]:
        """The names of the kinds that have ``role``."""

        return frozenset(kind.name for kind in self if role in kind.roles)


# The headings of the member groups on the page of a type.
TYPES = "Public Types"
FUNCTIONS = "Public Functions"
MEMBERS = "Public Members"

__all__ = ["FUNCTIONS", "MEMBERS", "TYPES", "EntityKind", "EntityKinds", "Role"]
