# SPDX-FileCopyrightText: 2026 cpdocs developers
#
# SPDX-License-Identifier: Apache-2.0
"""Standalone HTML renderer for cpdocs API references.

The project documentation is rendered by ProperDocs, but API references have different navigation
and versioning semantics.  This renderer therefore consumes the language-neutral :class:`ApiGraph`
directly and emits a self-contained code browser without routing the reference through Markdown,
MkDocs, Sphinx, Doxygen, Breathe, or Exhale.
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import html
import json
import posixpath
import re
import shutil
from pathlib import Path, PurePosixPath

from markdown_it import MarkdownIt

from .model import ApiEntity, ApiGraph, ApiSignature, entity_sort_key
from .render import (
    _CLASS_LIKE_KINDS,
    _documentation_blocks,
    _embedded_member_parent,
    _entity_declaration,
    _highlight_declaration,
    _highlight_source_lines,
    _kind_marker,
    _member_anchor,
    _member_summary_spelling,
    _relative_link,
    _signature_spelling,
    _source_document,
    _source_language,
    _feature_set_anchor,
    assign_documents,
    entity_document,
)

_CONTAINER_KINDS = {"namespace", "module", "package"}
_FUNCTION_KINDS = {"function", "subroutine", "method", "constructor", "deduction_guide"}
_TYPE_KINDS = {"class", "struct", "derived_type", "union", "enum", "trait", "protocol", "type_alias", "concept"}
_MEMBER_VALUE_KINDS = {"property", "attribute", "variable", "constant"}

_INLINE_DOCUMENTATION = re.compile(
    r"`(?P<code>[^`]+)`"
    r"|\*\*(?P<strong>[^*\n]+?)\*\*"
    r"|\[(?P<label>[^\]]+)\]\((?P<href>[^)]+)\)"
    r"|@projectdocs(?:\{(?P<project_path>[^}]+)\})?"
)
_PROJECTDOCS_HREF = re.compile(r'href=(?P<quote>["\'])projectdocs:(?P<path>[^"\']*)(?P=quote)')

_MARKDOWN = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})


# ---------------------------------------------------------------------------
# Paths and links
# ---------------------------------------------------------------------------


def _output_directory(document: Path) -> Path:
    if document.name == "index.md":
        return document.parent
    return document.with_suffix("")


def _output_file(document: Path) -> Path:
    return _output_directory(document) / "index.html"


def _root_relative(document: Path, target: str) -> str:
    directory = _output_directory(document)
    value = posixpath.relpath(target, directory.as_posix() or ".")
    if target.endswith("/") and not value.endswith("/"):
        value += "/"
    return value


def _page_href(source: Path, target: Path, anchor: str = "") -> str:
    value = _relative_link(source, target)
    return value + (f"#{anchor}" if anchor else "")


def _project_docs_target(document: Path, project_docs_url: str, target: str = "") -> str:
    """Resolve one semantic ``projectdocs:`` target for the current API page.

    ``target`` is always interpreted relative to the root of the non-versioned project site.  This
    is deliberately different from a normal relative hyperlink: every historical API version must
    continue to point at the single current project website.
    """

    base = _project_docs_href(document, project_docs_url)
    target = target.strip()
    if not target:
        return base
    if target.startswith("#"):
        return base + target

    path, separator, fragment = target.partition("#")
    value = base.rstrip("/") + "/" + path.lstrip("/")
    if path.endswith("/") and not value.endswith("/"):
        value += "/"
    if separator:
        value += "#" + fragment
    return value


def _resolve_projectdocs_links(fragment: str, document: Path, project_docs_url: str) -> str:
    """Resolve semantic project-site links after a page has been placed in the API tree."""

    def replace(match: re.Match[str]) -> str:
        target = _project_docs_target(
            document, project_docs_url, html.unescape(match.group("path"))
        )
        quote = match.group("quote")
        return f"href={quote}{html.escape(target, quote=True)}{quote}"

    return _PROJECTDOCS_HREF.sub(replace, fragment)


def _entity_target(entity: ApiEntity, graph: ApiGraph) -> tuple[Path, str]:
    parent = _embedded_member_parent(entity, graph)
    if parent is not None:
        return entity_document(parent), _member_anchor(entity)
    return entity_document(entity), ""


def _entity_href(source: Path, entity: ApiEntity, graph: ApiGraph) -> str:
    target, anchor = _entity_target(entity, graph)
    return _page_href(source, target, anchor)


def _display_source_path(source_path: str, graph: ApiGraph) -> str:
    """Return the source path shown to readers while preserving the real repository path for links."""
    source_root = str(graph.metadata.get("source_root") or "").strip("/")
    logical = PurePosixPath(source_path)
    if not source_root:
        return logical.as_posix()
    root = PurePosixPath(source_root)
    try:
        return logical.relative_to(root).as_posix()
    except ValueError:
        return logical.as_posix()


def _source_href(source_document: Path, entity: ApiEntity, graph: ApiGraph) -> str | None:
    if entity.source is None or entity.source.path not in graph.sources:
        return None
    value = _page_href(source_document, _source_document(entity.source.path))
    if entity.source.line:
        value += f"#L{entity.source.line}"
    return value


# ---------------------------------------------------------------------------
# Shared fragments
# ---------------------------------------------------------------------------


def _kind_label(kind: str) -> str:
    return {
        "namespace": "namespace",
        "module": "module",
        "package": "package",
        "class": "class",
        "struct": "struct",
        "derived_type": "derived type",
        "union": "union",
        "enum": "enum",
        "trait": "trait",
        "protocol": "protocol",
        "type_alias": "type alias",
        "concept": "concept",
        "function": "function",
        "subroutine": "subroutine",
        "method": "method",
        "constructor": "constructor",
        "property": "property",
        "attribute": "attribute",
        "variable": "variable",
        "constant": "constant",
        "macro": "macro",
        "deduction_guide": "deduction guide",
    }.get(kind, kind.replace("_", " "))


def _kind_badge(kind: str) -> str:
    marker = html.escape(_kind_marker(kind))
    return f'<span class="api-kind" title="{html.escape(_kind_label(kind))}">{marker}</span>'


_LANGUAGE_LABELS = {
    "c": "C",
    "cpp": "C++",
    "cuda": "CUDA",
    "hip": "HIP",
    "fortran": "Fortran",
    "python": "Python",
    "rust": "Rust",
}


def _language_label(language: str) -> str:
    return _LANGUAGE_LABELS.get(language, language)


def _language_badge(entity: ApiEntity) -> str:
    if entity.kind in _CONTAINER_KINDS:
        return ""
    label = _language_label(entity.language)
    return f'<span class="api-language-badge">{html.escape(label)}</span>'


def _feature_set_features(graph: ApiGraph, key: str) -> tuple[str, ...]:
    metadata = graph.feature_sets.get(key, {})
    if not isinstance(metadata, dict):
        return ()
    features = metadata.get("features", [])
    if not isinstance(features, list):
        return ()
    return tuple(str(feature) for feature in features)


def _feature_set_text(graph: ApiGraph, key: str) -> str:
    features = _feature_set_features(graph, key)
    return ", ".join(features) if features else "default"


def _feature_set_inline(graph: ApiGraph, key: str) -> str:
    features = _feature_set_features(graph, key)
    if not features:
        return '<span class="api-feature-set-empty">default (no features enabled)</span>'
    return " ".join(f'<code>{html.escape(feature)}</code>' for feature in features)


def _legend(graph: ApiGraph) -> str:
    present = {entity.kind for entity in graph.entities.values()}
    order = [
        "namespace",
        "module",
        "package",
        "class",
        "struct",
        "union",
        "enum",
        "trait",
        "protocol",
        "concept",
        "function",
        "macro",
    ]
    entries = []
    for kind in order:
        if kind not in present:
            continue
        entries.append(
            f'<span class="api-legend-entry">{_kind_badge(kind)} {_kind_label(kind)}</span>'
        )
    return (
        '<div class="api-legend">'
        + '<span class="api-legend-separator">·</span>'.join(entries)
        + "</div>"
    )


def _visible_outline_children(entity: ApiEntity, graph: ApiGraph) -> list[ApiEntity]:
    # Public members of records live on the record page and should not duplicate themselves in the
    # global API outline.  Namespaces/modules/packages retain their recursive API tree.
    if entity.kind in _CLASS_LIKE_KINDS or entity.kind == "enum":
        return []
    values = [
        graph.entities[child_id]
        for child_id in entity.children
        if child_id in graph.entities and graph.entities[child_id].kind != "macro"
    ]
    return sorted(values, key=entity_sort_key)


def _is_ancestor(candidate: ApiEntity, current: ApiEntity | None, graph: ApiGraph) -> bool:
    entity = current
    while entity is not None:
        if entity.id == candidate.id:
            return True
        if not entity.parent or entity.parent not in graph.entities:
            break
        entity = graph.entities[entity.parent]
    return False


def _outline_entity(
    entity: ApiEntity, graph: ApiGraph, document: Path, current: ApiEntity | None
) -> str:
    children = _visible_outline_children(entity, graph)
    expanded = bool(children and _is_ancestor(entity, current, graph))
    active = current is not None and entity.id == current.id
    href = _entity_href(document, entity, graph)
    row = [
        '<div class="api-outline-row' + (" is-current" if active else "") + '">',
        _kind_badge(entity.kind),
        f'<a class="api-outline-link" href="{html.escape(href)}">{html.escape(entity.member_label)}</a>',
        f'<span class="api-outline-language">{_language_badge(entity)}</span>',
    ]
    if children:
        state = "true" if expanded else "false"
        row.append(
            f'<button class="api-outline-toggle" type="button" aria-expanded="{state}" '
            f'aria-label="{"Collapse" if expanded else "Expand"} {html.escape(entity.qualified_name)}"></button>'
        )
    row.append("</div>")
    child_html = ""
    if children:
        hidden = "" if expanded else " hidden"
        child_html = (
            '<ul class="api-outline-children"'
            + hidden
            + ">"
            + "".join(
                "<li>" + _outline_entity(child, graph, document, current) + "</li>"
                for child in children
            )
            + "</ul>"
        )
    return "".join(row) + child_html


def _outline(
    graph: ApiGraph, document: Path, current: ApiEntity | None, *, current_special: str = ""
) -> str:
    roots = [entity for entity in graph.roots() if entity.kind != "macro"]
    macros = sorted(
        (entity for entity in graph.entities.values() if entity.kind == "macro"),
        key=entity_sort_key,
    )
    current_label = (
        current.name
        if current is not None
        else {
            "home": "Home",
            "feature_sets": "Feature Sets",
            "macros": "Macros",
            "source": "Source",
        }.get(current_special, "")
    )
    home_current = current is None and current_special == "home"
    feature_sets_current = current_special == "feature_sets"
    parts = [
        '<nav class="api-outline" aria-label="API outline">',
        "<h2>Outline</h2>",
        # On small screens the outline collapses behind this button, which names the current page.
        '<button class="api-outline-panel-toggle" type="button" aria-expanded="false"'
        ' aria-controls="api-outline-tree"><span>Outline</span>'
        f'<span class="api-outline-current">{html.escape(current_label)}</span></button>',
        '<ul class="api-outline-root" id="api-outline-tree">',
        '<li><div class="api-outline-row' + (" is-current" if home_current else "") + '">',
        '<span class="api-kind api-kind-home">H</span>',
        f'<a class="api-outline-link" href="{html.escape(_page_href(document, Path("index.md")))}">Home</a>',
        "</div></li>",
    ]
    if graph.feature_sets:
        parts.extend(
            [
                '<li><div class="api-outline-row'
                + (" is-current" if feature_sets_current else "")
                + '">',
                '<span class="api-kind api-kind-empty"></span>',
                f'<a class="api-outline-link" href="{html.escape(_page_href(document, Path("feature-sets.md")))}">Feature Sets</a>',
                "</div></li>",
            ]
        )
    for entity in roots:
        parts.append("<li>" + _outline_entity(entity, graph, document, current) + "</li>")
    if macros:
        macro_open = current is not None and current.kind == "macro"
        parts.extend(
            [
                "<li>",
                '<div class="api-outline-row">',
                '<span class="api-kind api-kind-empty"></span>',
                '<a class="api-outline-link" href="'
                + html.escape(_page_href(document, Path("macros.md")))
                + '">Macros</a>',
                f'<button class="api-outline-toggle" type="button" aria-expanded="{"true" if macro_open else "false"}" aria-label="{"Collapse" if macro_open else "Expand"} Macros"></button>',
                "</div>",
                '<ul class="api-outline-children"' + ("" if macro_open else " hidden") + ">",
            ]
        )
        for macro in macros:
            active = current is not None and macro.id == current.id
            parts.append(
                '<li><div class="api-outline-row'
                + (" is-current" if active else "")
                + '">'
                + _kind_badge("macro")
                + f'<a class="api-outline-link" href="{html.escape(_entity_href(document, macro, graph))}">{html.escape(macro.name)}</a>'
                + "</div></li>"
            )
        parts.extend(["</ul>", "</li>"])
    parts.extend(["</ul>", "</nav>"])
    return "".join(parts)


def _toc(items: list[tuple[str, str, int]]) -> str:
    if not items:
        return '<aside class="api-toc"><h2>On this page</h2></aside>'
    parts = ['<aside class="api-toc"><h2>On this page</h2><ul>']
    for label, anchor, level in items:
        parts.append(
            f'<li class="toc-level-{level}"><a href="#{html.escape(anchor)}">{html.escape(label)}</a></li>'
        )
    parts.append("</ul></aside>")
    return "".join(parts)


def _inline_documentation(text: str) -> str:
    """Render the small Markdown-like inline subset accepted in extracted API prose.

    API comments are intentionally not routed through a full Markdown engine.  We only need stable,
    predictable inline constructs here: code spans, Markdown links, and cpdocs's ``@projectdocs``
    shorthand.  A Markdown link may use ``projectdocs:`` as its destination and is resolved later,
    once the renderer knows the final depth of the generated API page.
    """

    result: list[str] = []
    position = 0
    for match in _INLINE_DOCUMENTATION.finditer(text):
        result.append(html.escape(text[position : match.start()]))
        if match.group("code") is not None:
            result.append(f"<code>{html.escape(match.group('code'))}</code>")
        elif match.group("strong") is not None:
            result.append(f"<strong>{html.escape(match.group('strong'))}</strong>")
        elif match.group("label") is not None:
            label = html.escape(match.group("label"))
            href = match.group("href").strip()
            # Reject executable URL schemes in comments.  Ordinary relative links, anchors,
            # HTTP(S), mailto and projectdocs semantic links remain available.
            if re.match(r"(?i)^(?:javascript|data|vbscript):", href):
                result.append(label)
            else:
                result.append(f'<a href="{html.escape(href, quote=True)}">{label}</a>')
        else:
            target = (match.group("project_path") or "").strip()
            label = target.rstrip("/") or "project documentation"
            result.append(
                f'<a href="projectdocs:{html.escape(target, quote=True)}">{html.escape(label)}</a>'
            )
        position = match.end()
    result.append(html.escape(text[position:]))
    return "".join(result)


_DOCUMENTATION_FIELD = re.compile(
    r"@(?P<command>tparam|param|returns?|throws?)\b\s*(?P<rest>.*)", re.DOTALL
)
_FIELD_TITLES = {
    "tparam": "Template parameters",
    "param": "Parameters",
    "return": "Returns",
    "throws": "Throws",
}


def _documentation_description(text: str) -> str:
    """Render documentation prose, followed by its parameter, return and exception fields.

    Paragraphs of the form ``@tparam NAME text``, ``@param NAME text``, ``@return text`` and
    ``@throws text`` are collected, wherever they appear, into titled lists after the prose.
    """

    paragraphs: list[str] = []
    fields: dict[str, list[tuple[str, str]]] = {}
    for block in re.split(r"\n\s*\n", text.strip()):
        paragraph = block.strip()
        if not paragraph or paragraph.startswith("CPDOCS-API-RELATES-TO:"):
            continue
        # Doc-comment line wrapping is not semantically significant.  Keep explicit Markdown-like
        # inline syntax intact while presenting the prose as a normal paragraph.
        normalized = " ".join(line.strip() for line in paragraph.splitlines())
        field = _DOCUMENTATION_FIELD.fullmatch(normalized)
        if field is None:
            paragraphs.append(f"<p>{_inline_documentation(normalized)}</p>")
            continue
        command = {"returns": "return", "throw": "throws"}.get(
            field.group("command"), field.group("command")
        )
        rest = field.group("rest").strip()
        if command in {"tparam", "param"}:
            name, _, description = rest.partition(" ")
            fields.setdefault(command, []).append((name, description.strip()))
        else:
            fields.setdefault(command, []).append(("", rest))
    for command in ("tparam", "param", "return", "throws"):
        entries = fields.get(command)
        if not entries:
            continue
        paragraphs.append(
            f'<div class="api-doc-field"><p class="api-doc-field-title">{_FIELD_TITLES[command]}</p>'
        )
        if command in {"tparam", "param"}:
            paragraphs.append(
                "<dl>"
                + "".join(
                    f"<dt><code>{html.escape(name)}</code></dt><dd>{_inline_documentation(description)}</dd>"
                    for name, description in entries
                )
                + "</dl>"
            )
        else:
            paragraphs.extend(f"<p>{_inline_documentation(value)}</p>" for _name, value in entries)
        paragraphs.append("</div>")
    return "".join(paragraphs)


def _documentation(entity: ApiEntity, graph: ApiGraph, document: Path) -> str:
    _, related = _documentation_blocks(entity, graph)
    description = _documentation_description(entity.documentation)
    if not description and not related:
        description = '<p class="api-undocumented">No API documentation has been provided.</p>'
    if not related:
        return description
    links: list[str] = []
    for text, target in related:
        if target is None:
            links.append(f"<code>{html.escape(text)}</code>")
        else:
            links.append(
                f'<a href="{html.escape(_entity_href(document, target, graph))}"><code>{html.escape(target.name)}</code></a>'
            )
    return (
        description
        + '<p class="api-related"><strong>Related:</strong> '
        + " · ".join(links)
        + "</p>"
    )


def _availability(
    entity: ApiEntity,
    graph: ApiGraph,
    document: Path,
    feature_sets: list[str] | None = None,
) -> str:
    keys = feature_sets if feature_sets else entity.feature_sets
    if not keys:
        return ""
    rows = []
    for key in keys:
        href = _page_href(document, Path("feature-sets.md"), _feature_set_anchor(key))
        rows.append(
            '<li><a href="'
            + html.escape(href)
            + '">'
            + _feature_set_inline(graph, key)
            + "</a></li>"
        )
    return (
        '<div class="api-availability"><strong>Available in feature sets</strong>'
        '<ul class="api-availability-list">'
        + "".join(rows)
        + "</ul></div>"
    )


def _defined_in(entity: ApiEntity, graph: ApiGraph, document: Path) -> str:
    if entity.kind in _CONTAINER_KINDS or entity.source is None:
        return ""
    href = _source_href(document, entity, graph)
    label = Path(entity.source.path).name
    if href:
        return f'<p class="api-defined">Defined in <a href="{html.escape(href)}">{html.escape(label)}</a></p>'
    return f'<p class="api-defined">Defined in <code>{html.escape(label)}</code></p>'


def _definition_row(entity: ApiEntity, graph: ApiGraph, document: Path) -> str:
    if entity.source is None:
        return ""
    href = _source_href(document, entity, graph)
    location = _display_source_path(entity.source.path, graph) + (
        f":{entity.source.line}" if entity.source.line else ""
    )
    value = (
        f'<a href="{html.escape(href)}"><code>{html.escape(location)}</code></a>'
        if href
        else f"<code>{html.escape(location)}</code>"
    )
    return '<div class="api-meta-row"><strong>Definition</strong><span>' + value + "</span></div>"


def _signature_card(
    entity: ApiEntity,
    signature: ApiSignature,
    graph: ApiGraph,
    document: Path,
    *,
    anchor: str,
    documentation: bool = True,
) -> str:
    if signature.documentation or signature.source is not None:
        entity = dataclasses.replace(
            entity,
            documentation=signature.documentation or entity.documentation,
            source=signature.source or entity.source,
        )
    spelling = _signature_spelling(entity, signature)
    declaration = _highlight_declaration(
        spelling, entity.language, entity=entity, graph=graph, document_path=document
    )
    properties = list(dict.fromkeys([*entity.properties, *signature.qualifiers]))
    rows = []
    if properties:
        rows.append(
            '<div class="api-meta-row"><strong>Properties</strong><span class="api-badges">'
            + "".join(f"<span>{html.escape(value)}</span>" for value in properties)
            + "</span></div>"
        )
    if entity.source is not None:
        rows.append(_definition_row(entity, graph, document))
    body = _documentation(entity, graph, document) if documentation else ""
    return (
        f'<article class="api-signature-card" id="{html.escape(anchor)}">'
        f'<pre class="api-signature"><code class="language-{html.escape(entity.language)}">{declaration}</code></pre>'
        + "".join(rows)
        + (f'<div class="api-description">{body}</div>' if body else "")
        + _availability(entity, graph, document, _signature_feature_sets(entity, signature))
        + "</article>"
    )


def _signature_feature_sets(entity: ApiEntity, signature: ApiSignature) -> list[str]:
    if signature not in entity.signatures:
        return []
    index = entity.signatures.index(signature)
    if index < len(entity.signature_feature_sets):
        return entity.signature_feature_sets[index]
    return []


def _compact_signature_label(entity: ApiEntity, signature: ApiSignature) -> str:
    if entity.kind == "macro":
        return entity.name
    values = [parameter.type or parameter.name for parameter in signature.parameters]
    return f"{entity.name}({', '.join(values)})"


def _member_anchor_for_signature(entity: ApiEntity, index: int) -> str:
    base = _member_anchor(entity)
    return base if index == 0 else f"{base}-{index + 1}"


# ---------------------------------------------------------------------------
# Page bodies
# ---------------------------------------------------------------------------


def _namespace_page(
    entity: ApiEntity, graph: ApiGraph, document: Path
) -> tuple[str, list[tuple[str, str, int]]]:
    title = f"{_kind_label(entity.kind).title()} {entity.qualified_name}"
    body = [f"<h1>{html.escape(title)}</h1>"]
    if entity.documentation.strip():
        body.append(
            '<div class="api-namespace-doc">' + _documentation(entity, graph, document) + "</div>"
        )
    else:
        body.append(
            '<div class="api-namespace-doc api-namespace-doc-generated">'
            f"<p>The <code>{html.escape(entity.qualified_name)}</code> namespace groups the public API "
            "declared in this scope. The hierarchy below expands nested namespaces through their "
            "public types and function families; members of classes and structs remain documented "
            "on their corresponding type pages.</p>"
            "</div>"
        )
    body.extend(
        [
            '<section id="members" class="api-section">',
            "<h2>Members</h2>",
            _legend(graph),
            '<ul class="api-namespace-tree">',
        ]
    )

    def render_namespace_children(container: ApiEntity) -> str:
        children = [
            graph.entities[value]
            for value in container.children
            if value in graph.entities and graph.entities[value].kind != "macro"
        ]
        children.sort(key=entity_sort_key)
        parts: list[str] = []
        for child in children:
            parts.append('<li><div class="api-namespace-tree-row">')
            parts.append(_kind_badge(child.kind))
            parts.append(
                f'<a href="{html.escape(_entity_href(document, child, graph))}">{html.escape(child.member_label)}</a>'
            )
            parts.append(_language_badge(child))
            parts.append("</div>")
            if child.kind in _CONTAINER_KINDS:
                nested = render_namespace_children(child)
                if nested:
                    parts.append("<ul>" + nested + "</ul>")
            parts.append("</li>")
        return "".join(parts)

    body.append(render_namespace_children(entity))
    body.extend(["</ul>", _availability(entity, graph, document), "</section>"])
    return "".join(body), [("Members", "members", 1)]


def _record_page(
    entity: ApiEntity, graph: ApiGraph, document: Path
) -> tuple[str, list[tuple[str, str, int]]]:
    children = [graph.entities[value] for value in entity.children if value in graph.entities]
    children.sort(key=entity_sort_key)
    body = [
        f'<h1 class="api-entity-title">{html.escape(entity.name)} {_language_badge(entity)}</h1>',
        _defined_in(entity, graph, document),
    ]
    if entity.language in {"c", "cpp", "cuda", "hip"} and entity.kind in {"class", "struct", "union", "enum"}:
        scoped = " class" if entity.kind == "enum" and "scoped" in entity.properties else ""
        bases = f" : {', '.join(entity.bases)}" if entity.bases else ""
        declaration_text = f"{entity.kind}{scoped} {entity.name}{bases}"
        if entity.template:
            declaration_text = f"{entity.template}\n{declaration_text}"
    elif entity.language == "python" and entity.kind in {"class", "protocol"}:
        bases = f"({', '.join(entity.bases)})" if entity.bases else ""
        declaration_text = f"class {entity.name}{bases}"
    elif entity.language == "rust" and entity.kind in {"struct", "enum", "trait"}:
        prefix = "pub " if "pub" in entity.properties else ""
        declaration_text = f"{prefix}{entity.kind} {entity.name}"
    else:
        declaration_text = _entity_declaration(entity)
    declaration = _highlight_declaration(
        declaration_text, entity.language, entity=entity, graph=graph, document_path=document
    )
    body.append(
        '<article class="api-entity-card">'
        f'<pre class="api-signature"><code class="language-{html.escape(entity.language)}">{declaration}</code></pre>'
        + _definition_row(entity, graph, document)
        + '<div class="api-description">'
        + _documentation(entity, graph, document)
        + "</div>"
        + _availability(entity, graph, document)
        + "</article>"
    )

    toc: list[tuple[str, str, int]] = []
    specializations = _specializations(entity, graph)
    if specializations:
        body.append(
            '<section id="specializations" class="api-section"><h2>Specializations</h2>'
            '<div class="api-record-members">'
        )
        toc.append(("Specializations", "specializations", 1))
        for other in specializations:
            # Only the specialization's name is a link, as in every other member row; the
            # highlighted prefix must not contain links of its own, since links cannot nest.
            prefix = _highlight_declaration(
                f"{other.template} {other.kind}".strip(),
                other.language,
                entity=other,
                graph=graph,
                document_path=document,
            )
            href = html.escape(_entity_href(document, other, graph))
            body.append(
                '<div class="api-member-row">'
                + _kind_badge(other.kind)
                + f'<code>{prefix} <a href="{href}">{html.escape(other.name)}</a></code>'
                + (
                    '<div class="api-member-doc">'
                    + _documentation(other, graph, document)
                    + "</div>"
                    if other.documentation.strip()
                    else ""
                )
                + "</div>"
            )
        body.append("</div></section>")

    grouped = {
        "Public Types": [
            child for child in children if child.kind in _TYPE_KINDS or child.kind in {"type_alias"}
        ],
        "Public Functions": [
            child
            for child in children
            if child.kind in _FUNCTION_KINDS and child.kind != "deduction_guide"
        ],
        "Deduction Guides": [child for child in children if child.kind == "deduction_guide"],
        "Public Members": [child for child in children if child.kind in _MEMBER_VALUE_KINDS],
    }
    for heading, values in grouped.items():
        if not values:
            continue
        section_anchor = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
        body.append(
            f'<section id="{section_anchor}" class="api-section"><h2>{html.escape(heading)}</h2>'
        )
        toc.append((heading, section_anchor, 1))
        body.append('<div class="api-record-members">')
        for child in values:
            if child.kind in _FUNCTION_KINDS and child.signatures:
                for index, signature in enumerate(child.signatures):
                    anchor = _member_anchor_for_signature(child, index)
                    label = _compact_signature_label(child, signature)
                    toc.append((label, anchor, 2))
                    body.append(_signature_card(child, signature, graph, document, anchor=anchor))
            elif child.kind in _MEMBER_VALUE_KINDS:
                anchor = _member_anchor(child)
                toc.append((child.name, anchor, 2))
                summary = _member_summary_spelling(child)
                highlighted = _highlight_declaration(
                    summary, child.language, entity=child, graph=graph, document_path=document
                )
                body.append(
                    f'<div class="api-member-row" id="{html.escape(anchor)}">'
                    + _kind_badge(child.kind)
                    + f"<code>{highlighted}</code>"
                    + (
                        '<div class="api-member-doc">'
                        + _documentation(child, graph, document)
                        + "</div>"
                        if child.documentation.strip()
                        else ""
                    )
                    + "</div>"
                )
            else:
                anchor = _member_anchor(child)
                toc.append((child.name, anchor, 2))
                body.append(
                    f'<div class="api-member-row" id="{html.escape(anchor)}">'
                    + _kind_badge(child.kind)
                    + f'<a href="{html.escape(_entity_href(document, child, graph))}">{html.escape(child.name)}</a></div>'
                )
        body.extend(["</div>", "</section>"])
    return "".join(body), toc


def _specializations(entity: ApiEntity, graph: ApiGraph) -> list[ApiEntity]:
    """Written specializations of a primary class template, which are its siblings."""

    if "<" in entity.name or not entity.template:
        return []
    values = [
        other
        for other in graph.entities.values()
        if other.parent == entity.parent
        and other.language == entity.language
        and other.name.startswith(entity.name + "<")
    ]
    return sorted(values, key=lambda other: other.name)


def _function_page(
    entity: ApiEntity, graph: ApiGraph, document: Path
) -> tuple[str, list[tuple[str, str, int]]]:
    body = [
        f'<h1 class="api-entity-title">{html.escape(entity.name)} {_language_badge(entity)}</h1>',
        _defined_in(entity, graph, document),
    ]
    toc: list[tuple[str, str, int]] = []
    signatures = entity.signatures or [ApiSignature()]
    for index, signature in enumerate(signatures):
        anchor = f"overload-{index + 1}"
        label = _compact_signature_label(entity, signature)
        toc.append((label, anchor, 1))
        body.append(_signature_card(entity, signature, graph, document, anchor=anchor))
    return "".join(body), toc


def _enum_page(
    entity: ApiEntity, graph: ApiGraph, document: Path
) -> tuple[str, list[tuple[str, str, int]]]:
    return _record_page(entity, graph, document)


def _simple_entity_page(
    entity: ApiEntity, graph: ApiGraph, document: Path
) -> tuple[str, list[tuple[str, str, int]]]:
    body = [
        f'<h1 class="api-entity-title">{html.escape(entity.name)} {_language_badge(entity)}</h1>',
        _defined_in(entity, graph, document),
    ]
    if entity.signatures:
        for index, signature in enumerate(entity.signatures):
            body.append(
                _signature_card(entity, signature, graph, document, anchor=f"signature-{index + 1}")
            )
    else:
        declaration = _highlight_declaration(
            _entity_declaration(entity),
            entity.language,
            entity=entity,
            graph=graph,
            document_path=document,
        )
        body.append(
            '<article class="api-entity-card">'
            f'<pre class="api-signature"><code class="language-{html.escape(entity.language)}">{declaration}</code></pre>'
            + _definition_row(entity, graph, document)
            + '<div class="api-description">'
            + _documentation(entity, graph, document)
            + "</div>"
            + _availability(entity, graph, document)
            + "</article>"
        )
    return "".join(body), []


def _entity_page(
    entity: ApiEntity, graph: ApiGraph, document: Path
) -> tuple[str, list[tuple[str, str, int]]]:
    if entity.kind in _CONTAINER_KINDS:
        return _namespace_page(entity, graph, document)
    if entity.kind in _CLASS_LIKE_KINDS or entity.kind == "enum":
        return _record_page(entity, graph, document)
    if entity.kind in _FUNCTION_KINDS:
        return _function_page(entity, graph, document)
    return _simple_entity_page(entity, graph, document)


def _hierarchy_entity(entity: ApiEntity, graph: ApiGraph, document: Path) -> str:
    children = _visible_outline_children(entity, graph)
    parts = [
        "<li>",
        _kind_badge(entity.kind),
        f'<a href="{html.escape(_entity_href(document, entity, graph))}">{html.escape(entity.member_label)}</a>',
        _language_badge(entity),
    ]
    if children:
        parts.append("<ul>")
        parts.extend(_hierarchy_entity(child, graph, document) for child in children)
        parts.append("</ul>")
    parts.append("</li>")
    return "".join(parts)


def _file_tree(graph: ApiGraph) -> dict[str, object]:
    root: dict[str, object] = {}
    for source in sorted(set(graph.sources) | set(graph.files)):
        node = root
        display_source = _display_source_path(source, graph)
        parts = PurePosixPath(display_source).parts
        for part in parts[:-1]:
            node = node.setdefault(part, {})  # type: ignore[assignment]
        node.setdefault("__files__", []).append((parts[-1], source))  # type: ignore[union-attr]
    return root


def _file_tree_html(node: dict[str, object], document: Path) -> str:
    parts = ['<ul class="api-file-tree">']
    files = node.get("__files__", [])
    if isinstance(files, list):
        for filename, source_path in sorted(files, key=lambda item: str(item[0]).casefold()):
            parts.append(
                '<li><span class="api-kind file-kind" title="file">F</span>'
                f'<a href="{html.escape(_page_href(document, _source_document(str(source_path))))}">{html.escape(str(filename))}</a></li>'
            )
    for name, child in sorted(node.items()):
        if name == "__files__" or not isinstance(child, dict):
            continue
        parts.append(
            f'<li><span class="api-kind file-kind" title="directory">D</span>'
            f"<span>{html.escape(name)}</span>"
        )
        parts.append(_file_tree_html(child, document))
        parts.append("</li>")
    parts.append("</ul>")
    return "".join(parts)


_HTML_COMMENT = re.compile(r"<!--.*?-->[ \t]*\n?", re.DOTALL)


def _render_markdown(text: str, graph: ApiGraph) -> str:
    """Render human-authored Markdown used by the standalone API site.

    Raw HTML is not rendered, so HTML comments such as the SPDX header of the introduction file
    are removed instead of being shown as text.
    """

    substituted = (
        _HTML_COMMENT.sub("", text)
        .replace("{{ project }}", graph.project)
        .replace("{{ version }}", graph.version)
        .replace("{{ language }}", graph.language)
    )
    return _MARKDOWN.render(substituted)


def _home_page(
    graph: ApiGraph,
    document: Path,
    project_docs_url: str,
    *,
    introduction: str | None = None,
) -> tuple[str, list[tuple[str, str, int]]]:
    del project_docs_url
    roots = [entity for entity in graph.roots() if entity.kind != "macro"]
    macros = sorted(
        (entity for entity in graph.entities.values() if entity.kind == "macro"),
        key=entity_sort_key,
    )
    if introduction is None:
        introduction = (
            "# API Documentation Home\n\n"
            "This site is the generated API reference for this version of `{{ project }}`. "
            "For tutorials, how-to guides, explanations, and general project information, see the "
            "[main project documentation](projectdocs:).\n\n"
            "cpdocs extracts semantic declarations into a language-neutral API graph and renders this "
            "versioned reference directly as a code-oriented site.\n\n"
            "The [feature sets](feature-sets/) page shows the concrete project configurations "
            "whose APIs were merged into this reference.\n"
        )
    body = [
        _render_markdown(introduction, graph),
        '<section id="api-hierarchy" class="api-section"><h2>API hierarchy</h2>',
        _legend(graph),
        '<ul class="api-hierarchy">',
    ]
    body.extend(_hierarchy_entity(entity, graph, document) for entity in roots)
    if macros:
        body.append("<li><strong>Macros</strong><ul>")
        for macro in macros:
            body.append(
                "<li>"
                + _kind_badge("macro")
                + f'<a href="{html.escape(_entity_href(document, macro, graph))}">{html.escape(macro.name)}</a></li>'
            )
        body.append("</ul></li>")
    body.extend(
        [
            "</ul></section>",
            '<section id="file-hierarchy" class="api-section"><h2>File Hierarchy</h2>',
            _file_tree_html(_file_tree(graph), document),
            "</section>",
        ]
    )
    return "".join(body), [
        ("API hierarchy", "api-hierarchy", 1),
        ("File Hierarchy", "file-hierarchy", 1),
    ]


def _feature_sets_page(graph: ApiGraph, document: Path) -> tuple[str, list[tuple[str, str, int]]]:
    del document
    units = graph.metadata.get("units", [])
    if not isinstance(units, list):
        units = []
    unit_text = " · ".join(
        f"<code>{html.escape(str(unit.get('id')))}</code> ({html.escape(_language_label(str(unit.get('language'))))})"
        for unit in units
        if isinstance(unit, dict)
    )
    body = [
        "<h1>Feature Sets</h1>",
        "<p>The project's build system enumerates concrete feature sets. cpdocs builds each set "
        "independently. Feature sets have no names: each row below is simply the list of project "
        "features enabled for that build.</p>",
        '<section id="overview" class="api-section"><h2>Overview</h2>',
        "<table><tbody>",
        f"<tr><th>Project</th><td><code>{html.escape(graph.project)}</code></td></tr>",
        f"<tr><th>Feature sets</th><td>{len(graph.feature_sets)}</td></tr>",
    ]
    if unit_text:
        body.append(f"<tr><th>Units</th><td>{unit_text}</td></tr>")
    generator = graph.metadata.get("generator")
    if generator:
        body.append(f"<tr><th>Described by</th><td>{html.escape(str(generator))}</td></tr>")
    body.extend(
        [
            "</tbody></table></section>",
            '<section id="feature-sets" class="api-section"><h2>Feature Sets</h2>',
            '<table class="api-feature-set-table">',
            '<thead><tr><th>Feature set</th><th>Enabled features</th></tr></thead>',
            '<tbody>',
        ]
    )
    toc: list[tuple[str, str, int]] = [("Overview", "overview", 1), ("Feature Sets", "feature-sets", 1)]
    for index, key in enumerate(graph.feature_sets, 1):
        anchor = _feature_set_anchor(key)
        body.append(
            f'<tr id="{html.escape(anchor)}">'
            f'<th scope="row">{index}</th>'
            '<td>'
            + _feature_set_inline(graph, key)
            + '</td></tr>'
        )
    body.append("</tbody></table></section>")
    return "".join(body), toc


def _macros_page(graph: ApiGraph, document: Path) -> tuple[str, list[tuple[str, str, int]]]:
    macros = sorted(
        (entity for entity in graph.entities.values() if entity.kind == "macro"),
        key=entity_sort_key,
    )
    body = ['<h1>Macros</h1><ul class="api-member-list">']
    for macro in macros:
        body.append(
            "<li>"
            + _kind_badge("macro")
            + f'<a href="{html.escape(_entity_href(document, macro, graph))}">{html.escape(macro.name)}</a></li>'
        )
    body.append("</ul>")
    return "".join(body), []


def _source_page(
    source_path: str, content: str, document: Path, graph: ApiGraph
) -> tuple[str, list[tuple[str, str, int]]]:
    language = _source_language(source_path)
    if language == "cpp":
        # Some generated headers align macro-continuation backslashes with large runs of spaces.
        # That is useful in raw source but produces visually detached backslashes in the browser.
        # Preserve the source semantics while normalizing only the rendered representation.
        content = "\n".join(
            re.sub(r"[ \t]+\\[ \t]*$", r" \\", line.rstrip()) for line in content.splitlines()
        ) + ("\n" if content.endswith("\n") else "")
    highlighted = _highlight_source_lines(content, language)
    display_path = _display_source_path(source_path, graph)
    generated_sources = graph.metadata.get("generated_sources", [])
    generated_files = graph.metadata.get("generated_files", [])
    generated = (
        (isinstance(generated_sources, list) and source_path in generated_sources)
        or (isinstance(generated_files, list) and source_path in generated_files)
    )
    note = (
        '<p class="api-section-intro">Generated by the build; not part of the repository.</p>'
        if generated
        else ""
    )
    lines = [
        f"<h1>File: {html.escape(display_path)}</h1>" + note,
        f'<pre class="api-source"><code class="language-{html.escape(language)}">',
    ]
    for number, value in enumerate(highlighted, 1):
        lines.append(
            f'<span class="source-line" id="L{number}"><a class="source-number" href="#L{number}">{number}</a><span class="source-code">{value}</span></span>'
        )
    lines.extend(["</code></pre>"])
    return "".join(lines), []


# ---------------------------------------------------------------------------
# Complete layout and assets
# ---------------------------------------------------------------------------


def _page_title(entity: ApiEntity | None, graph: ApiGraph, special: str) -> str:
    if entity is not None:
        return f"{entity.name} — {graph.project} API documentation"
    if special == "feature_sets":
        return f"Feature Sets — {graph.project} API documentation"
    if special == "macros":
        return f"Macros — {graph.project} API documentation"
    return f"{graph.project} API documentation"


def _project_docs_href(document: Path, project_docs_url: str) -> str:
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", project_docs_url) or project_docs_url.startswith(
        "/"
    ):
        return project_docs_url
    root = _root_relative(document, ".")
    if root == ".":
        root = ""
    elif not root.endswith("/"):
        root += "/"
    return posixpath.normpath(root + project_docs_url).rstrip("/") + "/"


def _layout(
    *,
    graph: ApiGraph,
    document: Path,
    body: str,
    toc: list[tuple[str, str, int]],
    current: ApiEntity | None,
    special: str,
    project_docs_url: str,
    copyright_text: str,
) -> str:
    body = _resolve_projectdocs_links(body, document, project_docs_url)
    # The version query changes whenever the asset does, so a browser never pairs new pages with a
    # stylesheet or script it cached from an older cpdocs.
    stylesheet = _root_relative(document, "assets/cpdocs-api.css") + f"?v={_asset_version('css')}"
    script = _root_relative(document, "assets/cpdocs-api.js") + f"?v={_asset_version('js')}"
    home = _page_href(document, Path("index.md"))
    project_docs = _project_docs_href(document, project_docs_url)
    version_root = _root_relative(document, ".")
    if version_root == ".":
        version_root = "./"
    elif not version_root.endswith("/"):
        version_root += "/"
    api_root = posixpath.normpath(version_root + "../").rstrip("/") + "/"
    current_route = _output_directory(document).as_posix().strip(".")
    if current_route and not current_route.endswith("/"):
        current_route += "/"
    return f'''<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<script>document.documentElement.classList.add("js");try{{for(const k of ["sidebar","toc"]){{const v=localStorage.getItem("cpdocs-api-"+k+"-width");if(v)document.documentElement.style.setProperty("--api-"+k+"-width",v+"px")}}}}catch(e){{}}try{{const t=localStorage.getItem("cpdocs-api-theme");document.documentElement.dataset.theme=t==="dark"||t==="light"?t:(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light")}}catch(e){{}}</script>
<title>{html.escape(_page_title(current, graph, special))}</title>
<link rel="stylesheet" href="{html.escape(stylesheet)}">
</head>
<body data-version-root="{html.escape(version_root)}" data-api-root="{html.escape(api_root)}" data-current-route="{html.escape(current_route)}">
<header class="api-topbar">
  <a class="api-brand" href="{html.escape(home)}">{html.escape(graph.project)} API documentation</a>
  <div class="api-topbar-actions">
    <div class="api-search"><span aria-hidden="true">⌕</span><input type="search" placeholder="Search" aria-label="Search API"><div class="api-search-results" hidden></div></div>
    <a class="api-project-docs" href="{html.escape(project_docs)}" title="Project documentation"><span aria-hidden="true">←</span><span class="api-long"> Project documentation</span><span class="api-short"> Docs</span></a>
    <select class="api-version" aria-label="API version"><option>{html.escape(graph.version)}</option></select>
    <button class="api-theme" type="button" aria-label="Toggle color theme">◐</button>
  </div>
</header>
<div class="api-shell">
  <aside class="api-sidebar">{_outline(graph, document, current, current_special=special)}</aside>
  <main class="api-main">{body}</main>
  {_toc(toc)}
  <div class="api-resizer api-resizer-sidebar" data-resize="sidebar" role="separator" aria-orientation="vertical" aria-label="Resize the outline" title="Drag to resize, double-click to reset" tabindex="0"></div>
  <div class="api-resizer api-resizer-toc" data-resize="toc" role="separator" aria-orientation="vertical" aria-label="Resize the page contents" title="Drag to resize, double-click to reset" tabindex="0"></div>
</div>
<footer class="api-footer"><span>{html.escape(copyright_text)}</span><span>Generated by cpdocs.</span></footer>
<script src="{html.escape(script)}"></script>
</body>
</html>
'''


_CSS = r"""
:root {
  --api-accent: #2f62b5;
  --api-accent-2: #168b98;
  --api-bg: #ffffff;
  --api-fg: #20242a;
  --api-muted: #66707c;
  --api-border: #d8dde3;
  --api-soft: #f5f6f8;
  --api-selected: #eef1fb;
  --api-code: ui-monospace, "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  --api-ui: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --api-tree-indent: 2.45rem;
}
html[data-theme="dark"] {
  --api-accent: #83b7ff;
  --api-accent-2: #68d3dd;
  --api-bg: #17191c;
  --api-fg: #e8eaf0;
  --api-muted: #a9b1bc;
  --api-border: #3b4048;
  --api-soft: #22262b;
  --api-selected: #29334a;
}
* { box-sizing: border-box; }
html, body { margin: 0; min-height: 100%; background: var(--api-bg); color: var(--api-fg); font-family: var(--api-ui); }
a { color: var(--api-accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code, pre { font-family: var(--api-code); }
.api-topbar { height: 3rem; position: sticky; top: 0; z-index: 20; display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 0 .9rem; border-bottom: 1px solid var(--api-border); background: var(--api-bg); }
.api-brand { color: var(--api-fg); font-weight: 650; white-space: nowrap; }
.api-topbar-actions { display: flex; align-items: center; gap: .7rem; margin-left: auto; }
.api-search { position: relative; display: flex; align-items: center; gap: .4rem; border: 1px solid var(--api-border); border-radius: .4rem; padding: .25rem .55rem; min-width: 12rem; }
.api-search input { border: 0; outline: 0; background: transparent; color: var(--api-fg); width: 100%; }
.api-search-results { position: absolute; top: calc(100% + .3rem); right: 0; width: 26rem; max-height: 24rem; overflow: auto; background: var(--api-bg); border: 1px solid var(--api-border); border-radius: .35rem; box-shadow: 0 .4rem 1rem #0002; padding: .25rem; }
.api-search-results a { display: block; padding: .35rem .45rem; border-radius: .25rem; }
.api-search-results a:hover { background: var(--api-soft); text-decoration: none; }
.api-project-docs .api-short { display: none; }
.api-outline-panel-toggle { display: none; }
.api-version { min-width: 6.5rem; }
.api-feature-axis th { padding-top: .8rem; color: var(--api-muted); font-weight: 650; text-align: left; }
tbody th[scope="row"] { font-weight: 400; text-align: left; }
.api-doc-field { margin-top: .9rem; }
.api-description .api-doc-field-title { margin: 0 0 .35rem; color: var(--api-muted); font-size: .78rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
.api-doc-field dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: .3rem 1.1rem; margin: 0; }
.api-doc-field dt { margin: 0; font-weight: 700; }
.api-doc-field dt code { color: var(--api-accent); }
.api-doc-field dd { margin: 0; }
.api-doc-field > p:not(.api-doc-field-title) { margin: 0; }
.api-feature-set-tag { margin-left: .45rem; padding: .02rem .38rem; border: 1px solid var(--api-border); border-radius: .7rem; color: var(--api-muted); font-size: .72rem; white-space: nowrap; }
.api-project-docs { color: #fff; background: var(--api-accent); border-radius: .25rem; padding: .38rem .65rem; font-weight: 650; white-space: nowrap; }
.api-version, .api-theme { height: 2rem; border: 1px solid var(--api-border); border-radius: .3rem; background: var(--api-bg); color: var(--api-fg); }
.api-theme { width: 2rem; cursor: pointer; }
:root { --api-sidebar-default: 20.5rem; --api-toc-default: 24rem; }
.api-shell { position: relative; display: grid; grid-template-columns: var(--api-sidebar-width, var(--api-sidebar-default)) minmax(0, 1fr) var(--api-toc-width, var(--api-toc-default)); min-height: calc(100vh - 5rem); }
.api-resizer { position: absolute; top: 0; bottom: 0; z-index: 15; width: 9px; cursor: col-resize; touch-action: none; outline: none; }
.api-resizer::after { content: ""; position: absolute; top: 0; bottom: 0; left: 3px; width: 3px; background: transparent; transition: background .12s; }
.api-resizer:hover::after, .api-resizer:focus-visible::after, .is-resizing .api-resizer::after { background: var(--api-accent); }
.api-resizer-sidebar { left: calc(var(--api-sidebar-width, var(--api-sidebar-default)) - 5px); }
.api-resizer-toc { right: calc(var(--api-toc-width, var(--api-toc-default)) - 5px); }
html.is-resizing, html.is-resizing * { cursor: col-resize !important; user-select: none; }
.api-sidebar, .api-toc { position: sticky; top: 3rem; align-self: start; height: calc(100vh - 3rem); overflow: auto; padding: 1.15rem .8rem 2rem; }
.api-sidebar { border-right: 1px solid var(--api-border); }
.api-toc { border-left: 1px solid var(--api-border); }
.api-main { width: min(80%, 80rem); min-width: 0; justify-self: center; padding: 1.45rem 0 4rem; }
.api-main h1 { font-size: 1.75rem; line-height: 1.15; border-bottom: 2px solid var(--api-accent); padding-bottom: .25rem; margin: 0 0 .65rem; }
.api-main h2 { font-size: 1.28rem; line-height: 1.2; border-left: .28rem solid var(--api-accent-2); padding-left: .55rem; margin: 1.2rem 0 .55rem; }
.api-main h3 { font-size: 1.04rem; margin: .85rem 0 .35rem; }
.api-main p, .api-main li, .api-main td, .api-main th { line-height: 1.34; }
.api-main p { margin: .4rem 0; }
.api-defined { margin: -.1rem 0 .75rem !important; }
.api-sidebar h2, .api-toc h2 { font-size: 1.18rem; margin: .15rem 0 .65rem; }
.api-outline-root, .api-outline-children { list-style: none; margin: 0; padding: 0; }
.api-outline-root > li { margin: 0; }
.api-outline-row { display: grid; grid-template-columns: 1.45rem minmax(0, 1fr) auto auto; column-gap: .68rem; align-items: center; width: 100%; min-width: 0; min-height: 1.72rem; overflow: hidden; }
.api-outline-row.is-current { background: var(--api-selected); border-radius: .25rem; padding-right: .18rem; }
.api-outline-link { min-width: 0; overflow: hidden; text-overflow: ellipsis; color: var(--api-fg); padding: .1rem 0; white-space: nowrap; }
.api-outline-language { min-width: 0; justify-self: end; overflow: hidden; }
.api-outline-language:empty { display: none; }
.api-outline-language .api-language-badge { max-width: 100%; overflow: hidden; text-overflow: ellipsis; }
.api-outline-row.is-current .api-outline-link { color: var(--api-accent); font-weight: 650; }
.api-outline-root > li > .api-outline-row .api-outline-link { font-weight: 500; }
.api-outline-root > li > .api-outline-row .api-outline-link[href*="api/"] { font-weight: 700; }
.api-outline-children { margin: .08rem 0 .12rem var(--api-tree-indent); padding-left: 1.15rem; }
.api-outline-children > li { position: relative; }
.api-outline-children > li::before { content: ""; position: absolute; left: -1.15rem; top: -.08rem; bottom: -.12rem; border-left: 1px solid var(--api-border); }
.api-outline-children > li::after { content: ""; position: absolute; left: -1.15rem; top: .85rem; width: 1rem; border-top: 1px solid var(--api-border); }
.api-outline-children > li:last-child::before { bottom: auto; height: .94rem; }
.api-kind { display: inline-grid; place-items: center; min-width: 1.42rem; height: 1.25rem; padding: 0 .22rem; border: 1px solid var(--api-border); border-radius: .23rem; color: var(--api-muted); font-family: var(--api-code); font-size: .68rem; line-height: 1; font-weight: 950; }
.api-kind-empty { border-color: transparent; }
.api-outline-toggle { position: relative; width: 1.4rem; height: 1.4rem; border: 1px solid var(--api-border); border-radius: .25rem; background: transparent; color: var(--api-muted); font: 800 1rem/1 var(--api-code); cursor: pointer; }
.api-outline-toggle::before { content: "+"; position: absolute; inset: 0; display: grid; place-items: center; }
.api-outline-toggle[aria-expanded="true"]::before { content: "−"; }
.api-outline-toggle:hover { color: var(--api-accent); border-color: var(--api-accent); }
.api-outline-children[hidden] { display: none; }
.api-toc ul { list-style: none; padding: 0; margin: 0; }
.api-toc li { margin: .34rem 0; }
.api-toc .toc-level-2 { padding-left: .85rem; font-size: .9rem; }
.api-toc a { color: var(--api-muted); }
.api-toc a:hover { color: var(--api-accent); }
.api-section { margin-top: 1rem; }
.api-legend { display: flex; flex-wrap: wrap; align-items: center; gap: .28rem; margin: .25rem 0 .55rem; font-size: .83rem; }
.api-legend-entry { display: inline-flex; align-items: center; gap: .28rem; }
.api-legend-separator { color: var(--api-muted); }
.api-member-list, .api-hierarchy, .api-hierarchy ul, .api-file-tree { list-style: none; margin: .25rem 0; padding-left: 1.25rem; }
.api-member-list { padding-left: 0; }
.api-member-list li { display: flex; align-items: center; gap: .55rem; padding: .24rem 0; border-bottom: 1px solid var(--api-border); }
.api-namespace-tree, .api-namespace-tree ul { list-style: none; margin: .2rem 0; padding-left: 0; }
.api-namespace-tree ul { margin-left: 2.35rem; padding-left: 1.05rem; border-left: 1px solid var(--api-border); }
.api-namespace-tree li { margin: 0; }
.api-namespace-tree-row { display: flex; align-items: center; gap: .52rem; min-height: 1.72rem; border-bottom: 1px solid var(--api-border); }
.api-namespace-tree ul > li > .api-namespace-tree-row { position: relative; }
.api-namespace-tree ul > li > .api-namespace-tree-row::before { content: ""; position: absolute; left: -1.05rem; width: .8rem; border-top: 1px solid var(--api-border); }
.api-hierarchy li, .api-file-tree li { margin: .18rem 0; }
/* Give the in-page API and file hierarchies the same tree connectors as the primary outline. */
.api-hierarchy ul,
.api-file-tree .api-file-tree {
  margin-left: .35rem;
  padding-left: 1.15rem;
}
.api-hierarchy ul > li,
.api-file-tree .api-file-tree > li {
  position: relative;
}
.api-hierarchy ul > li::before,
.api-file-tree .api-file-tree > li::before {
  border-left: 1px solid var(--api-border);
  bottom: -.18rem;
  content: "";
  left: -1.15rem;
  position: absolute;
  top: -.18rem;
}
.api-hierarchy ul > li::after,
.api-file-tree .api-file-tree > li::after {
  border-top: 1px solid var(--api-border);
  content: "";
  left: -1.15rem;
  position: absolute;
  top: .72rem;
  width: .9rem;
}
.api-hierarchy ul > li:last-child::before,
.api-file-tree .api-file-tree > li:last-child::before {
  bottom: auto;
  height: .9rem;
}
.api-hierarchy .api-kind { margin-right: .35rem; }
.api-file-tree .api-kind { margin-right: .35rem; }
.api-entity-card, .api-signature-card { border: 1px solid var(--api-border); border-top: .22rem solid var(--api-accent); border-radius: .45rem; padding: .7rem .85rem .8rem; margin: .55rem 0 .9rem; }
.api-signature { margin: 0; padding: 0 0 .55rem; background: transparent; border-bottom: 1px solid var(--api-border); overflow-x: auto; font-size: .87rem; line-height: 1.35; font-weight: 650; }
.api-signature code { padding: 0; }
.api-signature-name { font-weight: 800; }
.api-meta-row { display: flex; align-items: baseline; gap: .65rem; margin-top: .42rem; font-size: .78rem; }
.api-meta-row > strong { flex: 0 0 5rem; }
.api-badges { display: flex; flex-wrap: wrap; gap: .3rem; }
.api-badges > span { border: 1px solid color-mix(in srgb, var(--api-accent) 32%, var(--api-border)); border-radius: 999px; background: color-mix(in srgb, var(--api-accent) 8%, transparent); padding: .08rem .36rem; font: 650 .72rem var(--api-code); }
.api-language-badge { display: inline-flex; align-items: center; border: 1px solid color-mix(in srgb, var(--api-accent) 32%, var(--api-border)); border-radius: 999px; background: color-mix(in srgb, var(--api-accent) 8%, transparent); padding: .08rem .38rem; font: 650 .68rem var(--api-code); white-space: nowrap; vertical-align: middle; }
.api-entity-title .api-language-badge { margin-left: .35rem; transform: translateY(-.08rem); }
.api-description { border-top: 1px solid var(--api-border); margin-top: .55rem; padding-top: .45rem; }
.api-related { margin-top: .45rem !important; }
.api-availability { border-top: 1px solid var(--api-border); margin-top: .55rem; padding-top: .48rem; font-size: .82rem; }
.api-availability-list, .api-feature-set-list { margin: .35rem 0 0; padding-left: 1.25rem; }
.api-availability-list li, .api-feature-set-row { margin: .2rem 0; }
.api-availability-list a { text-decoration: none; }
.api-feature-set-empty { color: var(--api-muted); font-style: italic; }
.api-record-members { border-top: 1px solid var(--api-border); }
.api-member-row { display: grid; grid-template-columns: 1.5rem minmax(0, 1fr); align-items: baseline; gap: .55rem; border-bottom: 1px solid var(--api-border); padding: .34rem .08rem; }
.api-member-row code { font-weight: 600; }
.api-member-doc { grid-column: 2; color: var(--api-muted); }
.api-namespace-doc { margin: .4rem 0 .8rem; }
table { width: 100%; border-collapse: collapse; margin: .4rem 0 .8rem; }
th, td { text-align: left; padding: .45rem .55rem; border-bottom: 1px solid var(--api-border); }
thead th { border-bottom: 2px solid var(--api-accent); }
tbody tr:nth-child(odd) { background: var(--api-soft); }
.table-scroll { overflow-x: auto; }
.api-section-intro { color: var(--api-muted); max-width: 70rem; }
.api-feature-set-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr)); gap: .75rem; margin: .7rem 0 1rem; }
.api-feature-set-card { border: 1px solid var(--api-border); border-top: .2rem solid var(--api-accent-2); border-radius: .45rem; background: color-mix(in srgb, var(--api-soft) 55%, transparent); overflow: hidden; }
.api-feature-set-card header { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; padding: .62rem .75rem .5rem; border-bottom: 1px solid var(--api-border); }
.api-feature-set-card h3 { margin: 0; font-size: 1rem; }
.api-feature-set-card-label { color: var(--api-muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; }
.api-feature-set-card dl { margin: 0; padding: .2rem .75rem .65rem; }
.api-feature-set-card dl > div { padding: .45rem 0; }
.api-feature-set-card dl > div + div { border-top: 1px solid var(--api-border); }
.api-feature-set-card dt { font-size: .76rem; font-weight: 700; color: var(--api-muted); margin-bottom: .22rem; }
.api-feature-set-card dd { margin: 0; display: flex; flex-wrap: wrap; gap: .28rem; }
.api-chip { display: inline-block; border: 1px solid var(--api-border); border-radius: .25rem; background: var(--api-bg); padding: .08rem .32rem; }
.api-none { color: var(--api-muted); font-style: italic; }
.api-source { background: var(--api-soft); border: 1px solid var(--api-border); border-radius: .4rem; padding: .75rem 0; overflow: auto; font-size: .82rem; line-height: 1.35; }
.source-line { display: grid; grid-template-columns: 4.2rem minmax(max-content, 1fr); min-height: 1.1rem; }
.source-line:target { background: color-mix(in srgb, var(--api-accent) 12%, transparent); }
.source-number { user-select: none; text-align: right; padding-right: 1rem; color: var(--api-muted); }
.source-code { white-space: pre; padding-right: 1rem; }
.cpdocs-syntax-keyword { color: #005cc5; font-weight: 650; }
.cpdocs-syntax-comment { color: #6a737d; font-style: italic; }
.cpdocs-syntax-string { color: #032f62; }
.cpdocs-syntax-number { color: #005cc5; }
.cpdocs-syntax-preprocessor { color: #6f42c1; }
html[data-theme="dark"] .cpdocs-syntax-keyword { color: #79b8ff; }
html[data-theme="dark"] .cpdocs-syntax-comment { color: #8b949e; }
html[data-theme="dark"] .cpdocs-syntax-string { color: #9ecbff; }
html[data-theme="dark"] .cpdocs-syntax-number { color: #79b8ff; }
html[data-theme="dark"] .cpdocs-syntax-preprocessor { color: #d2a8ff; }
.api-footer { min-height: 2rem; display: flex; align-items: center; justify-content: space-between; gap: 1rem; border-top: 1px solid var(--api-border); padding: .45rem 1rem; font-size: .72rem; color: var(--api-muted); }
@media (max-width: 1400px) { :root { --api-sidebar-default: 19rem; --api-toc-default: 20rem; } .api-main { width: 88%; } }
@media (max-width: 1100px) { :root { --api-sidebar-default: 18rem; } .api-shell { grid-template-columns: var(--api-sidebar-width, var(--api-sidebar-default)) minmax(0, 1fr); } .api-toc, .api-resizer-toc { display: none; } .api-main { width: 92%; } }
@media (max-width: 760px) { .api-shell { display: block; } .api-resizer { display: none; } .api-sidebar { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--api-border); } .api-topbar-actions { gap: .35rem; } .api-search { min-width: 7rem; } .api-project-docs { padding: .38rem .5rem; } .api-project-docs .api-long { display: none; } .api-project-docs .api-short { display: inline; } .api-topbar { height: auto; min-height: 3rem; flex-wrap: wrap; row-gap: .4rem; padding: .45rem .9rem; } .api-brand { white-space: normal; } .api-main { width: auto; padding: 1rem; } .api-sidebar { padding: .5rem .8rem; } .api-sidebar h2 { display: none; } .api-outline-panel-toggle { display: flex; align-items: center; gap: .6rem; width: 100%; min-height: 2.4rem; padding: .35rem .6rem; border: 1px solid var(--api-border); border-radius: .35rem; background: var(--api-soft); color: var(--api-fg); font: inherit; font-weight: 650; cursor: pointer; text-align: left; } .api-outline-panel-toggle::after { content: "▾"; margin-left: auto; transition: transform .15s; } .api-outline-panel-toggle[aria-expanded="true"]::after { transform: rotate(180deg); } .api-outline-current { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--api-muted); font-weight: 500; } .js .api-sidebar:not(.is-open) .api-outline-root { display: none; } .api-sidebar.is-open .api-outline-root { max-height: 60vh; overflow: auto; margin-top: .5rem; } }
"""


_JS = r"""
(() => {
  const root = document.documentElement;

  // Keep the sidebar where the reader left it; a full page load otherwise jumps it to the top.
  const sidebar = document.querySelector(".api-sidebar");
  const panelToggle = document.querySelector(".api-outline-panel-toggle");
  panelToggle?.addEventListener("click", () => {
    const open = sidebar?.classList.toggle("is-open") ?? false;
    panelToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) sidebar?.querySelector(".is-current")?.scrollIntoView({block: "nearest"});
  });
  if (sidebar) {
    try {
      const saved = sessionStorage.getItem("cpdocs-api-sidebar");
      if (saved !== null) sidebar.scrollTop = Number(saved);
    } catch {}
    const currentRow = sidebar.querySelector(".is-current");
    if (currentRow) {
      const box = sidebar.getBoundingClientRect();
      const row = currentRow.getBoundingClientRect();
      if (row.top < box.top || row.bottom > box.bottom) currentRow.scrollIntoView({block: "center"});
    }
    addEventListener("pagehide", () => {
      try { sessionStorage.setItem("cpdocs-api-sidebar", String(sidebar.scrollTop)); } catch {}
    });
  }

  document.querySelector(".api-theme")?.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    localStorage.setItem("cpdocs-api-theme", next);
  });

  // Drag the border of the outline or of the page contents to resize it; the width is kept for
  // later visits. Arrow keys resize a focused handle, double-click restores the default.
  for (const handle of document.querySelectorAll(".api-resizer")) {
    const side = handle.dataset.resize;
    const panel = document.querySelector(side === "sidebar" ? ".api-sidebar" : ".api-toc");
    const shell = handle.closest(".api-shell");
    if (!panel || !shell) continue;
    const property = `--api-${side}-width`;
    const key = `cpdocs-api-${side}-width`;
    const clamp = value => Math.round(Math.min(Math.max(value, 160), window.innerWidth * 0.45));
    const apply = width => root.style.setProperty(property, `${width}px`);
    const save = () => {
      try { localStorage.setItem(key, String(Math.round(panel.getBoundingClientRect().width))); } catch {}
    };
    handle.addEventListener("pointerdown", event => {
      if (event.button !== 0) return;
      event.preventDefault();
      handle.setPointerCapture(event.pointerId);
      root.classList.add("is-resizing");
      const box = shell.getBoundingClientRect();
      const move = moving => apply(clamp(side === "sidebar" ? moving.clientX - box.left : box.right - moving.clientX));
      const stop = () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", stop);
        handle.removeEventListener("pointercancel", stop);
        root.classList.remove("is-resizing");
        save();
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", stop);
      handle.addEventListener("pointercancel", stop);
    });
    handle.addEventListener("keydown", event => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const step = (event.shiftKey ? 64 : 16) * (event.key === "ArrowRight" ? 1 : -1);
      apply(clamp(panel.getBoundingClientRect().width + (side === "sidebar" ? step : -step)));
      save();
    });
    handle.addEventListener("dblclick", () => {
      root.style.removeProperty(property);
      try { localStorage.removeItem(key); } catch {}
    });
  }

  for (const button of document.querySelectorAll(".api-outline-toggle")) {
    const row = button.closest(".api-outline-row");
    const children = row?.nextElementSibling;
    if (!children?.classList.contains("api-outline-children")) continue;
    button.addEventListener("click", () => {
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", expanded ? "false" : "true");
      children.hidden = expanded;
    });
  }

  const version = document.querySelector(".api-version");
  const apiRoot = document.body.dataset.apiRoot || "../";
  const route = document.body.dataset.currentRoute || "";
  if (version) {
    fetch(apiRoot + "versions.json")
      .then(response => response.ok ? response.json() : null)
      .then(data => {
        if (!data?.versions) return;
        version.replaceChildren();
        for (const item of data.versions) {
          const option = document.createElement("option");
          option.value = item.name;
          option.textContent = item.name;
          option.selected = item.name === document.querySelector(".api-version")?.dataset.current;
          version.appendChild(option);
        }
        const current = location.pathname.split("/").filter(Boolean).at(-1);
        for (const option of version.options) {
          if (location.pathname.includes(`/${option.value}/`)) option.selected = true;
        }
        version.addEventListener("change", () => {
          location.href = apiRoot + version.value + "/" + route;
        });
      }).catch(() => {});
  }

  const search = document.querySelector(".api-search input");
  const results = document.querySelector(".api-search-results");
  const versionRoot = document.body.dataset.versionRoot || "./";
  let index = null;
  function showResults(values) {
    if (!results) return;
    results.replaceChildren();
    for (const item of values.slice(0, 20)) {
      const link = document.createElement("a");
      link.href = versionRoot + item.url;
      link.innerHTML = `<strong>${item.label}</strong><br><small>${item.kind} · ${item.qualified}</small>`;
      results.appendChild(link);
    }
    results.hidden = values.length === 0;
  }
  search?.addEventListener("input", async () => {
    const query = search.value.trim().toLowerCase();
    if (!query) { if (results) results.hidden = true; return; }
    if (index === null) {
      try { index = await (await fetch(versionRoot + "search-index.json")).json(); }
      catch { index = []; }
    }
    const values = index.filter(item => `${item.label} ${item.qualified}`.toLowerCase().includes(query));
    showResults(values);
  });
  document.addEventListener("click", event => {
    if (!event.target.closest(".api-search") && results) results.hidden = true;
  });
})();
"""


@functools.cache
def _asset_version(kind: str) -> str:
    text = _CSS if kind == "css" else _JS
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:10]


def _write_page(
    *,
    output: Path,
    graph: ApiGraph,
    document: Path,
    body: str,
    toc: list[tuple[str, str, int]],
    current: ApiEntity | None,
    special: str,
    project_docs_url: str,
    copyright_text: str,
) -> None:
    path = output / _output_file(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _layout(
            graph=graph,
            document=document,
            body=body,
            toc=toc,
            current=current,
            special=special,
            project_docs_url=project_docs_url,
            copyright_text=copyright_text,
        ),
        encoding="utf-8",
    )


def _redirect(output: Path, document: Path, target: str) -> None:
    path = output / _output_file(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url='
        + html.escape(target, quote=True)
        + '">'
        "<script>location.replace(" + json.dumps(target) + ")</script>",
        encoding="utf-8",
    )


def _search_index(graph: ApiGraph) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for entity in sorted(
        graph.entities.values(), key=lambda value: value.qualified_name.casefold()
    ):
        target, anchor = _entity_target(entity, graph)
        url = _output_directory(target).as_posix().rstrip("/") + "/"
        if anchor:
            url += f"#{anchor}"
        values.append(
            {
                "label": entity.member_label,
                "qualified": entity.qualified_name,
                "kind": _kind_label(entity.kind),
                "url": url,
            }
        )
    return values


def render_html_site(
    graph: ApiGraph,
    *,
    output_directory: Path,
    project_docs_url: str,
    copyright_text: str,
    introduction_file: Path | None = None,
) -> None:
    """Render one API version directly to a standalone HTML site."""

    assign_documents(graph.entities.values())
    output = output_directory.resolve()
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True, exist_ok=True)
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "cpdocs-api.css").write_text(_CSS.strip() + "\n", encoding="utf-8")
    (assets / "cpdocs-api.js").write_text(_JS.strip() + "\n", encoding="utf-8")

    home_document = Path("index.md")
    introduction = None
    if introduction_file is not None and introduction_file.is_file():
        introduction = introduction_file.read_text(encoding="utf-8")
    body, toc = _home_page(graph, home_document, project_docs_url, introduction=introduction)
    _write_page(
        output=output,
        graph=graph,
        document=home_document,
        body=body,
        toc=toc,
        current=None,
        special="home",
        project_docs_url=project_docs_url,
        copyright_text=copyright_text,
    )

    if graph.feature_sets:
        feature_sets_document = Path("feature-sets.md")
        body, toc = _feature_sets_page(graph, feature_sets_document)
        _write_page(
            output=output,
            graph=graph,
            document=feature_sets_document,
            body=body,
            toc=toc,
            current=None,
            special="feature_sets",
            project_docs_url=project_docs_url,
            copyright_text=copyright_text,
        )

    if any(entity.kind == "macro" for entity in graph.entities.values()):
        macros_document = Path("macros.md")
        body, toc = _macros_page(graph, macros_document)
        _write_page(
            output=output,
            graph=graph,
            document=macros_document,
            body=body,
            toc=toc,
            current=None,
            special="macros",
            project_docs_url=project_docs_url,
            copyright_text=copyright_text,
        )

    for entity in graph.entities.values():
        if _embedded_member_parent(entity, graph) is not None:
            continue
        document = entity_document(entity)
        body, toc = _entity_page(entity, graph, document)
        _write_page(
            output=output,
            graph=graph,
            document=document,
            body=body,
            toc=toc,
            current=entity,
            special="entity",
            project_docs_url=project_docs_url,
            copyright_text=copyright_text,
        )

    source_pages = dict(graph.files)
    source_pages.update(graph.sources)
    for source_path, content in source_pages.items():
        document = _source_document(source_path)
        body, toc = _source_page(source_path, content, document, graph)
        _write_page(
            output=output,
            graph=graph,
            document=document,
            body=body,
            toc=toc,
            current=None,
            special="source",
            project_docs_url=project_docs_url,
            copyright_text=copyright_text,
        )

    symbols: dict[str, str] = {}
    for entity in graph.entities.values():
        target_document, anchor = _entity_target(entity, graph)
        target_url = _output_directory(target_document).as_posix().rstrip("/") + "/"
        if anchor:
            target_url += f"#{anchor}"
        symbols[entity.qualified_name] = target_url
        separator = "." if entity.language == "python" else "::"
        alias = Path("_symbols", *entity.qualified_name.split(separator), "index.md")
        redirect_target = _page_href(alias, target_document, anchor)
        _redirect(output, alias, redirect_target)

    (output / "symbols.json").write_text(
        json.dumps(symbols, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "search-index.json").write_text(
        json.dumps(_search_index(graph), indent=2) + "\n", encoding="utf-8"
    )
    (output / ".nojekyll").touch()
