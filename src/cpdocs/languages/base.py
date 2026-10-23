# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Language-specific presentation contract used by generic renderers."""

from __future__ import annotations

import collections.abc
import dataclasses
import functools

import cpdocs.languages.kinds
import cpdocs.model


@dataclasses.dataclass(frozen=True)
class LanguageRendering:
    """Presentation rules that belong to a programming language, not to HTML.

    ``kinds`` is the language's table of entity kinds; the kind sets the renderer asks for, such as
    ``function_kinds``, are derived from the roles declared there.
    """

    separator: str
    kinds: cpdocs.languages.kinds.EntityKinds
    source_suffixes: frozenset[str]
    signature_spelling: collections.abc.Callable[[cpdocs.model.ApiEntity, cpdocs.model.ApiSignature], str]
    entity_declaration: collections.abc.Callable[[cpdocs.model.ApiEntity], str]
    member_summary: collections.abc.Callable[[cpdocs.model.ApiEntity], str]

    @functools.cached_property
    def container_kinds(self) -> frozenset[str]:
        return self.kinds.with_role(cpdocs.languages.kinds.Role.CONTAINER)

    @functools.cached_property
    def class_like_kinds(self) -> frozenset[str]:
        return self.kinds.with_role(cpdocs.languages.kinds.Role.CLASS_LIKE)

    @functools.cached_property
    def type_page_kinds(self) -> frozenset[str]:
        return self.kinds.with_role(cpdocs.languages.kinds.Role.TYPE_PAGE)

    @functools.cached_property
    def type_like_kinds(self) -> frozenset[str]:
        return self.kinds.with_role(cpdocs.languages.kinds.Role.TYPE)

    @functools.cached_property
    def function_kinds(self) -> frozenset[str]:
        return self.kinds.with_role(cpdocs.languages.kinds.Role.CALLABLE)

    @functools.cached_property
    def member_value_kinds(self) -> frozenset[str]:
        return self.kinds.with_role(cpdocs.languages.kinds.Role.VALUE)

    def member_group(self, entity: cpdocs.model.ApiEntity) -> str | None:
        """The heading an entity is listed under on the page of its type, if it is listed there."""

        return self.kinds[entity.kind].group


def parameter_spelling(signature: cpdocs.model.ApiSignature) -> str:
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


def assigned_property(entity: cpdocs.model.ApiEntity) -> str:
    """Return an ``= value`` property without its marker."""

    return next((value[2:] for value in entity.properties if value.startswith("= ")), "")


def typed_property(entity: cpdocs.model.ApiEntity, *, ignored: frozenset[str] = frozenset()) -> str:
    """Return the first property that represents a type rather than an assignment/flag."""

    return next((value for value in entity.properties if not value.startswith("=") and value not in ignored), "")
