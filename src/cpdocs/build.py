# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Build operations: enumerate feature sets, build each one, extract, merge and render.

Output layout below ``<output>/cpdocs``::

    current/            API site of the working tree (``cpdocs build``)
    versions/           versioned API site (``cpdocs versions``), one directory per ref
    work/<ref>/         requests, manifests and build directories handed to the build system
"""

from __future__ import annotations

import dataclasses
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from .config import CpdocsConfig
from .contract import ContractError, UnitManifest
from .languages import rendering_for
from .languages.cpp.extract import extract_clang_graph
from .languages.fortran.extract import extract_fortran_graph
from .languages.python.extract import build_python_graph
from .languages.rust.extract import build_rust_graph
from .model import ApiGraph, merge_graphs, relative_source_path
from .providers.contract import discover_feature_sets, resolve_manifest
from .rendering.html import render_html_site
from .versioning import SelectedRef, current_branch, select_refs


@dataclasses.dataclass(frozen=True)
class Layout:
    """Published and temporary directories used by cpdocs."""

    root: Path
    work_root: Path

    @classmethod
    def for_output(cls, output: Path, *, tmp_directory: Path | None = None) -> Layout:
        root = (output / "cpdocs").resolve()
        work_root = (tmp_directory.resolve() / "cpdocs" if tmp_directory else root)
        return cls(root=root, work_root=work_root)

    @property
    def current(self) -> Path:
        return self.root / "current"

    @property
    def versions(self) -> Path:
        return self.root / "versions"

    def work(self, ref: str) -> Path:
        return self.work_root / "work" / ref.replace("/", "__")



# --------------------------------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------------------------------


def _clang() -> str:
    for candidate in (os.environ.get("CPDOCS_CLANG"), "clang++", "clang"):
        if candidate and shutil.which(candidate):
            return candidate
    raise RuntimeError(
        "cpdocs needs clang to document C and C++ units; put clang++ on PATH "
        "(or name it in CPDOCS_CLANG)"
    )


def _browse_logical_path(
    path: Path, *, project_root: Path, unit: UnitManifest, category: str, root: Path
) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except (OSError, ValueError):
        # Keep a stable internal key for files outside the checkout. This path is not presented to
        # readers; rendering uses the semantic layout recorded in ``source_display_paths``.
        base = Path("_generated") / unit.id / category
        try:
            relative = (
                path.resolve().relative_to(root.resolve()) if root.is_dir() else Path(path.name)
            )
        except (OSError, ValueError):
            relative = Path(path.name)
        return (base / relative).as_posix()


def _semantic_display_path(path: Path, *, root: Path, generated: bool) -> str:
    """Return the compiler-facing layout path shown in the file browser.

    Manifest roots are semantic roots. A file below ``.../src/cuda/include`` is therefore shown
    below ``include`` and a file below ``.../src/cuda/lib`` below ``lib``. Build-generated roots
    use the same flattened layout under one ``_generated`` prefix.
    """

    try:
        if root.is_dir():
            relative = path.resolve().relative_to(root.resolve())
            root_name = root.name
        else:
            relative = Path(path.name)
            root_name = root.parent.name
    except (OSError, ValueError):
        relative = Path(path.name)
        root_name = root.name if root.name != path.name else root.parent.name

    base = Path("_generated") if generated else Path()
    if root_name:
        base /= root_name
    return (base / relative).as_posix()


def _api_display_paths(
    unit: UnitManifest, graph: ApiGraph, *, project_root: Path
) -> dict[str, str]:
    """Map API source keys to their semantic include/module layout."""

    values: dict[str, str] = {}
    for api_root in unit.api:
        root = api_root.path
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                root_relative = path.resolve().relative_to(root.resolve()).as_posix()
            except (OSError, ValueError):
                root_relative = path.name
            project_relative = relative_source_path(path, project_root)
            logical = next(
                (candidate for candidate in (root_relative, project_relative) if candidate in graph.sources),
                None,
            )
            if logical is not None:
                values.setdefault(
                    logical,
                    _semantic_display_path(
                        path, root=root, generated=unit.generated or api_root.generated
                    ),
                )
    return values


def _collect_browse_files(
    unit: UnitManifest, *, project_root: Path
) -> tuple[dict[str, str], list[str], dict[str, str]]:
    files: dict[str, str] = {}
    generated: list[str] = []
    display_paths: dict[str, str] = {}
    # Public headers are already present in ``graph.sources`` after API extraction.  These roots
    # add implementation-only material without duplicating public headers in the file hierarchy.
    groups = (
        ("sources", unit.sources),
        ("modules", unit.modules),
        ("executables", unit.executables),
    )
    for category, roots in groups:
        for root in roots:
            if root.is_file():
                candidates = [root]
            elif root.is_dir():
                candidates = sorted(root.rglob("*"))
            else:
                candidates = []
            for path in candidates:
                if not path.is_file():
                    continue
                try:
                    content = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                logical = _browse_logical_path(
                    path, project_root=project_root, unit=unit, category=category, root=root
                )
                files.setdefault(logical, content)
                display_paths.setdefault(
                    logical,
                    _semantic_display_path(path, root=root, generated=unit.generated),
                )
                if unit.generated and logical not in generated:
                    generated.append(logical)
    return files, generated, display_paths


def _generated_sources(unit: UnitManifest, graph: ApiGraph) -> list[str]:
    values: list[str] = []
    for root in unit.api:
        if not root.generated:
            continue
        for path in root.path.rglob("*"):
            if path.is_file():
                logical = path.relative_to(root.path).as_posix()
                if logical in graph.sources:
                    values.append(logical)
    return values


def extract_unit(
    unit: UnitManifest,
    *,
    project: str,
    version: str,
    project_root: Path,
    feature_set: str,
    work: Path,
    config: CpdocsConfig,
) -> ApiGraph:
    if unit.language is None:
        return ApiGraph(project=project, version=version, language="none")
    if unit.language in {"c", "cpp", "cuda", "hip"}:
        assert unit.parse is not None
        graph = extract_clang_graph(
            project=project,
            version=version,
            project_root=project_root,
            language=unit.language,
            api_roots=[root.path for root in unit.api],
            parse=unit.parse,
            feature_set=feature_set,
            clang_executable=_clang(),
            work_directory=work / "clang" / unit.id,
        )
        generated = _generated_sources(unit, graph)
        if generated:
            graph.metadata["generated_sources"] = generated
        return graph
    if unit.language == "fortran":
        roots = [root.path for root in unit.api]
        roots.extend(path for path in unit.modules if path not in roots)
        return extract_fortran_graph(
            project=project,
            version=version,
            project_root=project_root,
            api_roots=roots,
            feature_set=feature_set,
        )
    if unit.language == "python":
        assert unit.package is not None
        return build_python_graph(
            project_root=project_root,
            package_root=unit.api[0].path,
            package=unit.package,
            version=version,
            include_private=not config.hide_private_python,
        )
    if unit.language == "rust":
        assert unit.rustdoc_json is not None
        return build_rust_graph(
            rustdoc_json=unit.rustdoc_json,
            project=project,
            version=version,
            project_root=project_root,
        )
    raise ContractError(f"unsupported unit language {unit.language!r}")


def _merge_metadata(target: dict[str, object], source: dict[str, object]) -> None:
    for key, value in source.items():
        if isinstance(value, list):
            existing = target.setdefault(key, [])
            assert isinstance(existing, list)
            existing.extend(item for item in value if item not in existing)
        elif isinstance(value, dict):
            existing = target.setdefault(key, {})
            assert isinstance(existing, dict)
            for item_key, item_value in value.items():
                existing.setdefault(item_key, item_value)
        else:
            target.setdefault(key, value)


def _combine(graphs: list[ApiGraph], *, project: str, version: str, language: str) -> ApiGraph:
    """Combine the graphs of several units extracted for the same feature set."""

    combined = ApiGraph(project=project, version=version, language=language)
    for graph in graphs:
        for entity in graph.entities.values():
            combined.add(entity)
        for path, content in graph.sources.items():
            combined.sources.setdefault(path, content)
        for path, content in graph.files.items():
            combined.files.setdefault(path, content)
        _merge_metadata(combined.metadata, graph.metadata)
    combined.rebuild_children()
    return combined


def _apply_visibility(graph: ApiGraph, config: CpdocsConfig) -> None:
    patterns = config.hide_cpp_namespaces
    if not patterns:
        return
    hidden = {
        entity.id
        for entity in graph.entities.values()
        if entity.language in {"c", "cpp", "cuda", "hip"}
        and entity.kind == "namespace"
        and any(fnmatch.fnmatchcase(entity.qualified_name, pattern) for pattern in patterns)
    }
    changed = True
    while changed:
        changed = False
        for entity in graph.entities.values():
            if entity.id not in hidden and entity.parent in hidden:
                hidden.add(entity.id)
                changed = True
    for identifier in hidden:
        del graph.entities[identifier]
    graph.rebuild_children()


def _check_undocumented(graph: ApiGraph, level: str) -> None:
    if level == "ignore":
        return
    missing = sorted(
        entity.qualified_name
        for entity in graph.entities.values()
        if entity.kind not in rendering_for(entity.language).container_kinds
        and not entity.documentation.strip()
    )
    if not missing:
        return
    message = f"{len(missing)} public API entities have no documentation:\n" + "\n".join(
        f"  - {name}" for name in missing
    )
    if level == "fail":
        raise RuntimeError(message)
    print(f"cpdocs: warning: {message}", file=sys.stderr)


def build_graph(
    config: CpdocsConfig,
    *,
    source: Path,
    work: Path,
    version: str,
) -> ApiGraph:
    """Discover every feature set, build each one independently, and merge the API graphs."""

    feature_sets = discover_feature_sets(config.feature_sets, source=source, work=work)

    per_feature_set: list[tuple[str, ApiGraph]] = []
    metadata: dict[str, object] = {}
    languages: set[str] = set()
    units: dict[tuple[str, str], None] = {}

    for feature_set in feature_sets.feature_sets:
        manifest = resolve_manifest(config.build, feature_set, source=source, work=work)
        languages.update(unit.language for unit in manifest.units if unit.language is not None)
        for unit in manifest.units:
            units[(unit.id, unit.language)] = None
        feature_set_language_values = sorted(
            {unit.language for unit in manifest.units if unit.language is not None}
        )
        if len(feature_set_language_values) == 1:
            feature_set_language = feature_set_language_values[0]
        elif feature_set_language_values:
            feature_set_language = "mixed"
        else:
            feature_set_language = "none"
        unit_graphs = []
        for unit in manifest.units:
            unit_graph = extract_unit(
                unit,
                project=feature_sets.project,
                version=version,
                project_root=source,
                feature_set=feature_set.key,
                work=work / "feature-sets" / feature_set.key,
                config=config,
            )
            display_paths = unit_graph.metadata.setdefault("source_display_paths", {})
            assert isinstance(display_paths, dict)
            for path, display in _api_display_paths(unit, unit_graph, project_root=source).items():
                display_paths.setdefault(path, display)

            browse_files, generated_files, browse_display_paths = _collect_browse_files(
                unit, project_root=source
            )
            for path, content in browse_files.items():
                unit_graph.files.setdefault(path, content)
            for path, display in browse_display_paths.items():
                display_paths.setdefault(path, display)
            if generated_files:
                existing = unit_graph.metadata.setdefault("generated_files", [])
                assert isinstance(existing, list)
                existing.extend(path for path in generated_files if path not in existing)
            unit_graphs.append(unit_graph)
        graph = _combine(
            unit_graphs,
            project=feature_sets.project,
            version=version,
            language=feature_set_language,
        )
        graph.feature_sets[feature_set.key] = {
            "features": list(feature_set.features),
            "selection": feature_set.selection,
        }
        _merge_metadata(metadata, graph.metadata)
        per_feature_set.append((feature_set.key, graph))

    language_values = sorted(languages)
    if len(language_values) == 1:
        language = language_values[0]
    elif language_values:
        language = "mixed"
    else:
        language = "none"
    merged = merge_graphs(
        per_feature_set, project=feature_sets.project, version=version, language=language
    )
    metadata["feature_sets"] = [feature_set.selection for feature_set in feature_sets.feature_sets]
    sorted_units = sorted(units, key=lambda value: (value[0], value[1] or ""))
    metadata["units"] = [
        {"id": unit_id, "language": unit_language} for unit_id, unit_language in sorted_units
    ]
    metadata["generator"] = feature_sets.generator
    metadata["project_version"] = feature_sets.version
    merged.metadata = metadata

    _apply_visibility(merged, config)
    _check_undocumented(merged, config.check_undocumented)
    return merged


# --------------------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------------------


def _graph_json(graph: ApiGraph) -> str:
    return json.dumps(dataclasses.asdict(graph), indent=2, sort_keys=True, default=str) + "\n"


def _project_docs_url(graph: ApiGraph, configured: str, *, root_depth: int) -> str:
    if configured != "auto":
        return configured
    version_depth = max(1, len(PurePosixPath(graph.version).parts))
    return "../" * (root_depth + version_depth)


def _render(
    graph: ApiGraph, config: CpdocsConfig, *, output: Path, work: Path, root_depth: int
) -> None:
    work.mkdir(parents=True, exist_ok=True)
    render_html_site(
        graph,
        output_directory=output,
        project_docs_url=_project_docs_url(graph, config.project_docs, root_depth=root_depth),
        copyright_text=config.copyright or f"Copyright © {graph.project} developers",
        introduction_file=config.index,
    )
    (work / "api-graph.json").write_text(_graph_json(graph), encoding="utf-8")


def build_current(
    config: CpdocsConfig,
    *,
    output: Path,
    version: str = "main",
    project_docs_root_depth: int = 2,
    tmp_directory: Path | None = None,
) -> ApiGraph:
    """Document the working tree into ``<output>/cpdocs/current``."""

    layout = Layout.for_output(output, tmp_directory=tmp_directory)
    work = layout.work("current")
    graph = build_graph(
        config,
        source=config.project_root,
        work=work,
        version=version,
    )
    _render(
        graph,
        config,
        output=layout.current,
        work=work / "render",
        root_depth=project_docs_root_depth,
    )
    return graph


def _html_pages(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*.html"))


def _redirect_page(target: str) -> str:
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url={target}">'
        f'<link rel="canonical" href="{target}"></head>'
        f'<body><a href="{target}">{target}</a></body></html>\n'
    )


def _write_versions(output: Path, built: list[SelectedRef]) -> None:
    default_name = built[0].name if built else "main"
    metadata = {
        "default": default_name,
        "versions": [
            {
                "name": ref.name,
                "kind": ref.kind,
                "url": f"{ref.name}/",
                "pages": _html_pages(output / ref.name),
            }
            for ref in built
            if (output / ref.name / "index.html").is_file()
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "versions.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (output / "index.html").write_text(_redirect_page(default_name + "/"), encoding="utf-8")


def _git(command: list[str], *, cwd: Path) -> None:
    result = subprocess.run(
        ["git", *command],
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise RuntimeError("Git command failed:\n" + result.stdout.rstrip())


def _config_for_checkout(config: CpdocsConfig, checkout: Path) -> CpdocsConfig:
    """Use the current cpdocs policy against another checkout of the same project."""

    index = config.index
    if index is not None:
        relative = index.relative_to(config.project_root)
        moved = checkout / relative
        index = moved if moved.is_file() else None
    return dataclasses.replace(
        config,
        config_file=checkout / config.config_file.relative_to(config.project_root),
        project_root=checkout.resolve(),
        index=index,
    )


def _repository_root(project_root: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=project_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{project_root} is not inside a Git repository")
    return Path(result.stdout.strip()).resolve()


def build_versions(
    config: CpdocsConfig,
    *,
    output: Path,
    project_docs_root_depth: int = 2,
    include_working_tree: bool = False,
    tmp_directory: Path | None = None,
) -> list[str]:
    """Document the explicitly configured ``versions`` in order."""

    layout = Layout.for_output(output, tmp_directory=tmp_directory)
    project_root = config.project_root.resolve()
    subdirectory = project_root.relative_to(_repository_root(project_root))
    selected = select_refs(project_root, config.versions)

    if include_working_tree:
        checked_out = current_branch(project_root)
        if checked_out is not None:
            existing = next((ref for ref in selected if ref.name == checked_out), None)
            if existing is not None:
                selected.remove(existing)
            selected.insert(0, SelectedRef(name=checked_out, kind="worktree", checkout=None))
        elif not any(ref.checkout is None for ref in selected):
            selected.insert(0, SelectedRef(name="current", kind="worktree", checkout=None))

    shutil.rmtree(layout.versions, ignore_errors=True)
    layout.versions.mkdir(parents=True, exist_ok=True)

    built: list[SelectedRef] = []
    for ref in selected:
        temporary: tempfile.TemporaryDirectory[str] | None = None
        worktree: Path | None = None
        checkout = project_root
        if ref.checkout is not None:
            temporary = tempfile.TemporaryDirectory(prefix="cpdocs-ref-")
            worktree = Path(temporary.name) / "checkout"
            _git(["worktree", "add", "--detach", str(worktree), ref.checkout], cwd=project_root)
            checkout = worktree / subdirectory
        try:
            if not checkout.is_dir():
                raise RuntimeError(
                    f"configured version {ref.name!r} does not contain {subdirectory}"
                )
            ref_config = _config_for_checkout(config, checkout) if ref.checkout else config
            work = layout.work(ref.name)
            graph = build_graph(
                ref_config, source=checkout, work=work, version=ref.name
            )
            _render(
                graph,
                ref_config,
                output=layout.versions / ref.name,
                work=work / "render",
                root_depth=project_docs_root_depth,
            )
            built.append(ref)
        finally:
            if temporary is not None and worktree is not None:
                _git(["worktree", "remove", "--force", str(worktree)], cwd=project_root)
                temporary.cleanup()

    _write_versions(layout.versions, built)
    return [ref.name for ref in built]


def recorded_default_version(output: Path) -> str:
    """The default version recorded by the last :func:`build_versions` run."""

    metadata = Layout.for_output(output).versions / "versions.json"
    try:
        return str(json.loads(metadata.read_text(encoding="utf-8"))["default"])
    except (OSError, KeyError, json.JSONDecodeError):
        return "main"


__all__ = [
    "Layout",
    "build_current",
    "build_graph",
    "build_versions",
    "discover_feature_sets",
    "recorded_default_version",
    "resolve_manifest",
]
