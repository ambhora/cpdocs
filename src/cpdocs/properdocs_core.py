# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Framework-independent helpers used by the ProperDocs cpdocs plugin."""

from __future__ import annotations

import posixpath
import re
import shutil
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from urllib.parse import quote

_APIDOCS_REFERENCE = re.compile(
    r"@apidocs(?:\[(?P<version>[^\]]+)\])?::"
    r"(?P<symbol>[A-Za-z_](?:[A-Za-z0-9_:.]*[A-Za-z0-9_])?)"
)


def repository_provider(repo_url: str, extra: dict[str, object]) -> str:
    explicit = str(extra.get("cpdocs_repo_provider") or "").strip().lower()
    if explicit:
        return explicit
    host = repo_url.lower()
    if "github" in host:
        return "github"
    if "bitbucket" in host:
        return "bitbucket"
    return "gitlab"


def _repository_base(repo_url: str) -> str:
    value = repo_url.rstrip("/")
    return value[:-4] if value.endswith(".git") else value


def source_url(repo_url: str, provider: str, ref: str, source_path: str) -> str:
    base = _repository_base(repo_url)
    ref_part = quote(ref, safe="/")
    path_part = quote(source_path, safe="/")
    if provider == "github":
        return f"{base}/blob/{ref_part}/{path_part}"
    if provider == "bitbucket":
        return f"{base}/src/{ref_part}/{path_part}"
    return f"{base}/-/blob/{ref_part}/{path_part}"


def edit_url(repo_url: str, provider: str, ref: str, source_path: str) -> str:
    base = _repository_base(repo_url)
    ref_part = quote(ref, safe="/")
    path_part = quote(source_path, safe="/")
    if provider == "github":
        return f"{base}/edit/{ref_part}/{path_part}"
    if provider == "bitbucket":
        return f"{base}/src/{ref_part}/{path_part}?mode=edit"
    return f"{base}/-/edit/{ref_part}/{path_part}"


def default_issue_url(repo_url: str, provider: str) -> str:
    base = _repository_base(repo_url)
    return f"{base}/-/issues/new" if provider == "gitlab" else f"{base}/issues/new"


# Fenced code blocks and inline code spans show ``@apidocs`` literally; they are never rewritten.
_CODE = re.compile(
    r"^(?P<fence>`{3,}|~{3,}).*?^(?P=fence)[ \t]*$|`[^`\n]+`", re.MULTILINE | re.DOTALL
)


def api_symbol_public_path(symbol: str, version: str, mount: str) -> PurePosixPath:
    return PurePosixPath(mount) / version / "_symbols" / PurePosixPath(*re.split(r"::|\.", symbol))


def resolve_api_references(
    markdown: str,
    *,
    page_dest_uri: str,
    mount: str,
    default_version: str,
    locate: Callable[[str, str], str | None] | None = None,
    missing: list[tuple[str, str]] | None = None,
) -> str:
    """Resolve ``@apidocs`` names to links into the versioned API.

    ``locate(version, symbol)`` returns the entity's page below the version directory, such as
    ``api/demo/struct-settings/``; the link then points straight at it. Without ``locate``, or for
    symbols it does not know, the link points at the stable ``_symbols`` alias, and unknown symbols
    are appended to ``missing`` as ``(version, symbol)``.
    """

    page_directory = PurePosixPath(page_dest_uri).parent

    def href_to(target: PurePosixPath, anchor: str = "") -> str:
        relative = posixpath.relpath(target.as_posix(), page_directory.as_posix())
        return relative + "/" + (f"#{anchor}" if anchor else "")

    def replace(match: re.Match[str]) -> str:
        symbol = match.group("symbol")
        version = match.group("version") or default_version
        found = locate(version, symbol) if locate is not None else None
        if found:
            path, _, anchor = found.partition("#")
            return f"[`{symbol}`]({href_to(PurePosixPath(mount) / version / path, anchor)})"
        if locate is not None and missing is not None:
            missing.append((version, symbol))
        return f"[`{symbol}`]({href_to(api_symbol_public_path(symbol, version, mount))})"

    parts: list[str] = []
    position = 0
    for code in _CODE.finditer(markdown):
        parts.append(_APIDOCS_REFERENCE.sub(replace, markdown[position : code.start()]))
        parts.append(code.group(0))
        position = code.end()
    parts.append(_APIDOCS_REFERENCE.sub(replace, markdown[position:]))
    return "".join(parts)


_VERSIONS_DIRECTIVE = re.compile(r"^@apidocs-versions[ \t]*$", re.MULTILINE)


def expand_versions_directive(
    markdown: str, *, page_dest_uri: str, mount: str, metadata: dict[str, object]
) -> str:
    """Replace a line ``@apidocs-versions`` with a list of every published API version."""

    if not _VERSIONS_DIRECTIVE.search(markdown):
        return markdown
    page_directory = PurePosixPath(page_dest_uri).parent
    default = metadata.get("default")
    aliases = metadata.get("aliases", {})
    aliases = aliases if isinstance(aliases, dict) else {}
    lines: list[str] = []
    versions = metadata.get("versions", [])
    for entry in versions if isinstance(versions, list) else []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name"))
        target = PurePosixPath(mount) / name
        href = posixpath.relpath(target.as_posix(), page_directory.as_posix()) + "/"
        notes = [str(entry.get("kind", ""))]
        if name == default:
            notes.append("default")
        notes.extend(f"`{alias}`" for alias, value in sorted(aliases.items()) if value == name)
        lines.append(f"- [{name}]({href}) — " + ", ".join(note for note in notes if note))
    listing = "\n".join(lines) if lines else "No API version has been published."
    return _VERSIONS_DIRECTIVE.sub(lambda _match: listing, markdown)


def publish_api(source: Path, site_directory: Path, mount: str) -> Path:
    """Replace the mounted API subtree with cpdocs's complete versioned output."""

    destination = site_directory / Path(*PurePosixPath(mount).parts)
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    (site_directory / ".nojekyll").touch()
    return destination
