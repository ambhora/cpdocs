# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Loading ``cpdocs.yml``.

The configuration tells cpdocs how to ask the project for its feature sets, how to build one
selected feature set, and which Git versions to document. Project structure remains owned by the
build system and is communicated through JSON manifests.

``cpdocs.yml`` is read as Korml, the JSON-shaped subset of YAML: mappings, sequences and text
scalars, without anchors, aliases, tags, complex keys or duplicate keys. Every scalar arrives as
text and this module decodes it, so ``1.10`` stays ``"1.10"`` instead of becoming the float 1.1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import korml

CONTRACT_VERSION = 3
DEFAULT_CONFIG = Path("docs/cpdocs.yml")
_CHECK_LEVELS = {"ignore", "warn", "fail"}

# The colours a theme may set, one set per colour scheme of the API site.
THEME_SCHEMES = ("light", "dark")
THEME_COLORS = ("accent", "accent-2", "on-accent", "background", "foreground", "muted", "border", "soft", "selected")
_HEX_COLOR = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")
_IMAGE_SUFFIXES = (".svg", ".png", ".ico", ".webp", ".jpg", ".jpeg", ".gif")


@dataclass(frozen=True)
class SiteTheme:
    """Presentation of the API site: logo, favicon, colours and an extra stylesheet.

    Paths are absolute and point into the current checkout, so every documented version is
    presented the same way. ``colors`` maps a scheme in ``THEME_SCHEMES`` to the colours it sets,
    each a name in ``THEME_COLORS`` with a hexadecimal value.
    """

    logo: Path | None = None
    favicon: Path | None = None
    stylesheet: Path | None = None
    colors: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class CpdocsConfig:
    config_file: Path
    project_root: Path
    feature_sets: str
    build: str
    language_configurations: tuple[dict[str, Any], ...]
    versions: tuple[str, ...]
    index: Path | None
    copyright: str | None
    project_docs: str
    theme: SiteTheme
    hide_cpp_namespaces: tuple[str, ...]
    hide_private_python: bool
    check_undocumented: str
    check_broken_references: str


def project_root_for(config_file: Path) -> Path:
    """Return the repository root for a configuration file."""

    parent = config_file.resolve().parent
    return parent.parent if parent.name == "docs" else parent


def _mapping(value: object, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RuntimeError(f"cpdocs.yml: {name} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _strings(value: object, name: str, *, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    if value is None:
        return default
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise RuntimeError(f"cpdocs.yml: {name} must be a list of non-empty strings")
    result = tuple(item.strip() for item in value)
    if len(set(result)) != len(result):
        raise RuntimeError(f"cpdocs.yml: {name} must not contain duplicates")
    return result


def _versions(value: object) -> tuple[str, ...]:
    versions = _strings(value, "versions", default=("main",))
    if not versions:
        raise RuntimeError("cpdocs.yml: versions must contain at least one version")
    return versions


def _choice(value: object, name: str, allowed: set[str], default: str) -> str:
    result = str(value if value is not None else default)
    if result not in allowed:
        raise RuntimeError(f"cpdocs.yml: {name} must be one of {', '.join(sorted(allowed))}")
    return result


def _command(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"cpdocs.yml: {name} must be a non-empty command string")
    return value.strip()


def _theme_file(value: object, name: str, root: Path, *, suffixes: tuple[str, ...]) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"cpdocs.yml: {name} must be a path relative to the project root")
    path = (root / value.strip()).resolve()
    if not path.is_file():
        raise RuntimeError(f"cpdocs.yml: {name} does not exist: {path}")
    if path.suffix.lower() not in suffixes:
        raise RuntimeError(f"cpdocs.yml: {name} must be one of {', '.join(suffixes)} files")
    return path


def _theme_colors(value: object) -> dict[str, dict[str, str]]:
    schemes = _mapping(value, "site.theme.colors")
    unknown = sorted(set(schemes) - set(THEME_SCHEMES))
    if unknown:
        raise RuntimeError(f"cpdocs.yml: unknown site.theme.colors schemes: {', '.join(unknown)}")
    result: dict[str, dict[str, str]] = {}
    for scheme in THEME_SCHEMES:
        if scheme not in schemes:
            continue
        colors = _mapping(schemes[scheme], f"site.theme.colors.{scheme}")
        unknown = sorted(set(colors) - set(THEME_COLORS))
        if unknown:
            raise RuntimeError(f"cpdocs.yml: unknown site.theme.colors.{scheme} colours: {', '.join(unknown)}")
        for name, color in colors.items():
            # An unquoted "#266c7c" starts a comment, so the value must be quoted.
            if not isinstance(color, str) or not _HEX_COLOR.fullmatch(color):
                raise RuntimeError(
                    f"cpdocs.yml: site.theme.colors.{scheme}.{name} must be a quoted hexadecimal "
                    'colour such as "#2f62b5"'
                )
        result[scheme] = {name: colors[name].lower() for name in THEME_COLORS if name in colors}
    return result


def _theme(value: object, root: Path) -> SiteTheme:
    theme = _mapping(value, "site.theme")
    unknown = sorted(set(theme) - {"logo", "favicon", "stylesheet", "colors"})
    if unknown:
        raise RuntimeError(f"cpdocs.yml: unknown site.theme keys: {', '.join(unknown)}")
    logo = _theme_file(theme.get("logo"), "site.theme.logo", root, suffixes=_IMAGE_SUFFIXES)
    favicon = _theme_file(theme.get("favicon"), "site.theme.favicon", root, suffixes=_IMAGE_SUFFIXES)
    return SiteTheme(
        logo=logo,
        # The logo is usually the project's icon, which also serves as its favicon.
        favicon=favicon if favicon is not None else logo,
        stylesheet=_theme_file(theme.get("stylesheet"), "site.theme.stylesheet", root, suffixes=(".css",)),
        colors=_theme_colors(theme.get("colors")),
    )


def _keyso_integers(value: object, name: str) -> Any:
    """Decode the integer bounds of Keyso ``_interval`` operators; every other scalar stays text.

    Korml scalars are text, and Keyso needs integers only for ``_interval``. Values that become
    placeholders are text either way.
    """

    if isinstance(value, list):
        return [_keyso_integers(item, f"{name}[{index}]") for index, item in enumerate(value)]
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, child in value.items():
        if key == "_interval" and isinstance(child, dict):
            bounds: dict[str, Any] = {}
            for bound, text in child.items():
                if not isinstance(text, str) or not re.fullmatch(r"[+-]?[0-9]+", text):
                    raise RuntimeError(f"cpdocs.yml: {name}._interval.{bound} must be an integer")
                bounds[bound] = int(text)
            result[key] = bounds
        else:
            result[key] = _keyso_integers(child, f"{name}.{key}")
    return result


def _language_configurations(raw: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Expand the optional Keyso language space, preserving the original default build."""

    if "languages" not in raw:
        return ({},)
    expression = _keyso_integers(_mapping(raw["languages"], "languages"), "languages")
    try:
        import keyso
    except ImportError as error:
        raise RuntimeError("cpdocs.yml: languages requires the keyso package") from error
    try:
        configurations = keyso.expand(expression)
    except Exception as error:
        raise RuntimeError(f"cpdocs.yml: invalid languages Keyso space: {error}") from error
    if not configurations:
        raise RuntimeError("cpdocs.yml: languages must expand to at least one configuration")
    if not all(isinstance(configuration, dict) for configuration in configurations):
        raise RuntimeError("cpdocs.yml: languages must expand to dictionaries")
    return tuple(configurations)


def _read(config_file: Path) -> dict[str, Any]:
    """Read the single Korml document of ``config_file`` as a mapping of text scalars."""

    try:
        documents = korml.load(config_file).to_builtin()
    except korml.KormlError as error:
        raise RuntimeError(f"cpdocs.yml: {error}") from error
    if len(documents) > 1:
        raise RuntimeError("cpdocs.yml: the configuration must be a single document")
    raw = documents[0] if documents else {}
    if not isinstance(raw, dict):
        raise RuntimeError("cpdocs.yml: top level must be a mapping")
    return raw


def load_config(path: Path | str = DEFAULT_CONFIG) -> CpdocsConfig:
    config_file = Path(path).expanduser().resolve()
    if not config_file.is_file():
        raise RuntimeError(f"cpdocs configuration does not exist: {config_file}")
    raw = _read(config_file)
    if raw.get("contract") != str(CONTRACT_VERSION):
        raise RuntimeError(f"cpdocs.yml: contract must be {CONTRACT_VERSION}, found {raw.get('contract')!r}")
    known = {"contract", "build", "languages", "versions", "site", "api", "checks"}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise RuntimeError(f"cpdocs.yml: unknown top-level keys: {', '.join(unknown)}")

    root = project_root_for(config_file)
    build = _mapping(raw.get("build"), "build")
    unknown_build = sorted(set(build) - {"feature-sets", "build"})
    if unknown_build:
        raise RuntimeError(f"cpdocs.yml: unknown build keys: {', '.join(unknown_build)}")
    site = _mapping(raw.get("site"), "site")
    api = _mapping(raw.get("api"), "api")
    hide = _mapping(api.get("hide"), "api.hide")
    checks = _mapping(raw.get("checks"), "checks")

    index_value = site.get("index")
    index = (root / str(index_value)).resolve() if index_value else root / "docs" / "api" / "index.md"
    copyright_value = site.get("copyright")

    return CpdocsConfig(
        config_file=config_file,
        project_root=root,
        feature_sets=_command(build.get("feature-sets"), "build.feature-sets"),
        build=_command(build.get("build"), "build.build"),
        language_configurations=_language_configurations(raw),
        versions=_versions(raw.get("versions")),
        index=index if index.is_file() else None,
        copyright=str(copyright_value) if copyright_value is not None else None,
        project_docs=str(site.get("project-docs") or "auto"),
        theme=_theme(site.get("theme"), root),
        hide_cpp_namespaces=_strings(hide.get("cpp-namespaces"), "api.hide.cpp-namespaces"),
        hide_private_python=_choice(
            hide.get("python-modules"), "api.hide.python-modules", {"private", "none"}, "private"
        )
        == "private",
        check_undocumented=_choice(checks.get("undocumented"), "checks.undocumented", _CHECK_LEVELS, "ignore"),
        check_broken_references=_choice(
            checks.get("broken-references"), "checks.broken-references", _CHECK_LEVELS, "warn"
        ),
    )
