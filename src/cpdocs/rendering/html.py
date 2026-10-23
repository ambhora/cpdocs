# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
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
import secrets
import shutil
from pathlib import Path, PurePosixPath

from markdown_it import MarkdownIt

from ..config import THEME_COLORS, SiteTheme
from ..filesystem import contained_path, remove_tree
from ..languages import kind_label as language_kind_label
from ..languages import language_label as semantic_language_label
from ..languages import rendering_for
from ..model import ApiEntity, ApiGraph, ApiSignature, entity_sort_key
from ..resources import resource, shared_template, shared_text
from .common import (
    _documentation_blocks,
    _embedded_member_parent,
    _entity_declaration,
    _feature_set_anchor,
    _highlight_declaration,
    _highlight_source_lines,
    _is_container,
    _is_function,
    _is_type_page,
    _kind_marker,
    _member_anchor,
    _member_summary_spelling,
    _relative_link,
    _signature_spelling,
    _source_document,
    _source_language,
    assign_documents,
    entity_document,
)

_INLINE_DOCUMENTATION = re.compile(
    r"`(?P<code>[^`]+)`"
    r"|\*\*(?P<strong>[^*\n]+?)\*\*"
    r"|\[(?P<label>[^\]]+)\]\((?P<href>[^)]+)\)"
    r"|@projectdocs(?:\{(?P<project_path>[^}]+)\})?"
)
_PROJECTDOCS_HREF = re.compile(r'href=(?P<quote>["\'])projectdocs:(?P<path>[^"\']*)(?P=quote)')

_MARKDOWN = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})

# A browser drops ASCII tab and newline anywhere in a URL, and leading C0 controls and spaces, before
# it reads the scheme, so ``java\tscript:`` and ``\x01javascript:`` both reach it as ``javascript:``.
# Destinations with any control character are therefore refused outright rather than normalized.
_LINK_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_LINK_SCHEME = re.compile(r"^(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*):")
_LINK_SCHEMES = frozenset({"http", "https", "mailto", "projectdocs"})


def safe_link_destination(href: str) -> str | None:
    """Return a documentation link destination if it is safe to emit, otherwise ``None``.

    Relative links and anchors carry no scheme and are kept; a destination with a scheme is kept
    only for HTTP(S), mail and cpdocs's own ``projectdocs:`` links.
    """

    value = href.strip(" ")
    if not value or _LINK_CONTROL.search(value):
        return None
    scheme = _LINK_SCHEME.match(value)
    if scheme is not None and scheme.group("scheme").casefold() not in _LINK_SCHEMES:
        return None
    return value


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
        target = _project_docs_target(document, project_docs_url, html.unescape(match.group("path")))
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
    """Return the semantic path shown to readers while preserving internal source keys for links."""
    display_paths = graph.metadata.get("source_display_paths", {})
    if isinstance(display_paths, dict):
        value = display_paths.get(source_path)
        if isinstance(value, str) and value:
            return value

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


def _kind_label(kind: str, language: str) -> str:
    return language_kind_label(kind, language)


def _kind_badge(kind: str, language: str) -> str:
    marker = html.escape(_kind_marker(kind, language))
    return f'<span class="api-kind" title="{html.escape(_kind_label(kind, language))}">{marker}</span>'


def _language_label(language: str) -> str:
    return semantic_language_label(language)


def _language_badge(entity: ApiEntity) -> str:
    if _is_container(entity):
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


def _language_configuration_inline(graph: ApiGraph, key: str) -> str:
    configuration = graph.feature_sets.get(key, {}).get("languages", {})
    if not isinstance(configuration, dict) or not configuration:
        return ""

    def entries(value: dict[str, object], prefix: str = "") -> list[str]:
        results = []
        for name, item in sorted(value.items()):
            path = f"{prefix}.{name}" if prefix else name
            if isinstance(item, dict):
                results.extend(entries(item, path))
            else:
                results.append(f"{path}={item}")
        return results

    return " ".join(f"<code>{html.escape(item)}</code>" for item in entries(configuration))


def _feature_set_text(graph: ApiGraph, key: str) -> str:
    features = _feature_set_features(graph, key)
    return ", ".join(features) if features else "default"


def _feature_set_inline(graph: ApiGraph, key: str) -> str:
    features = _feature_set_features(graph, key)
    if not features:
        return '<span class="api-feature-set-empty">default (no features enabled)</span>'
    return " ".join(f"<code>{html.escape(feature)}</code>" for feature in features)


def _legend(graph: ApiGraph) -> str:
    kinds: list[tuple[str, str]] = []
    seen: set[str] = set()
    for entity in sorted(graph.entities.values(), key=entity_sort_key):
        if entity.kind in seen:
            continue
        seen.add(entity.kind)
        kinds.append((entity.kind, entity.language))
    entries = [
        f'<span class="api-legend-entry">{_kind_badge(kind, language)} {_kind_label(kind, language)}</span>'
        for kind, language in kinds
    ]
    return '<div class="api-legend">' + '<span class="api-legend-separator">·</span>'.join(entries) + "</div>"


def _visible_outline_children(entity: ApiEntity, graph: ApiGraph) -> list[ApiEntity]:
    # Public members of records live on the record page and should not duplicate themselves in the
    # global API outline.  Namespaces/modules/packages retain their recursive API tree.
    if _is_type_page(entity):
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


def _outline_entity(entity: ApiEntity, graph: ApiGraph, document: Path, current: ApiEntity | None) -> str:
    children = _visible_outline_children(entity, graph)
    expanded = bool(children and _is_ancestor(entity, current, graph))
    active = current is not None and entity.id == current.id
    href = _entity_href(document, entity, graph)
    row = [
        '<div class="api-outline-row' + (" is-current" if active else "") + '">',
        _kind_badge(entity.kind, entity.language),
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
            + "".join("<li>" + _outline_entity(child, graph, document, current) + "</li>" for child in children)
            + "</ul>"
        )
    return "".join(row) + child_html


def _outline(graph: ApiGraph, document: Path, current: ApiEntity | None, *, current_special: str = "") -> str:
    roots = [entity for entity in graph.roots() if entity.kind != "macro"]
    macros = sorted((entity for entity in graph.entities.values() if entity.kind == "macro"), key=entity_sort_key)
    current_label = (
        current.name
        if current is not None
        else {"home": "Home", "feature_sets": "Feature Sets", "macros": "Macros", "source": "Source"}.get(
            current_special, ""
        )
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
                '<li><div class="api-outline-row' + (" is-current" if feature_sets_current else "") + '">',
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
                + _kind_badge("macro", macro.language)
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
        parts.append(f'<li class="toc-level-{level}"><a href="#{html.escape(anchor)}">{html.escape(label)}</a></li>')
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
            href = safe_link_destination(match.group("href"))
            # A refused destination keeps its label as plain text.
            if href is None:
                result.append(label)
            else:
                result.append(f'<a href="{html.escape(href, quote=True)}">{label}</a>')
        else:
            target = (match.group("project_path") or "").strip()
            label = target.rstrip("/") or "project documentation"
            result.append(f'<a href="projectdocs:{html.escape(target, quote=True)}">{html.escape(label)}</a>')
        position = match.end()
    result.append(html.escape(text[position:]))
    return "".join(result)


_DOCUMENTATION_FIELD = re.compile(r"@(?P<command>tparam|param|returns?|throws?)\b\s*(?P<rest>.*)", re.DOTALL)
_FIELD_TITLES = {"tparam": "Template parameters", "param": "Parameters", "return": "Returns", "throws": "Throws"}


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
        command = {"returns": "return", "throw": "throws"}.get(field.group("command"), field.group("command"))
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
        paragraphs.append(f'<div class="api-doc-field"><p class="api-doc-field-title">{_FIELD_TITLES[command]}</p>')
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
    return description + '<p class="api-related"><strong>Related:</strong> ' + " · ".join(links) + "</p>"


def _language_configuration_labels(graph: ApiGraph, key: str) -> list[str]:
    """Human-facing labels for the *observed* build configuration, not a range claim."""

    configuration = graph.feature_sets.get(key, {}).get("languages", {})
    if not isinstance(configuration, dict):
        return []
    names = {
        "c": "C",
        "cxx": "C++",
        "cpp": "C++",
        "python": "Python",
        "fortran": "Fortran",
        "rust": "Rust",
        "cuda": "CUDA",
        "hip": "HIP",
    }
    labels: list[str] = []

    def collect(value: dict[str, object], prefix: str = "") -> None:
        for name, item in sorted(value.items()):
            path = f"{prefix}.{name}" if prefix else name
            if isinstance(item, dict):
                collect(item, path)
                continue
            parts = path.split(".")
            if len(parts) == 2 and parts[0] in names and parts[1] in {"standard", "version", "edition"}:
                language = names[parts[0]]
                separator = "" if parts[0] in {"c", "cxx", "cpp"} else " "
                labels.append(f"{language}{separator}{item}")
            else:
                labels.append(f"{path}={item}")

    collect(configuration)
    return labels


def _availability(entity: ApiEntity, graph: ApiGraph, document: Path, feature_sets: list[str] | None = None) -> str:
    # A supplied empty signature list means *no observed build*, not entity-wide availability.
    keys = list(dict.fromkeys(entity.feature_sets if feature_sets is None else feature_sets))
    if not keys:
        return ""

    def link(key: str, contents: str) -> str:
        href = _page_href(document, Path("feature-sets.md"), _feature_set_anchor(key))
        return f'<a href="{html.escape(href)}">{contents}</a>'

    parts = ['<div class="api-availability">']
    # Group identical language configurations, but retain links to the exact build matrix below.
    seen: set[str] = set()
    language_rows: list[str] = []
    for key in keys:
        labels = _language_configuration_labels(graph, key)
        if not labels:
            continue
        configuration = graph.feature_sets.get(key, {}).get("languages", {})
        identity = json.dumps(configuration, sort_keys=True, default=str)
        if identity in seen:
            continue
        seen.add(identity)
        contents = " · ".join(f"<code>{html.escape(value)}</code>" for value in labels)
        language_rows.append("<li>" + link(key, contents) + "</li>")
    if language_rows:
        parts.append(
            '<div class="api-availability-dimension"><strong>Language versions / standards</strong>'
            '<ul class="api-availability-list">' + "".join(language_rows) + "</ul></div>"
        )

    rows = []
    for key in keys:
        labels = _language_configuration_labels(graph, key)
        # Preserve the exact combinations: e.g. C++20 + MPI can be present even if
        # C++20 + default is absent. Every row links to that precise build.
        qualifier = " · " + " · ".join(f"<code>{html.escape(value)}</code>" for value in labels) if labels else ""
        rows.append("<li>" + link(key, _feature_set_inline(graph, key) + qualifier) + "</li>")
    parts.append(
        '<div class="api-availability-dimension"><strong>Available in feature sets</strong>'
        '<ul class="api-availability-list">' + "".join(rows) + "</ul></div>"
    )
    parts.append("</div>")
    return "".join(parts)


def _defined_in(entity: ApiEntity, graph: ApiGraph, document: Path) -> str:
    if _is_container(entity) or entity.source is None:
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
    declaration = _highlight_declaration(spelling, entity.language, entity=entity, graph=graph, document_path=document)
    properties = list(
        dict.fromkeys(
            [*entity.properties, *signature.qualifiers, *(attribute.name for attribute in signature.attributes)]
        )
    )
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
    # Hand-built/legacy graphs did not record per-signature provenance.
    return entity.feature_sets


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


def _container_page(entity: ApiEntity, graph: ApiGraph, document: Path) -> tuple[str, list[tuple[str, str, int]]]:
    title = f"{_kind_label(entity.kind, entity.language).title()} {entity.qualified_name}"
    body = [f"<h1>{html.escape(title)}</h1>"]
    if entity.documentation.strip():
        body.append('<div class="api-namespace-doc">' + _documentation(entity, graph, document) + "</div>")
    else:
        body.append(
            shared_template("api/namespace-description.html").substitute(
                qualified_name=html.escape(entity.qualified_name),
                kind=html.escape(_kind_label(entity.kind, entity.language)),
            )
        )
    body.extend(
        [
            '<section id="members" class="api-section">',
            "<h2>Members</h2>",
            _legend(graph),
            '<ul class="api-namespace-tree">',
        ]
    )

    def render_container_children(container: ApiEntity) -> str:
        children = [
            graph.entities[value]
            for value in container.children
            if value in graph.entities and graph.entities[value].kind != "macro"
        ]
        children.sort(key=entity_sort_key)
        parts: list[str] = []
        for child in children:
            parts.append('<li><div class="api-namespace-tree-row">')
            parts.append(_kind_badge(child.kind, child.language))
            parts.append(
                f'<a href="{html.escape(_entity_href(document, child, graph))}">{html.escape(child.member_label)}</a>'
            )
            parts.append(_language_badge(child))
            parts.append("</div>")
            if _is_container(child):
                nested = render_container_children(child)
                if nested:
                    parts.append("<ul>" + nested + "</ul>")
            parts.append("</li>")
        return "".join(parts)

    body.append(render_container_children(entity))
    body.extend(["</ul>", _availability(entity, graph, document), "</section>"])
    return "".join(body), [("Members", "members", 1)]


def _record_page(entity: ApiEntity, graph: ApiGraph, document: Path) -> tuple[str, list[tuple[str, str, int]]]:
    children = [graph.entities[value] for value in entity.children if value in graph.entities]
    children.sort(key=entity_sort_key)
    body = [
        f'<h1 class="api-entity-title">{html.escape(entity.name)} {_language_badge(entity)}</h1>',
        _defined_in(entity, graph, document),
    ]
    display_entity = dataclasses.replace(entity, qualified_name=entity.name)
    declaration_text = _entity_declaration(display_entity)
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
            '<section id="specializations" class="api-section"><h2>Specializations</h2><div class="api-record-members">'
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
                + _kind_badge(other.kind, other.language)
                + f'<code>{prefix} <a href="{href}">{html.escape(other.name)}</a></code>'
                + (
                    '<div class="api-member-doc">' + _documentation(other, graph, document) + "</div>"
                    if other.documentation.strip()
                    else ""
                )
                + "</div>"
            )
        body.append("</div></section>")

    grouped: dict[str, list[ApiEntity]] = {}
    for child in children:
        heading = rendering_for(child.language).member_group(child)
        if heading is not None:
            grouped.setdefault(heading, []).append(child)
    for heading, values in grouped.items():
        if not values:
            continue
        section_anchor = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
        body.append(f'<section id="{section_anchor}" class="api-section"><h2>{html.escape(heading)}</h2>')
        toc.append((heading, section_anchor, 1))
        body.append('<div class="api-record-members">')
        for child in values:
            if _is_function(child) and child.signatures:
                for index, signature in enumerate(child.signatures):
                    anchor = _member_anchor_for_signature(child, index)
                    label = _compact_signature_label(child, signature)
                    toc.append((label, anchor, 2))
                    body.append(_signature_card(child, signature, graph, document, anchor=anchor))
            elif heading == "Public Members":
                anchor = _member_anchor(child)
                toc.append((child.name, anchor, 2))
                summary = _member_summary_spelling(child)
                highlighted = _highlight_declaration(
                    summary, child.language, entity=child, graph=graph, document_path=document
                )
                body.append(
                    f'<div class="api-member-row" id="{html.escape(anchor)}">'
                    + _kind_badge(child.kind, child.language)
                    + f"<code>{highlighted}</code>"
                    + (
                        '<div class="api-member-doc">' + _documentation(child, graph, document) + "</div>"
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
                    + _kind_badge(child.kind, child.language)
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


def _function_page(entity: ApiEntity, graph: ApiGraph, document: Path) -> tuple[str, list[tuple[str, str, int]]]:
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


def _enum_page(entity: ApiEntity, graph: ApiGraph, document: Path) -> tuple[str, list[tuple[str, str, int]]]:
    return _record_page(entity, graph, document)


def _simple_entity_page(entity: ApiEntity, graph: ApiGraph, document: Path) -> tuple[str, list[tuple[str, str, int]]]:
    body = [
        f'<h1 class="api-entity-title">{html.escape(entity.name)} {_language_badge(entity)}</h1>',
        _defined_in(entity, graph, document),
    ]
    if entity.signatures:
        for index, signature in enumerate(entity.signatures):
            body.append(_signature_card(entity, signature, graph, document, anchor=f"signature-{index + 1}"))
    else:
        declaration = _highlight_declaration(
            _entity_declaration(entity), entity.language, entity=entity, graph=graph, document_path=document
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


def _entity_page(entity: ApiEntity, graph: ApiGraph, document: Path) -> tuple[str, list[tuple[str, str, int]]]:
    if _is_container(entity):
        return _container_page(entity, graph, document)
    if _is_type_page(entity):
        return _record_page(entity, graph, document)
    if _is_function(entity):
        return _function_page(entity, graph, document)
    return _simple_entity_page(entity, graph, document)


def _hierarchy_entity(entity: ApiEntity, graph: ApiGraph, document: Path) -> str:
    children = _visible_outline_children(entity, graph)
    parts = [
        "<li>",
        _kind_badge(entity.kind, entity.language),
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
        parts.append(f'<li><span class="api-kind file-kind" title="directory">D</span><span>{html.escape(name)}</span>')
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
    graph: ApiGraph, document: Path, project_docs_url: str, *, introduction: str | None = None
) -> tuple[str, list[tuple[str, str, int]]]:
    del project_docs_url
    roots = [entity for entity in graph.roots() if entity.kind != "macro"]
    macros = sorted((entity for entity in graph.entities.values() if entity.kind == "macro"), key=entity_sort_key)
    if introduction is None:
        introduction = shared_text("api/index.md")
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
                + _kind_badge("macro", macro.language)
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
    return "".join(body), [("API hierarchy", "api-hierarchy", 1), ("File Hierarchy", "file-hierarchy", 1)]


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
    has_language_configurations = any(_language_configuration_inline(graph, key) for key in graph.feature_sets)
    body = [
        "<h1>Feature Sets</h1>",
        shared_text("api/feature-sets-intro.html"),
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
            "<thead><tr><th>Feature set</th><th>Enabled features</th>"
            + ("<th>Language configuration</th>" if has_language_configurations else "")
            + "</tr></thead>",
            "<tbody>",
        ]
    )
    toc: list[tuple[str, str, int]] = [("Overview", "overview", 1), ("Feature Sets", "feature-sets", 1)]
    for index, key in enumerate(graph.feature_sets, 1):
        anchor = _feature_set_anchor(key)
        configuration_column = (
            "<td>" + (_language_configuration_inline(graph, key) or "default") + "</td>"
            if has_language_configurations
            else ""
        )
        body.append(
            f'<tr id="{html.escape(anchor)}">'
            f'<th scope="row">{index}</th>'
            "<td>" + _feature_set_inline(graph, key) + "</td>" + configuration_column + "</tr>"
        )
    body.append("</tbody></table></section>")
    # Option metadata are documentation of each resolved build, not extra feature axes.
    # Display the first build as the default reference; retain all sets in graph metadata.
    configurations = graph.metadata.get("configuration_options", {})
    if isinstance(configurations, dict) and configurations:
        first = next(iter(graph.feature_sets), None)
        options = configurations.get(first, [])
        if isinstance(options, list) and options:
            body.extend(
                [
                    '<section id="configuration-options" class="api-section">',
                    "<h2>Configuration options</h2>",
                    shared_text("api/configuration-options-intro.html"),
                    "<table><thead><tr><th>Group</th><th>Option</th><th>Value</th><th>Description</th></tr></thead><tbody>",
                ]
            )
            for option in options:
                if not isinstance(option, dict):
                    continue
                cells = [str(option.get(field, "")) for field in ("group", "name", "value", "description")]
                body.append("<tr>" + "".join(f"<td>{html.escape(value)}</td>" for value in cells) + "</tr>")
            body.append("</tbody></table></section>")
            toc.append(("Configuration options", "configuration-options", 1))
    return "".join(body), toc


def _macros_page(graph: ApiGraph, document: Path) -> tuple[str, list[tuple[str, str, int]]]:
    macros = sorted((entity for entity in graph.entities.values() if entity.kind == "macro"), key=entity_sort_key)
    body = ['<h1>Macros</h1><ul class="api-member-list">']
    for macro in macros:
        body.append(
            "<li>"
            + _kind_badge("macro", macro.language)
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
        content = "\n".join(re.sub(r"[ \t]+\\[ \t]*$", r" \\", line.rstrip()) for line in content.splitlines()) + (
            "\n" if content.endswith("\n") else ""
        )
    highlighted = _highlight_source_lines(content, language)
    display_path = _display_source_path(source_path, graph)
    generated_sources = graph.metadata.get("generated_sources", [])
    generated_files = graph.metadata.get("generated_files", [])
    generated = (isinstance(generated_sources, list) and source_path in generated_sources) or (
        isinstance(generated_files, list) and source_path in generated_files
    )
    note = '<p class="api-section-intro">Generated by the build; not part of the repository.</p>' if generated else ""
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
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", project_docs_url) or project_docs_url.startswith("/"):
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
    theme: _ThemeAssets,
) -> str:
    body = _resolve_projectdocs_links(body, document, project_docs_url)
    # The version query changes whenever the asset does, so a browser never pairs new pages with a
    # stylesheet or script it cached from an older cpdocs.
    stylesheet = _root_relative(document, "assets/cpdocs-api.css") + f"?v={_asset_version('cpdocs-api.css')}"
    script = _root_relative(document, "assets/cpdocs-api.js") + f"?v={_asset_version('cpdocs-api.js')}"
    init_script = _root_relative(document, "assets/cpdocs-api-init.js") + f"?v={_asset_version('cpdocs-api-init.js')}"
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
    return shared_template("api/layout.html").substitute(
        page_title=html.escape(_page_title(current, graph, special)),
        stylesheet=html.escape(stylesheet),
        theme_head=_theme_head(document, theme),
        init_script=html.escape(init_script),
        version_root=html.escape(version_root),
        api_root=html.escape(api_root),
        current_route=html.escape(current_route),
        home=html.escape(home),
        logo=_theme_logo(document, theme),
        project=html.escape(graph.project),
        project_docs=html.escape(project_docs),
        version=html.escape(graph.version),
        outline=_outline(graph, document, current, current_special=special),
        body=body,
        toc=_toc(toc),
        copyright=html.escape(copyright_text),
        script=html.escape(script),
    )


_ASSET_FILES = ("cpdocs-api.css", "cpdocs-api.js", "cpdocs-api-init.js")


def _asset_resource(name: str):
    """Return a packaged API-rendering resource (also works outside a source checkout)."""
    return resource("api", name)


@functools.cache
def _asset_version(name: str) -> str:
    return hashlib.sha1(_asset_resource(name).read_bytes().strip()).hexdigest()[:10]


# The CSS custom property behind each colour of ``site.theme.colors``.
_THEME_PROPERTIES = {
    "accent": "--api-accent",
    "accent-2": "--api-accent-2",
    "on-accent": "--api-on-accent",
    "background": "--api-bg",
    "foreground": "--api-fg",
    "muted": "--api-muted",
    "border": "--api-border",
    "soft": "--api-soft",
    "selected": "--api-selected",
}
assert tuple(_THEME_PROPERTIES) == THEME_COLORS


@dataclasses.dataclass(frozen=True)
class _ThemeAsset:
    """A theme file in ``assets`` and the version that keeps browsers from caching it stale."""

    name: str
    version: str

    def href(self, document: Path) -> str:
        return _root_relative(document, f"assets/{self.name}") + f"?v={self.version}"


@dataclasses.dataclass(frozen=True)
class _ThemeAssets:
    """The theme files of one rendered site; each is ``None`` when the theme does not set it."""

    stylesheet: _ThemeAsset | None = None
    logo: _ThemeAsset | None = None
    favicon: _ThemeAsset | None = None


def _theme_stylesheet(theme: SiteTheme) -> str:
    """The colours of the theme as custom properties, followed by its own stylesheet."""

    blocks: list[str] = []
    for scheme, colors in theme.colors.items():
        if not colors:
            continue
        lines = [f"  {_THEME_PROPERTIES[name]}: {value};" for name, value in colors.items()]
        blocks.append(f'html[data-theme="{scheme}"] {{\n' + "\n".join(lines) + "\n}\n")
    if theme.stylesheet is not None:
        blocks.append(theme.stylesheet.read_text(encoding="utf-8"))
    return "\n".join(blocks)


def _write_theme_asset(assets: Path, name: str, contents: bytes) -> _ThemeAsset:
    (assets / name).write_bytes(contents)
    return _ThemeAsset(name=name, version=hashlib.sha1(contents).hexdigest()[:10])


def _write_theme(assets: Path, theme: SiteTheme) -> _ThemeAssets:
    stylesheet = _theme_stylesheet(theme)
    return _ThemeAssets(
        stylesheet=(_write_theme_asset(assets, "cpdocs-theme.css", stylesheet.encode("utf-8")) if stylesheet else None),
        logo=(
            _write_theme_asset(assets, "logo" + theme.logo.suffix.lower(), theme.logo.read_bytes())
            if theme.logo is not None
            else None
        ),
        favicon=(
            _write_theme_asset(assets, "favicon" + theme.favicon.suffix.lower(), theme.favicon.read_bytes())
            if theme.favicon is not None
            else None
        ),
    )


def _theme_head(document: Path, theme: _ThemeAssets) -> str:
    """Links of the theme in the page head, after the cpdocs stylesheet they override."""

    links = ""
    if theme.stylesheet is not None:
        links += f'\n<link rel="stylesheet" href="{html.escape(theme.stylesheet.href(document))}">'
    if theme.favicon is not None:
        links += f'\n<link rel="icon" href="{html.escape(theme.favicon.href(document))}">'
    return links


def _theme_logo(document: Path, theme: _ThemeAssets) -> str:
    if theme.logo is None:
        return ""
    # The project name follows the logo, so the image itself is decorative.
    return f'<img class="api-brand-logo" src="{html.escape(theme.logo.href(document))}" alt="">'


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
    theme: _ThemeAssets,
) -> None:
    path = contained_path(output, _output_file(document))
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
            theme=theme,
        ),
        encoding="utf-8",
    )


def _symbol_alias(parts: list[str]) -> Path | None:
    """The stable ``_symbols/...`` alias of a qualified name, if every component is a plain name.

    Aliases keep the readable spelling of each component, so a component that a filesystem would
    read as structure (a separator, ``.``, ``..``) gets no alias. Such names, as ``operator/``,
    are still documented and reachable through their page.
    """

    if any(not part or part in {".", ".."} or "/" in part or "\\" in part or "\0" in part for part in parts):
        return None
    return Path("_symbols", *parts, "index.md")


def _redirect(output: Path, document: Path, target: str) -> None:
    path = contained_path(output, _output_file(document))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        shared_template("api/redirect.html").substitute(
            target=html.escape(target, quote=True), target_json=json.dumps(target)
        ),
        encoding="utf-8",
    )


def _search_index(graph: ApiGraph) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for entity in sorted(graph.entities.values(), key=lambda value: value.qualified_name.casefold()):
        target, anchor = _entity_target(entity, graph)
        url = _output_directory(target).as_posix().rstrip("/") + "/"
        if anchor:
            url += f"#{anchor}"
        values.append(
            {
                "label": entity.member_label,
                "qualified": entity.qualified_name,
                "kind": _kind_label(entity.kind, entity.language),
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
    theme: SiteTheme | None = None,
) -> None:
    """Render one API version to a standalone HTML site in ``output_directory``.

    The site is rendered into a fresh sibling directory and moved into place only when complete,
    so a failed render leaves the previous site untouched. The directory being replaced is deleted
    as itself: a symbolic link there is refused rather than followed.
    """

    target = output_directory.absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f".{target.name}.{secrets.token_hex(6)}.cpdocs-staging"
    # mkdir, unlike mkdtemp, applies the umask, so a published site stays readable by a web server.
    staging.mkdir()
    try:
        _render_site(
            graph,
            output=staging,
            project_docs_url=project_docs_url,
            copyright_text=copyright_text,
            introduction_file=introduction_file,
            theme=theme,
        )
        remove_tree(target, owner=target.parent)
        staging.rename(target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _render_site(
    graph: ApiGraph,
    *,
    output: Path,
    project_docs_url: str,
    copyright_text: str,
    introduction_file: Path | None,
    theme: SiteTheme | None,
) -> None:
    """Render the pages, assets and indexes of one API version into the empty ``output``."""

    assign_documents(graph.entities.values())
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in _ASSET_FILES:
        (assets / name).write_bytes(_asset_resource(name).read_bytes())
    theme_assets = _write_theme(assets, theme if theme is not None else SiteTheme())

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
        theme=theme_assets,
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
            theme=theme_assets,
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
            theme=theme_assets,
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
            theme=theme_assets,
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
            theme=theme_assets,
        )

    symbols: dict[str, str] = {}
    for entity in graph.entities.values():
        target_document, anchor = _entity_target(entity, graph)
        target_url = _output_directory(target_document).as_posix().rstrip("/") + "/"
        if anchor:
            target_url += f"#{anchor}"
        symbols[entity.qualified_name] = target_url
        separator = "." if entity.language == "python" else "::"
        alias = _symbol_alias(entity.qualified_name.split(separator))
        if alias is not None:
            redirect_target = _page_href(alias, target_document, anchor)
            _redirect(output, alias, redirect_target)

    (output / "symbols.json").write_text(json.dumps(symbols, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "search-index.json").write_text(json.dumps(_search_index(graph), indent=2) + "\n", encoding="utf-8")
    (output / ".nojekyll").touch()
