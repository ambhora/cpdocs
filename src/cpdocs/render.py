# SPDX-FileCopyrightText: 2026 cpdocs developers
#
# SPDX-License-Identifier: Apache-2.0
"""Shared rendering helpers for cpdocs' code-oriented API layout."""

from __future__ import annotations

import hashlib
import html
import re
from collections.abc import Iterable
from pathlib import Path

try:
    from pygments import highlight, lex
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import CppLexer, FortranLexer, PythonLexer, RustLexer, TextLexer
except ImportError:  # pragma: no cover - optional dependency in some bootstrap environments
    highlight = None
    lex = None
    HtmlFormatter = None
    CppLexer = FortranLexer = PythonLexer = RustLexer = TextLexer = None

from .model import ApiEntity, ApiGraph, ApiSignature


def split_qualified(name: str, separator: str) -> list[str]:
    """Split a qualified name on ``separator`` outside template argument lists."""

    parts: list[str] = []
    depth = 0
    start = 0
    index = 0
    while index < len(name):
        character = name[index]
        if character == "<":
            depth += 1
        elif character == ">":
            depth = max(0, depth - 1)
        elif depth == 0 and name.startswith(separator, index):
            parts.append(name[start:index])
            index += len(separator)
            start = index
            continue
        index += 1
    parts.append(name[start:])
    return [part for part in parts if part]


def _segments(entity: ApiEntity) -> list[str]:
    separator = "." if entity.language == "python" else "::"
    return split_qualified(entity.qualified_name, separator)


# Operator names as words, longest spelling first, so that ``operator<<`` is not read as ``<``.
_OPERATOR_WORDS = (
    ("<=>", "spaceship"),
    ("<<=", "shl-assign"),
    (">>=", "shr-assign"),
    ("->*", "arrow-star"),
    ("new[]", "new-array"),
    ("delete[]", "delete-array"),
    ('""', "literal"),
    ("()", "call"),
    ("[]", "subscript"),
    ("->", "arrow"),
    ("<<", "shl"),
    (">>", "shr"),
    ("==", "eq"),
    ("!=", "ne"),
    ("<=", "le"),
    (">=", "ge"),
    ("&&", "and"),
    ("||", "or"),
    ("++", "inc"),
    ("--", "dec"),
    ("+=", "add-assign"),
    ("-=", "sub-assign"),
    ("*=", "mul-assign"),
    ("/=", "div-assign"),
    ("%=", "mod-assign"),
    ("&=", "and-assign"),
    ("|=", "or-assign"),
    ("^=", "xor-assign"),
    ("<", "lt"),
    (">", "gt"),
    ("+", "add"),
    ("-", "sub"),
    ("*", "mul"),
    ("/", "div"),
    ("%", "mod"),
    ("&", "bitand"),
    ("|", "bitor"),
    ("^", "xor"),
    ("~", "compl"),
    ("!", "not"),
    ("=", "assign"),
    (",", "comma"),
)

# Symbols inside template arguments that must stay distinguishable, spelled as words.
_TYPE_WORDS = (
    ("...", " pack "),
    ("&&", " rref "),
    ("&", " ref "),
    ("*", " ptr "),
    ("[]", " array "),
)


def _slug(value: str) -> str:
    """A readable URL segment for one name component.

    ``storage_traits<bool>`` becomes ``storage_traits-bool``, ``vec<T, 0>`` becomes ``vec-t-0``
    and ``operator[]`` becomes ``operator-subscript``. Names that still collide after this are told
    apart when a site is rendered, see :func:`assign_documents`.
    """

    text = value.strip()
    operator = re.fullmatch(r"operator\s*(.+)", text)
    if operator is not None:
        tail = operator.group(1).replace(" ", "")
        for spelling, word in _OPERATOR_WORDS:
            if tail == spelling:
                return f"operator-{word}"
    for spelling, word in _TYPE_WORDS:
        text = text.replace(spelling, word)
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "-", text).strip("-").lower()
    return cleaned or "symbol"


# Documents of entities whose readable path collides with another entity's, set per rendered site.
_DOCUMENT_OVERRIDES: dict[str, Path] = {}


def assign_documents(entities: Iterable[ApiEntity]) -> None:
    """Resolve path collisions between entities before a site is rendered.

    Entities whose readable document path is shared get a short digest of their qualified name
    appended; all other paths stay readable and do not depend on the rest of the API.
    """

    _DOCUMENT_OVERRIDES.clear()
    by_path: dict[Path, list[ApiEntity]] = {}
    for entity in entities:
        by_path.setdefault(entity_document(entity), []).append(entity)
    for path, values in by_path.items():
        if len(values) < 2:
            continue
        for entity in values:
            key = f"{entity.language}:{entity.kind}:{entity.qualified_name}"
            digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:7]
            if path.name == "index.md":
                _DOCUMENT_OVERRIDES[entity.id] = (
                    path.parent.with_name(f"{path.parent.name}-{digest}") / "index.md"
                )
            else:
                _DOCUMENT_OVERRIDES[entity.id] = path.with_name(f"{path.stem}-{digest}.md")


def entity_document(entity: ApiEntity) -> Path:
    override = _DOCUMENT_OVERRIDES.get(entity.id)
    if override is not None:
        return override
    parts = [_slug(part) for part in _segments(entity)]
    if entity.kind in {"namespace", "module", "package"}:
        return Path("api", *parts, "index.md")
    if entity.kind in {"class", "struct", "derived_type", "union", "enum", "trait", "protocol"}:
        if len(parts) > 1:
            return Path("api", *parts[:-1], f"{entity.kind}-{parts[-1]}", "index.md")
        return Path("api", f"{entity.kind}-{parts[0]}", "index.md")
    if len(parts) > 1:
        return Path("api", *parts[:-1], f"{entity.kind}-{parts[-1]}.md")
    return Path("api", f"{entity.kind}-{parts[0]}.md")


def _source_document(source_path: str) -> Path:
    logical = Path(source_path)
    return Path("_sources", *logical.parent.parts, logical.name + ".md")


def _source_language(source_path: str) -> str:
    suffix = Path(source_path).suffix.casefold()
    if suffix in {".h", ".hh", ".hpp", ".hxx", ".c", ".cc", ".cpp", ".cxx", ".cu", ".cuh"}:
        return "cpp"
    if suffix in {".f", ".for", ".ftn", ".f77", ".f90", ".f95", ".f03", ".f08", ".f18"}:
        return "fortran"
    if suffix in {".py", ".pyi"}:
        return "python"
    if suffix == ".rs":
        return "rust"
    return "text"


def _pygments_lexer(language: str):
    lexer_map = {
        "c": CppLexer,
        "cpp": CppLexer,
        "cuda": CppLexer,
        "hip": CppLexer,
        "fortran": FortranLexer,
        "python": PythonLexer,
        "rust": RustLexer,
    }
    lexer_type = lexer_map.get(language, TextLexer)
    return lexer_type() if lexer_type is not None else None


_FALLBACK_KEYWORDS = {
    "cpp": {
        "alignas",
        "alignof",
        "asm",
        "auto",
        "bool",
        "break",
        "case",
        "catch",
        "char",
        "char8_t",
        "char16_t",
        "char32_t",
        "class",
        "concept",
        "const",
        "consteval",
        "constexpr",
        "constinit",
        "const_cast",
        "continue",
        "co_await",
        "co_return",
        "co_yield",
        "decltype",
        "default",
        "delete",
        "do",
        "double",
        "dynamic_cast",
        "else",
        "enum",
        "explicit",
        "export",
        "extern",
        "false",
        "float",
        "for",
        "friend",
        "goto",
        "if",
        "inline",
        "int",
        "long",
        "mutable",
        "namespace",
        "new",
        "noexcept",
        "nullptr",
        "operator",
        "private",
        "protected",
        "public",
        "register",
        "reinterpret_cast",
        "requires",
        "return",
        "short",
        "signed",
        "sizeof",
        "static",
        "static_assert",
        "static_cast",
        "struct",
        "switch",
        "template",
        "this",
        "thread_local",
        "throw",
        "true",
        "try",
        "typedef",
        "typeid",
        "typename",
        "union",
        "unsigned",
        "using",
        "virtual",
        "void",
        "volatile",
        "wchar_t",
        "while",
    },
    "python": {
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "False",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "None",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "True",
        "try",
        "while",
        "with",
        "yield",
    },
    "rust": {
        "as",
        "async",
        "await",
        "break",
        "const",
        "continue",
        "crate",
        "dyn",
        "else",
        "enum",
        "extern",
        "false",
        "fn",
        "for",
        "if",
        "impl",
        "in",
        "let",
        "loop",
        "match",
        "mod",
        "move",
        "mut",
        "pub",
        "ref",
        "return",
        "self",
        "Self",
        "static",
        "struct",
        "super",
        "trait",
        "true",
        "type",
        "unsafe",
        "use",
        "where",
        "while",
    },
}


_FALLBACK_TOKEN = re.compile(
    r"//[^\n]*|/\*.*?\*/|#[^\n]*|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|"
    r"\b(?:0[xX][0-9A-Fa-f]+|\d+(?:\.\d+)?)\b|\b[A-Za-z_]\w*\b|\s+|.",
    re.DOTALL,
)


def _fallback_lex(code: str, language: str) -> list[tuple[str, str]]:
    """Small built-in highlighter used when Pygments is unavailable at render time."""

    normalized_language = "cpp" if language in {"c", "cuda", "hip"} else language
    keywords = _FALLBACK_KEYWORDS.get(normalized_language, set())
    values: list[tuple[str, str]] = []
    for match in _FALLBACK_TOKEN.finditer(code):
        token = match.group(0)
        if language in {"c", "cpp", "cuda", "hip"} and token.startswith("#"):
            kind = "preprocessor"
        elif (
            token.startswith("//")
            or token.startswith("/*")
            or (language == "python" and token.startswith("#"))
        ):
            kind = "comment"
        elif token.startswith(('"', "'")):
            kind = "string"
        elif re.fullmatch(r"(?:0[xX][0-9A-Fa-f]+|\d+(?:\.\d+)?)", token):
            kind = "number"
        elif re.fullmatch(r"[A-Za-z_]\w*", token):
            kind = "keyword" if token in keywords else "name"
        else:
            kind = "plain"
        values.append((kind, token))
    return values


def _fallback_token_html(kind: str, value: str) -> str:
    escaped = html.escape(value)
    if kind == "plain" or not value.strip():
        return escaped
    return f'<span class="cpdocs-syntax-{kind}">{escaped}</span>'


def _token_style(formatter: HtmlFormatter, token_type) -> str:
    style = formatter.style.style_for_token(token_type)
    values: list[str] = []
    if style.get("color"):
        values.append(f"color: #{style['color']}")
    if style.get("bgcolor"):
        values.append(f"background-color: #{style['bgcolor']}")
    if style.get("bold"):
        values.append("font-weight: bold")
    if style.get("italic"):
        values.append("font-style: italic")
    if style.get("underline"):
        values.append("text-decoration: underline")
    return "; ".join(values)


def _highlight_source_lines(content: str, language: str) -> list[str]:
    if lex is None or HtmlFormatter is None:
        rendered: list[list[str]] = [[]]
        for kind, value in _fallback_lex(content, language):
            parts = value.split("\n")
            for index, part in enumerate(parts):
                if part:
                    rendered[-1].append(_fallback_token_html(kind, part))
                if index + 1 < len(parts):
                    rendered.append([])
        if content.endswith("\n") and rendered and not rendered[-1]:
            rendered.pop()
        return ["".join(parts) or " " for parts in rendered]

    lexer = _pygments_lexer(language)
    if lexer is None:
        return [html.escape(value) or " " for value in content.splitlines()]

    formatter = HtmlFormatter(noclasses=True, style="friendly")
    rendered: list[list[str]] = [[]]
    for token_type, value in lex(content, lexer):
        style = _token_style(formatter, token_type)
        parts = value.split("\n")
        for index, part in enumerate(parts):
            if part:
                escaped = html.escape(part)
                if style:
                    rendered[-1].append(
                        f'<span style="{html.escape(style, quote=True)}">{escaped}</span>'
                    )
                else:
                    rendered[-1].append(escaped)
            if index + 1 < len(parts):
                rendered.append([])

    # lex() normally preserves the final newline as an empty logical line. Do not add an extra
    # displayed line for that terminator; line numbers should match the source file exactly.
    if content.endswith("\n") and rendered and not rendered[-1]:
        rendered.pop()
    return ["".join(parts) or " " for parts in rendered]


_TYPE_LIKE_KINDS = {
    "class",
    "struct",
    "union",
    "enum",
    "trait",
    "protocol",
    "type_alias",
    "concept",
}

_CLASS_LIKE_KINDS = {"class", "struct", "derived_type", "union", "trait", "protocol"}


def _preferred_type_target(name: str, entity: ApiEntity, graph: ApiGraph) -> ApiEntity | None:
    candidates = [
        candidate
        for candidate in graph.entities.values()
        if candidate.kind in _TYPE_LIKE_KINDS and candidate.name == name
    ]
    if not candidates:
        return None
    if entity.parent:
        same_parent = [candidate for candidate in candidates if candidate.parent == entity.parent]
        if len(same_parent) == 1:
            return same_parent[0]
    return candidates[0] if len(candidates) == 1 else None


def _embedded_member_parent(entity: ApiEntity, graph: ApiGraph) -> ApiEntity | None:
    if not entity.parent or entity.parent not in graph.entities:
        return None
    parent = graph.entities[entity.parent]
    return parent if parent.kind in _CLASS_LIKE_KINDS else None


def _member_anchor(entity: ApiEntity) -> str:
    return f"member-{_slug(entity.kind)}-{_slug(entity.name)}"


def _entity_href(document_path: Path, entity: ApiEntity, graph: ApiGraph) -> str:
    parent = _embedded_member_parent(entity, graph)
    if parent is not None:
        return _relative_link(document_path, entity_document(parent)) + f"#{_member_anchor(entity)}"
    return _relative_link(document_path, entity_document(entity))


def _highlight_declaration(
    code: str,
    language: str,
    *,
    entity: ApiEntity,
    graph: ApiGraph,
    document_path: Path,
) -> str:
    """Highlight a declaration and add semantic links to known API types."""

    if lex is None or HtmlFormatter is None:
        values: list[str] = []
        for kind, value in _fallback_lex(code, language):
            token_html = _fallback_token_html(kind, value)
            stripped = value.strip()
            if kind == "name" and stripped:
                target = _preferred_type_target(stripped, entity, graph)
                if target is not None and target.id != entity.id:
                    href = _entity_href(document_path, target, graph)
                    token_html = (
                        f'<a class="cpdocs-api-signature-type" href="{html.escape(href)}">'
                        + token_html
                        + "</a>"
                    )
                elif stripped == entity.name:
                    token_html = f'<span class="cpdocs-api-signature-name">{token_html}</span>'
            values.append(token_html)
        return "".join(values)

    lexer = _pygments_lexer(language)
    if lexer is None:
        return html.escape(code)

    formatter = HtmlFormatter(noclasses=True, style="friendly")
    values: list[str] = []
    tokens = list(lex(code, lexer))
    if tokens and tokens[-1][1] == "\n":
        tokens.pop()
    for token_type, value in tokens:
        if not value:
            continue
        style = _token_style(formatter, token_type)
        escaped = html.escape(value)
        token_html = (
            f'<span style="{html.escape(style, quote=True)}">{escaped}</span>' if style else escaped
        )

        stripped = value.strip()
        if stripped and re.fullmatch(r"[A-Za-z_]\w*", stripped):
            target = _preferred_type_target(stripped, entity, graph)
            if target is not None and target.id != entity.id:
                href = _entity_href(document_path, target, graph)
                token_html = (
                    f'<a class="cpdocs-api-signature-type" href="{html.escape(href)}">'
                    + token_html
                    + "</a>"
                )
            elif stripped == entity.name:
                token_html = f'<span class="cpdocs-api-signature-name">{token_html}</span>'
        values.append(token_html)
    return "".join(values)


def _parameter_spelling(signature: ApiSignature, language: str) -> str:
    if language != "python":
        values: list[str] = []
        for parameter in signature.parameters:
            value = parameter.type or parameter.name
            if parameter.name and parameter.type:
                value += f" {parameter.name}"
            if parameter.default is not None:
                value += f" = {parameter.default}"
            values.append(value)
        return ", ".join(values)

    values: list[str] = []
    parameters = list(signature.parameters)
    positional_only = [item for item in parameters if item.kind == "positional-only"]
    has_var_positional = any(item.kind == "var-positional" for item in parameters)
    keyword_marker_emitted = False
    for index, parameter in enumerate(parameters):
        if (
            parameter.kind == "keyword-only"
            and not has_var_positional
            and not keyword_marker_emitted
        ):
            values.append("*")
            keyword_marker_emitted = True
        prefix = ""
        if parameter.kind == "var-positional":
            prefix = "*"
            keyword_marker_emitted = True
        elif parameter.kind == "var-keyword":
            prefix = "**"
        value = prefix + parameter.name
        if parameter.type:
            value += f": {parameter.type}"
        if parameter.default is not None:
            value += f" = {parameter.default}"
        values.append(value)
        if positional_only and index + 1 == len(positional_only):
            values.append("/")
    return ", ".join(values)


def _with_template(template: str, declaration: str) -> str:
    return f"{template}\n{declaration}" if template else declaration


def _signature_spelling(entity: ApiEntity, signature: ApiSignature) -> str:
    return _with_template(signature.template, _plain_signature_spelling(entity, signature))


def _plain_signature_spelling(entity: ApiEntity, signature: ApiSignature) -> str:
    attribute_spellings = list(
        dict.fromkeys(attribute.spelling for attribute in signature.attributes if attribute.spelling)
    )
    attribute_prefix = " ".join(attribute_spellings)
    if signature.spelling:
        return f"{attribute_prefix} {signature.spelling}".strip()
    parameters = _parameter_spelling(signature, entity.language)
    if entity.language == "python":
        prefix = "async def" if "async" in signature.qualifiers else "def"
        value = f"{prefix} {entity.qualified_name}({parameters})"
        if signature.returns:
            value += f" -> {signature.returns}"
        return value
    if entity.language == "rust":
        modifiers = [value for value in entity.properties if value != "pub"]
        prefix = "pub " + ((" ".join(modifiers) + " ") if modifiers else "")
        value = f"{prefix}fn {entity.qualified_name}({parameters})"
        if signature.returns:
            value += f" -> {signature.returns}"
        return value
    prefix_values = [
        value
        for value in entity.properties
        if value in {"inline", "constexpr", "consteval", "static", "virtual"}
    ]
    prefix = (" ".join(prefix_values) + " ") if prefix_values else ""
    result = (signature.returns + " ") if signature.returns else ""
    suffix_values = [value for value in signature.qualifiers if value not in prefix_values]
    suffix = (" " + " ".join(suffix_values)) if suffix_values else ""
    declaration = f"{prefix}{result}{entity.qualified_name}({parameters}){suffix}".strip()
    return f"{attribute_prefix} {declaration}".strip()


def _entity_declaration(entity: ApiEntity) -> str:
    if entity.language == "python":
        if entity.kind in {"class", "protocol"}:
            bases = f"({', '.join(entity.bases)})" if entity.bases else ""
            return f"class {entity.qualified_name}{bases}"
        if entity.kind in {"module", "package"}:
            return f"module {entity.qualified_name}"
        if entity.kind == "type_alias":
            target = next((value[2:] for value in entity.properties if value.startswith("= ")), "")
            return f"{entity.qualified_name} = {target}".rstrip()
        if entity.kind in {"attribute", "variable", "constant", "property"}:
            type_name = next(
                (
                    value
                    for value in entity.properties
                    if not value.startswith("=") and value not in {"property"}
                ),
                "",
            )
            assigned = next(
                (value[2:] for value in entity.properties if value.startswith("= ")), ""
            )
            value = entity.qualified_name + (f": {type_name}" if type_name else "")
            return value + (f" = {assigned}" if assigned else "")
        return entity.qualified_name

    if entity.language == "rust":
        prefix = "pub " if "pub" in entity.properties else ""
        keyword = {
            "struct": "struct",
            "enum": "enum",
            "trait": "trait",
            "module": "mod",
            "type_alias": "type",
            "constant": "const",
        }.get(entity.kind, entity.kind)
        return f"{prefix}{keyword} {entity.qualified_name}".strip()

    if entity.declaration:
        return entity.declaration
    return _with_template(entity.template, _cpp_declaration(entity))


def _cpp_declaration(entity: ApiEntity) -> str:
    if entity.kind == "namespace":
        return f"namespace {entity.qualified_name}"
    if entity.kind in {"class", "struct", "union"}:
        bases = f" : {', '.join(entity.bases)}" if entity.bases else ""
        return f"{entity.kind} {entity.qualified_name}{bases}"
    if entity.kind == "enum":
        scoped = " class" if "scoped" in entity.properties else ""
        return f"enum{scoped} {entity.qualified_name}"
    if entity.kind == "type_alias":
        target = next((value[2:] for value in entity.properties if value.startswith("= ")), "")
        return f"using {entity.qualified_name} = {target}".rstrip()
    if entity.kind in {"attribute", "variable", "constant"}:
        type_name = next((value for value in entity.properties if not value.startswith("=")), "")
        value = next((value[2:] for value in entity.properties if value.startswith("= ")), "")
        return f"{type_name} {entity.qualified_name}".strip() + (f" = {value}" if value else "")
    if entity.kind == "concept":
        return f"concept {entity.qualified_name}"
    if entity.kind == "macro" and entity.signatures:
        return entity.signatures[0].spelling or entity.name
    return entity.qualified_name


def _paragraphs(text: str) -> str:
    if not text.strip():
        return '<p class="cpdocs-api-undocumented">No API documentation has been provided.</p>'
    return "\n".join(
        f"<p>{html.escape(paragraph.strip())}</p>"
        for paragraph in re.split(r"\n\s*\n", text.strip())
        if paragraph.strip()
    )


def _feature_set_anchor(name: str) -> str:
    return "feature-set-" + _slug(name)


def _resolve_related_entity(reference: str, entity: ApiEntity, graph: ApiGraph) -> ApiEntity | None:
    normalized = reference.strip()
    if not normalized:
        return None

    if "::" in normalized or "." in normalized:
        for candidate in graph.entities.values():
            if candidate.qualified_name == normalized or candidate.name == normalized:
                return candidate

    if entity.parent and entity.parent in graph.entities:
        parent = graph.entities[entity.parent]
        for child_id in parent.children:
            child = graph.entities[child_id]
            if child.name == normalized:
                return child

    matches = [candidate for candidate in graph.entities.values() if candidate.name == normalized]
    return matches[0] if len(matches) == 1 else None


def _documentation_blocks(
    entity: ApiEntity, graph: ApiGraph
) -> tuple[str, list[tuple[str, ApiEntity | None]]]:
    related_names = list(entity.related)
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", entity.documentation.strip()):
        paragraph = block.strip()
        if not paragraph:
            continue
        if paragraph.startswith("CPDOCS-API-RELATES-TO:"):
            payload = paragraph.split(":", 1)[1]
            for item in re.split(r"\s*,\s*", payload.strip()):
                if item and item not in related_names:
                    related_names.append(item)
            continue
        paragraphs.append(paragraph)
    text = "\n\n".join(paragraphs)
    related = [(name, _resolve_related_entity(name, entity, graph)) for name in related_names]
    return _paragraphs(text), related


def _feature_set_display_name(name: str) -> str:
    if name.casefold() in {"cpu", "cuda", "hip", "mpi", "sycl"}:
        return name.upper()
    return name


def _member_summary_spelling(entity: ApiEntity) -> str:
    if entity.kind in {"attribute", "variable", "constant"}:
        type_name = next((value for value in entity.properties if not value.startswith("=")), "")
        value = next((value[2:] for value in entity.properties if value.startswith("= ")), "")
        if entity.language == "python":
            result = entity.name + (f": {type_name}" if type_name else "")
            return result + (f" = {value}" if value else "")
        return f"{type_name} {entity.name}".strip() + (f" = {value}" if value else "")
    if entity.kind == "type_alias":
        target = next((value[2:] for value in entity.properties if value.startswith("= ")), "")
        if entity.language == "python":
            return f"{entity.name} = {target}".rstrip()
        return _with_template(entity.template, f"using {entity.name} = {target}".rstrip())
    if entity.kind in {"class", "struct", "derived_type", "union", "enum", "trait", "protocol"}:
        return f"{entity.kind} {entity.name}"
    return entity.name


def _relative_link(source: Path, target: Path) -> str:
    import posixpath

    def output_directory(document: Path) -> Path:
        if document.name == "index.md":
            return document.parent
        return document.with_suffix("")

    source_dir = output_directory(source)
    target_dir = output_directory(target)
    value = posixpath.relpath(target_dir.as_posix(), source_dir.as_posix())
    return "./" if value == "." else value.rstrip("/") + "/"


def _kind_marker(kind: str) -> str:
    return {
        "namespace": "N",
        "module": "M",
        "package": "P",
        "class": "C",
        "struct": "S",
        "derived_type": "T",
        "union": "U",
        "enum": "E",
        "trait": "T",
        "protocol": "P",
        "function": "F",
        "subroutine": "F",
        "method": "F",
        "constructor": "F",
        "type_alias": "T",
        "variable": "V",
        "attribute": "A",
        "property": "P",
        "constant": "C",
        "macro": "D",
        "concept": "K",
        "deduction_guide": "G",
    }.get(kind, "·")
