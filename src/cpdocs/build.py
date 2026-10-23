# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Build operations: enumerate feature sets, build each one, extract, merge and render.

Output layout below ``<output>/cpdocs``::

    current/            API site of the working tree (``cpdocs build``)
    versions/           versioned API site (``cpdocs versions``), one directory per ref
    work/<ref>/         requests, manifests and build directories handed to the build system
"""

from __future__ import annotations

import dataclasses
import fnmatch
import html
import json
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from .config import CpdocsConfig
from .contract import ContractError, UnitManifest
from .filesystem import contained_path, git_tracked_files, path_component, readable_file, remove_tree
from .languages import UnitContext, extractor_for, rendering_for
from .model import ApiGraph, merge_graphs, relative_source_path
from .providers.contract import discover_feature_sets, language_template_values, resolve_manifest
from .rendering.html import render_html_site
from .resources import shared_template
from .versioning import SelectedRef, current_branch, select_refs


@dataclasses.dataclass(frozen=True)
class Layout:
    """Published and temporary directories used by cpdocs."""

    root: Path
    work_root: Path

    @classmethod
    def for_output(cls, output: Path, *, tmp_directory: Path | None = None) -> Layout:
        """The layout below ``<output>/cpdocs``, with work directories below ``tmp_directory`` if given."""

        # The output and temporary roots are the user's choice and may be reached through links.
        # The ``cpdocs`` directory below them is not resolved: cpdocs deletes inside it, and a link
        # there must be refused rather than followed (see ``remove_tree``).
        root = output.absolute() / "cpdocs"
        work_root = tmp_directory.absolute() / "cpdocs" if tmp_directory else root
        return cls(root=root, work_root=work_root)

    @property
    def current(self) -> Path:
        """The API site of the working tree, written by ``cpdocs build``."""
        return self.root / "current"

    @property
    def versions(self) -> Path:
        """The versioned API site, one directory per documented ref, written by ``cpdocs versions``."""
        return self.root / "versions"

    def work(self, ref: str) -> Path:
        """The directory of requests, manifests and build trees handed to the build system for ``ref``."""
        return self.work_root / "work" / path_component(ref.replace("/", "__"))


# --------------------------------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------------------------------


def _browse_logical_path(path: Path, *, project_root: Path, unit: UnitManifest, category: str, root: Path) -> str:
    """The key of a browsed file: its project-relative path, or a ``_generated`` key outside the project."""

    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except (OSError, ValueError):
        # Keep a stable internal key for files outside the checkout. This path is not presented to
        # readers; rendering uses the semantic layout recorded in ``source_display_paths``. The
        # unit identifier comes from the build system and becomes a path, so it is made safe.
        base = Path("_generated") / path_component(unit.id) / category
        try:
            relative = path.resolve().relative_to(root.resolve()) if root.is_dir() else Path(path.name)
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


def _api_display_paths(unit: UnitManifest, graph: ApiGraph, *, project_root: Path) -> dict[str, str]:
    """Map the keys of extracted API sources to the paths readers see, such as ``include/demo/x.hpp``."""

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
                (candidate for candidate in (root_relative, project_relative) if candidate in graph.sources), None
            )
            if logical is not None:
                values.setdefault(
                    logical, _semantic_display_path(path, root=root, generated=unit.generated or api_root.generated)
                )
    return values


def _collect_browse_files(
    unit: UnitManifest, *, project_root: Path, tracked: frozenset[Path] | None
) -> tuple[dict[str, str], list[str], dict[str, str]]:
    """Read the implementation sources a unit declares for the source browser.

    Everything returned here is published. A file is read only if, after following symbolic
    links, it lies below its declared root or the project. Inside the project, a unit that is not
    marked ``generated`` publishes only files Git tracks (``tracked``; ``None`` outside Git), so
    untracked local files such as credentials are not published.
    """

    project = project_root.resolve()
    files: dict[str, str] = {}
    generated: list[str] = []
    display_paths: dict[str, str] = {}
    # Public headers are already present in ``graph.sources`` after API extraction.  These roots
    # add implementation-only material without duplicating public headers in the file hierarchy.
    groups = (("sources", unit.sources), ("modules", unit.modules), ("executables", unit.executables))
    for category, roots in groups:
        for root in roots:
            if root.is_file():
                candidates = [root]
            elif root.is_dir():
                candidates = sorted(root.rglob("*"))
            else:
                candidates = []
            for path in candidates:
                if not readable_file(path, (root, project_root)):
                    continue
                resolved = path.resolve()
                if (
                    tracked is not None
                    and not unit.generated
                    and resolved.is_relative_to(project)
                    and resolved not in tracked
                ):
                    continue
                try:
                    content = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                logical = _browse_logical_path(path, project_root=project_root, unit=unit, category=category, root=root)
                files.setdefault(logical, content)
                display_paths.setdefault(logical, _semantic_display_path(path, root=root, generated=unit.generated))
                if unit.generated and logical not in generated:
                    generated.append(logical)
    return files, generated, display_paths


def extract_unit(unit: UnitManifest, context: UnitContext) -> ApiGraph:
    """Extract the API graph of one manifest unit with the extractor of its language.

    A unit without a language only contributes files to the source browser, so its graph is empty.
    """

    if unit.language is None:
        return ApiGraph(project=context.project, version=context.version, language="none")
    try:
        extractor = extractor_for(unit.language)
    except ValueError as error:
        raise ContractError(f"unsupported unit language {unit.language!r}") from error
    return extractor(unit, context)


def _merge_metadata(target: dict[str, object], source: dict[str, object]) -> None:
    """Merge graph metadata into ``target``: lists are united, mappings and scalars keep the first value."""

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


def _graph_language(languages: set[str]) -> str:
    """The language recorded on a graph: its one unit language, ``mixed`` or ``none``."""

    if len(languages) == 1:
        return next(iter(languages))
    return "mixed" if languages else "none"


def _combine_unit_graphs(graphs: list[ApiGraph], *, project: str, version: str, language: str) -> ApiGraph:
    """Combine the graphs of the units of one feature set into the graph of that feature set."""

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


def _hide_configured_namespaces(graph: ApiGraph, config: CpdocsConfig) -> None:
    """Remove the C-family namespaces matching ``api.hide.cpp-namespaces``, with everything inside them."""

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


def _report_undocumented(graph: ApiGraph, level: str) -> None:
    """Warn about or fail on entities without documentation, as ``checks.undocumented`` asks.

    Containers such as namespaces and modules are exempt: they are often only documented once.
    """

    if level == "ignore":
        return
    missing = sorted(
        entity.qualified_name
        for entity in graph.entities.values()
        if entity.kind not in rendering_for(entity.language).container_kinds and not entity.documentation.strip()
    )
    if not missing:
        return
    message = f"{len(missing)} public API entities have no documentation:\n" + "\n".join(
        f"  - {name}" for name in missing
    )
    if level == "fail":
        raise RuntimeError(message)
    print(f"cpdocs: warning: {message}", file=sys.stderr)


def _document_unit(unit: UnitManifest, context: UnitContext, *, tracked: frozenset[Path] | None) -> ApiGraph:
    """Extract one unit and add the implementation files it declares for the source browser."""

    graph = extract_unit(unit, context)
    source = context.project_root
    display_paths = graph.metadata.setdefault("source_display_paths", {})
    assert isinstance(display_paths, dict)
    for path, display in _api_display_paths(unit, graph, project_root=source).items():
        display_paths.setdefault(path, display)

    files, generated_files, file_display_paths = _collect_browse_files(unit, project_root=source, tracked=tracked)
    for path, content in files.items():
        graph.files.setdefault(path, content)
    for path, display in file_display_paths.items():
        display_paths.setdefault(path, display)
    if generated_files:
        existing = graph.metadata.setdefault("generated_files", [])
        assert isinstance(existing, list)
        existing.extend(path for path in generated_files if path not in existing)
    return graph


def build_graph(config: CpdocsConfig, *, source: Path, work: Path, version: str) -> ApiGraph:
    """Document one checkout: the API of every build variant, merged into one graph.

    For every concrete language configuration, the ``build.feature-sets`` hook lists the variants
    of the project. The ``build.build`` hook then builds each variant and describes its units, and
    each unit is extracted with its language's extractor. The graphs of all variants are merged, so
    every entity records the variants and language configurations it exists in.
    """

    per_feature_set: list[tuple[str, ApiGraph]] = []
    metadata: dict[str, object] = {}
    languages: set[str] = set()
    units: dict[tuple[str, str], None] = {}
    configuration_options: dict[str, list[dict[str, object]]] = {}
    all_feature_selections: list[dict[str, object]] = []
    project: str | None = None
    project_version = ""
    generator = ""
    multiple_languages = len(config.language_configurations) > 1
    tracked = git_tracked_files(source)

    for index, configuration in enumerate(config.language_configurations, 1):
        template_values = language_template_values(configuration)
        # Preserve the existing work directory layout for projects with a single configuration.
        language_work = work / "language-configurations" / f"language-{index:03d}" if multiple_languages else work
        feature_sets = discover_feature_sets(
            config.feature_sets, source=source, work=language_work, template_values=template_values
        )
        if project is None:
            project = feature_sets.project
            project_version = feature_sets.version
            generator = feature_sets.generator
        elif project != feature_sets.project:
            raise RuntimeError(
                f"build.feature-sets returned inconsistent projects: {project!r} and {feature_sets.project!r}"
            )

        for feature_set in feature_sets.feature_sets:
            key = f"language-{index:03d}--{feature_set.key}" if multiple_languages else feature_set.key
            manifest = resolve_manifest(
                config.build, feature_set, source=source, work=language_work, template_values=template_values
            )
            if manifest.options:
                configuration_options[key] = [dict(option) for option in manifest.options]
            unit_languages = {unit.language for unit in manifest.units if unit.language is not None}
            languages.update(unit_languages)
            for unit in manifest.units:
                units[(unit.id, unit.language)] = None
            unit_work = language_work / "feature-sets" / feature_set.key / "units"
            unit_graphs = [
                _document_unit(
                    unit,
                    UnitContext(
                        project=feature_sets.project,
                        version=version,
                        project_root=source,
                        feature_set=key,
                        work_directory=unit_work / path_component(unit.id),
                        language_configuration=configuration,
                        config=config,
                    ),
                    tracked=tracked,
                )
                for unit in manifest.units
            ]
            graph = _combine_unit_graphs(
                unit_graphs, project=feature_sets.project, version=version, language=_graph_language(unit_languages)
            )
            graph.feature_sets[key] = {
                "features": list(feature_set.features),
                "selection": feature_set.selection,
                "languages": configuration,
            }
            _merge_metadata(metadata, graph.metadata)
            per_feature_set.append((key, graph))
            all_feature_selections.append(feature_set.selection)

    merged = merge_graphs(per_feature_set, project=project or "", version=version, language=_graph_language(languages))
    metadata["feature_sets"] = all_feature_selections
    metadata["language_configurations"] = list(config.language_configurations)
    sorted_units = sorted(units, key=lambda value: (value[0], value[1] or ""))
    metadata["units"] = [{"id": unit_id, "language": unit_language} for unit_id, unit_language in sorted_units]
    if configuration_options:
        metadata["configuration_options"] = configuration_options
    metadata["generator"] = generator
    metadata["project_version"] = project_version
    merged.metadata = metadata

    _hide_configured_namespaces(merged, config)
    _report_undocumented(merged, config.check_undocumented)
    return merged


# --------------------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------------------


def _graph_as_json(graph: ApiGraph) -> str:
    """The API graph as JSON, written next to the rendered site for inspection and debugging."""

    return json.dumps(dataclasses.asdict(graph), indent=2, sort_keys=True, default=str) + "\n"


def _project_docs_url(graph: ApiGraph, configured: str, *, root_depth: int) -> str:
    """The link to the project website: ``site.project-docs``, or for ``auto`` the relative path up to it."""

    if configured != "auto":
        return configured
    version_depth = max(1, len(PurePosixPath(graph.version).parts))
    return "../" * (root_depth + version_depth)


def _render_version(graph: ApiGraph, config: CpdocsConfig, *, output: Path, work: Path, root_depth: int) -> None:
    """Render the API site of one version into ``output`` and keep its graph as JSON in ``work``."""

    work.mkdir(parents=True, exist_ok=True)
    render_html_site(
        graph,
        output_directory=output,
        project_docs_url=_project_docs_url(graph, config.project_docs, root_depth=root_depth),
        copyright_text=config.copyright or f"Copyright © {graph.project} developers",
        introduction_file=config.index,
        theme=config.theme,
    )
    (work / "api-graph.json").write_text(_graph_as_json(graph), encoding="utf-8")


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
    graph = build_graph(config, source=config.project_root, work=work, version=version)
    _render_version(graph, config, output=layout.current, work=work / "render", root_depth=project_docs_root_depth)
    return graph


def _html_page_paths(root: Path) -> list[str]:
    """Every HTML page of a rendered version, relative to it, for the version switcher."""

    if not root.is_dir():
        return []
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*.html"))


def _redirect_page(target: str) -> str:
    """An HTML page that sends the reader on to ``target``."""

    return shared_template("api/versions-redirect.html").substitute(target=html.escape(target, quote=True))


def _write_version_index(output: Path, built: list[SelectedRef]) -> None:
    """Write ``versions.json`` and the redirect to the default version, the first one built."""

    default_name = built[0].name if built else "main"
    metadata = {
        "default": default_name,
        "versions": [
            {"name": ref.name, "kind": ref.kind, "url": f"{ref.name}/", "pages": _html_page_paths(output / ref.name)}
            for ref in built
            if (output / ref.name / "index.html").is_file()
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "versions.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (output / "index.html").write_text(_redirect_page(default_name + "/"), encoding="utf-8")


def _run_git(command: list[str], *, cwd: Path) -> None:
    """Run a Git command in ``cwd`` and raise with its output if it fails."""

    result = subprocess.run(
        ["git", *command], cwd=cwd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if result.returncode != 0:
        raise RuntimeError("Git command failed:\n" + result.stdout.rstrip())


def _config_for_checkout(config: CpdocsConfig, checkout: Path) -> CpdocsConfig:
    """Use the current cpdocs policy against another checkout of the same project.

    The introduction is content and comes from the checkout. The theme is presentation and keeps
    pointing into the current tree, so every version looks like the project does today.
    """

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
    """The top directory of the Git repository that contains ``project_root``."""

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

    remove_tree(layout.versions, owner=layout.root.parent)
    layout.versions.mkdir(parents=True, exist_ok=True)

    built: list[SelectedRef] = []
    for ref in selected:
        temporary: tempfile.TemporaryDirectory[str] | None = None
        worktree: Path | None = None
        checkout = project_root
        if ref.checkout is not None:
            temporary = tempfile.TemporaryDirectory(prefix="cpdocs-ref-")
            worktree = Path(temporary.name) / "checkout"
            _run_git(["worktree", "add", "--detach", str(worktree), ref.checkout], cwd=project_root)
            checkout = worktree / subdirectory
        try:
            if not checkout.is_dir():
                raise RuntimeError(f"configured version {ref.name!r} does not contain {subdirectory}")
            ref_config = _config_for_checkout(config, checkout) if ref.checkout else config
            work = layout.work(ref.name)
            graph = build_graph(ref_config, source=checkout, work=work, version=ref.name)
            _render_version(
                graph,
                ref_config,
                output=contained_path(layout.versions, Path(ref.name)),
                work=work / "render",
                root_depth=project_docs_root_depth,
            )
            built.append(ref)
        finally:
            if temporary is not None and worktree is not None:
                _run_git(["worktree", "remove", "--force", str(worktree)], cwd=project_root)
                temporary.cleanup()

    _write_version_index(layout.versions, built)
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
