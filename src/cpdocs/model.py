# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Language-neutral API graph used by cpdocs' reference renderer."""

from __future__ import annotations

import collections.abc
import dataclasses
import hashlib
import pathlib


@dataclasses.dataclass(frozen=True)
class SourceLocation:
    path: str
    line: int | None = None
    column: int | None = None


@dataclasses.dataclass(frozen=True)
class ApiParameter:
    name: str
    type: str = ""
    default: str | None = None
    kind: str = ""


@dataclasses.dataclass(frozen=True)
class ApiAttribute:
    """One source-level attribute attached to an API declaration."""

    name: str
    spelling: str = ""


@dataclasses.dataclass(frozen=True)
class ApiSignature:
    parameters: tuple[ApiParameter, ...] = ()
    returns: str = ""
    qualifiers: tuple[str, ...] = ()
    attributes: tuple[ApiAttribute, ...] = ()
    spelling: str = ""
    template: str = ""
    # Documentation and location of this overload; not part of its identity.
    documentation: str = dataclasses.field(default="", compare=False)
    source: SourceLocation | None = dataclasses.field(default=None, compare=False)

    @property
    def compact(self) -> str:
        values = [parameter.type or parameter.name or "?" for parameter in self.parameters]
        return f"({', '.join(values)})"


@dataclasses.dataclass
class ApiEntity:
    id: str
    language: str
    kind: str
    name: str
    qualified_name: str
    parent: str | None = None
    signatures: list[ApiSignature] = dataclasses.field(default_factory=list)
    documentation: str = ""
    source: SourceLocation | None = None
    properties: list[str] = dataclasses.field(default_factory=list)
    feature_sets: list[str] = dataclasses.field(default_factory=list)
    children: list[str] = dataclasses.field(default_factory=list)
    bases: list[str] = dataclasses.field(default_factory=list)
    aliases: list[str] = dataclasses.field(default_factory=list)
    related: list[str] = dataclasses.field(default_factory=list)
    template: str = ""
    declaration: str = ""
    # Feature sets of each signature, parallel to ``signatures``; empty when unknown.
    signature_feature_sets: list[list[str]] = dataclasses.field(default_factory=list)

    def __post_init__(self) -> None:
        # Each language declares its kinds in cpdocs.languages.<language>.entities; an entity of a
        # kind its language does not declare could not be presented, so it is rejected here.
        import cpdocs.languages

        try:
            cpdocs.languages.entity_kind(self.language, self.kind)
        except (KeyError, ValueError) as error:
            raise ValueError(f"API entity {self.qualified_name!r}: {error.args[0]}") from None

    @property
    def navigation_label(self) -> str:
        # The outline is deliberately name-only.  Detailed/overload signatures belong to the
        # entity page and its local "On this page" navigation, not to the global API tree.
        return self.name

    @property
    def member_label(self) -> str:
        if self.kind in {"function", "subroutine", "method", "constructor"}:
            return f"{self.name}()"
        return self.name


@dataclasses.dataclass
class ApiGraph:
    project: str
    version: str
    language: str
    entities: dict[str, ApiEntity] = dataclasses.field(default_factory=dict)
    feature_sets: dict[str, dict[str, object]] = dataclasses.field(default_factory=dict)
    # ``sources`` are API declaration sources used by "defined in" links. ``files`` is the broader
    # browseable project/source hierarchy and may additionally contain implementation-only files.
    sources: dict[str, str] = dataclasses.field(default_factory=dict)
    files: dict[str, str] = dataclasses.field(default_factory=dict)
    metadata: dict[str, object] = dataclasses.field(default_factory=dict)

    def add(self, entity: ApiEntity) -> None:
        existing = self.entities.get(entity.id)
        if existing is None:
            self.entities[entity.id] = entity
            return

        while len(existing.signature_feature_sets) < len(existing.signatures):
            existing.signature_feature_sets.append([])
        for index, signature in enumerate(entity.signatures):
            incoming = entity.signature_feature_sets[index] if index < len(entity.signature_feature_sets) else []
            if signature not in existing.signatures:
                existing.signatures.append(signature)
                existing.signature_feature_sets.append(list(incoming))
                continue
            known = existing.signature_feature_sets[existing.signatures.index(signature)]
            known.extend(value for value in incoming if value not in known)
        for value in entity.properties:
            if value not in existing.properties:
                existing.properties.append(value)
        for value in entity.feature_sets:
            if value not in existing.feature_sets:
                existing.feature_sets.append(value)
        for value in entity.children:
            if value not in existing.children:
                existing.children.append(value)
        for value in entity.bases:
            if value not in existing.bases:
                existing.bases.append(value)
        for value in entity.aliases:
            if value not in existing.aliases:
                existing.aliases.append(value)
        for value in entity.related:
            if value not in existing.related:
                existing.related.append(value)
        if not existing.documentation and entity.documentation:
            existing.documentation = entity.documentation
        if existing.source is None and entity.source is not None:
            existing.source = entity.source
        if not existing.template and entity.template:
            existing.template = entity.template
        if not existing.declaration and entity.declaration:
            existing.declaration = entity.declaration

    def rebuild_children(self) -> None:
        for entity in self.entities.values():
            entity.children = []
        for entity in self.entities.values():
            if entity.parent and entity.parent in self.entities:
                parent = self.entities[entity.parent]
                if entity.id not in parent.children:
                    parent.children.append(entity.id)
        for entity in self.entities.values():
            entity.children.sort(key=lambda key: entity_sort_key(self.entities[key]))

    def roots(self) -> list[ApiEntity]:
        values = [
            entity for entity in self.entities.values() if not entity.parent or entity.parent not in self.entities
        ]
        return sorted(values, key=entity_sort_key)


def entity_sort_key(entity: ApiEntity) -> tuple[int, str, str]:
    """Sort entities in member lists: by the order their language gives their kind, then by name."""

    import cpdocs.languages

    return (
        cpdocs.languages.entity_kind(entity.language, entity.kind).order,
        entity.name.casefold(),
        entity.qualified_name,
    )


def stable_entity_id(language: str, kind: str, qualified_name: str, signature_key: str = "") -> str:
    suffix = f"::{signature_key}" if signature_key else ""
    return f"{language}:{kind}:{qualified_name}{suffix}"


def relative_source_path(path: str | pathlib.Path, project_root: pathlib.Path) -> str:
    """The logical path of a source file: relative to the project, or below ``_external``.

    A logical path names the page of the file in the published site, so it must stay relative. A
    file outside the project, such as a dependency's source named by a rustdoc span or a module
    root in an out-of-tree build directory, keeps its name below a digest of its directory. The
    absolute path would otherwise become an output path, and would publish the directory layout
    of the machine that built the documentation.
    """

    source = pathlib.Path(path)
    try:
        return source.resolve().relative_to(project_root.resolve()).as_posix()
    except (OSError, ValueError):
        pass
    try:
        absolute = source.resolve()
    except OSError:
        absolute = source.absolute()
    digest = hashlib.sha1(absolute.parent.as_posix().encode("utf-8")).hexdigest()[:10]
    return f"_external/{digest}/{absolute.name}"


def merge_graphs(
    graphs: collections.abc.Iterable[tuple[str, ApiGraph]], *, project: str, version: str, language: str
) -> ApiGraph:
    merged = ApiGraph(project=project, version=version, language=language)
    for feature_set_name, graph in graphs:
        for key, value in graph.metadata.items():
            merged.metadata.setdefault(key, value)
        merged.feature_sets[feature_set_name] = graph.feature_sets.get(feature_set_name, {})
        for source_path, content in graph.sources.items():
            merged.sources.setdefault(source_path, content)
        for source_path, content in graph.files.items():
            merged.files.setdefault(source_path, content)
        for entity in graph.entities.values():
            entity_copy = ApiEntity(
                id=entity.id,
                language=entity.language,
                kind=entity.kind,
                name=entity.name,
                qualified_name=entity.qualified_name,
                parent=entity.parent,
                signatures=list(entity.signatures),
                documentation=entity.documentation,
                source=entity.source,
                properties=list(entity.properties),
                feature_sets=list(entity.feature_sets),
                children=list(entity.children),
                bases=list(entity.bases),
                aliases=list(entity.aliases),
                related=list(entity.related),
                template=entity.template,
                declaration=entity.declaration,
                signature_feature_sets=[[feature_set_name] for _signature in entity.signatures],
            )
            if feature_set_name not in entity_copy.feature_sets:
                entity_copy.feature_sets.append(feature_set_name)
            merged.add(entity_copy)
    merged.rebuild_children()
    return merged
