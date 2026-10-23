# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Language-specific presentation contract used by generic renderers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property

from ..model import ApiEntity, ApiSignature
from .kinds import EntityKinds, Role


@dataclass(frozen=True)
class LanguageRendering:
    """Presentation rules that belong to a programming language, not to HTML.

    ``kinds`` is the language's table of entity kinds; the kind sets the renderer asks for, such as
    ``function_kinds``, are derived from the roles declared there.
    """

    separator: str
    kinds: EntityKinds
    source_suffixes: frozenset[str]
    signature_spelling: Callable[[ApiEntity, ApiSignature], str]
    entity_declaration: Callable[[ApiEntity], str]
    member_summary: Callable[[ApiEntity], str]

    @cached_property
    def container_kinds(self) -> frozenset[str]:
        return self.kinds.with_role(Role.CONTAINER)

    @cached_property
    def class_like_kinds(self) -> frozenset[str]:
        return self.kinds.with_role(Role.CLASS_LIKE)

    @cached_property
    def type_page_kinds(self) -> frozenset[str]:
        return self.kinds.with_role(Role.TYPE_PAGE)

    @cached_property
    def type_like_kinds(self) -> frozenset[str]:
        return self.kinds.with_role(Role.TYPE)

    @cached_property
    def function_kinds(self) -> frozenset[str]:
        return self.kinds.with_role(Role.CALLABLE)

    @cached_property
    def member_value_kinds(self) -> frozenset[str]:
        return self.kinds.with_role(Role.VALUE)

    def member_group(self, entity: ApiEntity) -> str | None:
        """The heading an entity is listed under on the page of its type, if it is listed there."""

        return self.kinds[entity.kind].group


def parameter_spelling(signature: ApiSignature) -> str:
    """Render conventional typed parameters used by C-family, Fortran and Rust APIs."""

    values: list[str] = []
    for parameter in signature.parameters:
        value = parameter.type or parameter.name
        if parameter.name and parameter.type:
            value += f" {parameter.name}"
        if parameter.default is not None:
            value += f" = {parameter.default}"
        values.append(value)
    return ", ".join(values)


def assigned_property(entity: ApiEntity) -> str:
    """Return an ``= value`` property without its marker."""

    return next((value[2:] for value in entity.properties if value.startswith("= ")), "")


def typed_property(entity: ApiEntity, *, ignored: frozenset[str] = frozenset()) -> str:
    """Return the first property that represents a type rather than an assignment/flag."""

    return next((value for value in entity.properties if not value.startswith("=") and value not in ignored), "")
