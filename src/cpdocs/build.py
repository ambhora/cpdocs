# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Build operations: describe, resolve variants, extract, merge and render.

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
from importlib import resources
from pathlib import Path, PurePosixPath

from .clang_backend import extract_clang_graph
from .config import CpdocsConfig, load_config
from .contract import (
    ContractError,
    Description,
    Request,
    UnitManifest,
    VariantManifest,
    check_variant,
    read_description,
    read_variant_manifest,
)
from .html_renderer import render_html_site
from .model import ApiGraph, merge_graphs
from .python_backend import build_python_graph
from .rust_backend import build_rust_graph
from .versioning import SelectedRef, latest_tag, select_refs

_PLACEHOLDERS = ("source", "build", "request", "manifest", "python", "cpdocs.cmake")
_CONTAINER_KINDS = {"namespace", "package", "module"}


@dataclasses.dataclass(frozen=True)
class Layout:
    """Directories below ``<output>/cpdocs``."""

    root: Path

    @classmethod
    def for_output(cls, output: Path) -> Layout:
        return cls(root=(output / "cpdocs").resolve())

    @property
    def current(self) -> Path:
        return self.root / "current"

    @property
    def versions(self) -> Path:
        return self.root / "versions"

    def work(self, ref: str) -> Path:
        return self.root / "work" / ref.replace("/", "__")


def cmake_module() -> Path:
    """Path of the CMake adapter shipped with cpdocs."""

    return Path(str(resources.files("cpdocs") / "share" / "cmake" / "cpdocs.cmake"))


# --------------------------------------------------------------------------------------------------
# Talking to the build system
# --------------------------------------------------------------------------------------------------


def _expand(argument: str, request: Request, request_file: Path) -> str:
    values = {
        "source": str(request.source),
        "build": str(request.build),
        "request": str(request_file),
        "manifest": str(request.manifest),
        "python": sys.executable,
        "cpdocs.cmake": str(cmake_module()),
    }
    for name in _PLACEHOLDERS:
        argument = argument.replace("{" + name + "}", values[name])
    return argument


def _run_commands(
    commands: tuple[tuple[str, ...], ...], *, request: Request, request_file: Path, log: Path
) -> None:
    environment = dict(os.environ)
    environment["CPDOCS_REQUEST"] = str(request_file)
    environment["CPDOCS_MANIFEST"] = str(request.manifest)
    with log.open("w", encoding="utf-8") as stream:
        for command in commands:
            argv = [_expand(argument, request, request_file) for argument in command]
            stream.write("$ " + " ".join(argv) + "\n")
            stream.flush()
            try:
                result = subprocess.run(
                    argv,
                    cwd=request.source,
                    env=environment,
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
            except FileNotFoundError as error:
                raise RuntimeError(
                    f"cannot run build-system command {argv[0]!r}: {error}"
                ) from error
            stream.write(result.stdout)
            if result.returncode != 0:
                raise RuntimeError(
                    f"build-system command failed ({request.phase}"
                    + (f", variant {request.variant}" if request.variant else "")
                    + "):\n  "
                    + " ".join(argv)
                    + "\n\n"
                    + result.stdout.rstrip()
                )


def describe(
    commands: tuple[tuple[str, ...], ...], *, source: Path, work: Path, ref: str, ref_kind: str
) -> Description:
    """Run the describe phase and read the describe manifest."""

    directory = work / "describe"
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    request = Request(
        phase="describe",
        ref=ref,
        ref_kind=ref_kind,
        source=source.resolve(),
        build=directory / "build",
        manifest=directory / "manifest.json",
        variant=None,
    )
    request_file = directory / "request.json"
    request.write(request_file)
    _run_commands(commands, request=request, request_file=request_file, log=directory / "log.txt")
    return read_description(request.manifest)


def resolve_variant(
    description: Description, name: str, *, source: Path, work: Path, ref: str, ref_kind: str
) -> VariantManifest:
    """Run one variant's commands and read its variant manifest."""

    directory = work / "variants" / name
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    request = Request(
        phase="variant",
        ref=ref,
        ref_kind=ref_kind,
        source=source.resolve(),
        build=directory / "build",
        manifest=directory / "manifest.json",
        variant=name,
    )
    request_file = directory / "request.json"
    request.write(request_file)
    _run_commands(
        description.variant(name).commands,
        request=request,
        request_file=request_file,
        log=directory / "log.txt",
    )
    manifest = read_variant_manifest(request.manifest, source=request.source)
    check_variant(manifest, description=description, requested=name, path=request.manifest)
    return manifest


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
    variant: str,
    work: Path,
    config: CpdocsConfig,
) -> ApiGraph:
    if unit.language in {"c", "cpp"}:
        assert unit.parse is not None
        graph = extract_clang_graph(
            project=project,
            version=version,
            project_root=project_root,
            language=unit.language,
            api_roots=[root.path for root in unit.api],
            parse=unit.parse,
            variant=variant,
            clang_executable=_clang(),
            work_directory=work / "clang" / unit.id,
        )
        generated = _generated_sources(unit, graph)
        if generated:
            graph.metadata["generated_sources"] = generated
        return graph
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
        else:
            target.setdefault(key, value)


def _combine(graphs: list[ApiGraph], *, project: str, version: str, language: str) -> ApiGraph:
    """Combine the graphs of several units extracted for the same variant."""

    combined = ApiGraph(project=project, version=version, language=language)
    for graph in graphs:
        for entity in graph.entities.values():
            combined.add(entity)
        for path, content in graph.sources.items():
            combined.sources.setdefault(path, content)
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
        if entity.language in {"c", "cpp"}
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
        if entity.kind not in _CONTAINER_KINDS and not entity.documentation.strip()
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
    ref: str,
    ref_kind: str,
    version: str,
    variants: str,
) -> ApiGraph:
    """Describe, resolve the selected variants, and merge them into one API graph."""

    description = describe(config.describe, source=source, work=work, ref=ref, ref_kind=ref_kind)
    selected = (
        [variant.name for variant in description.variants]
        if variants == "all"
        else [description.primary.name]
    )
    languages = sorted({unit.language for unit in description.units})
    language = languages[0] if len(languages) == 1 else "mixed"

    per_variant: list[tuple[str, ApiGraph]] = []
    metadata: dict[str, object] = {}
    for name in selected:
        manifest = resolve_variant(
            description, name, source=source, work=work, ref=ref, ref_kind=ref_kind
        )
        unit_graphs = [
            extract_unit(
                unit,
                project=description.project,
                version=version,
                project_root=source,
                variant=name,
                work=work / "variants" / name,
                config=config,
            )
            for unit in manifest.units
        ]
        graph = _combine(
            unit_graphs, project=description.project, version=version, language=language
        )
        graph.variants[name] = {
            "primary": description.variant(name).primary,
            "features": {axis: list(values) for axis, values in manifest.features.items()},
        }
        _merge_metadata(metadata, graph.metadata)
        per_variant.append((name, graph))

    merged = merge_graphs(
        per_variant, project=description.project, version=version, language=language
    )
    metadata["features"] = {axis.name: list(axis.values) for axis in description.features}
    metadata["units"] = [{"id": unit.id, "language": unit.language} for unit in description.units]
    metadata["generator"] = description.generator
    metadata["project_version"] = description.version
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
    variants: str = "all",
    project_docs_root_depth: int = 2,
) -> ApiGraph:
    """Document the working tree into ``<output>/cpdocs/current``."""

    layout = Layout.for_output(output)
    work = layout.work("current")
    graph = build_graph(
        config,
        source=config.project_root,
        work=work,
        ref=version,
        ref_kind="worktree",
        version=version,
        variants=variants,
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


def _write_versions(
    output: Path, built: list[SelectedRef], *, default: str, aliases: dict[str, str]
) -> None:
    names = [ref.name for ref in built]
    newest = latest_tag([ref.name for ref in built if ref.kind == "tag"])

    def target(value: str) -> str | None:
        if value == "latest-tag":
            return newest
        return value if value in names else None

    default_name = target(default) or (names[0] if names else "main")
    resolved_aliases: dict[str, str] = {}
    for alias, value in aliases.items():
        resolved = target(value)
        if resolved is None or alias in names:
            continue
        resolved_aliases[alias] = resolved
        directory = output / alias
        directory.mkdir(parents=True, exist_ok=True)
        depth = len(PurePosixPath(alias).parts)
        (directory / "index.html").write_text(
            _redirect_page("../" * depth + resolved + "/"), encoding="utf-8"
        )

    metadata = {
        "default": default_name,
        "aliases": resolved_aliases,
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


def _config_for_checkout(config: CpdocsConfig, checkout: Path) -> CpdocsConfig | None:
    """Use the checkout's own cpdocs.yml; fall back according to ``versions.legacy``."""

    relative = config.config_file.relative_to(config.project_root)
    candidate = checkout / relative
    if candidate.is_file():
        return load_config(candidate)
    if config.legacy == "skip":
        return None
    index = config.index
    if index is not None:
        moved = checkout / index.relative_to(config.project_root)
        index = moved if moved.is_file() else index
    return dataclasses.replace(
        config, config_file=candidate, project_root=checkout.resolve(), index=index
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
    tags: str | None = None,
    project_docs_root_depth: int = 2,
) -> list[str]:
    """Document every selected ref into ``<output>/cpdocs/versions``.

    The project may live in a subdirectory of its Git repository. Each ref is then checked out as a
    whole and the same subdirectory is documented; refs in which it does not exist are skipped.
    """

    layout = Layout.for_output(output)
    project_root = config.project_root.resolve()
    subdirectory = project_root.relative_to(_repository_root(project_root))
    selected = select_refs(project_root, branches=config.branches, tags=tags or config.tags)
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
                print(
                    f"cpdocs: skipping {ref.name}: {subdirectory} does not exist", file=sys.stderr
                )
                continue
            ref_config = _config_for_checkout(config, checkout) if ref.checkout else config
            if ref_config is None:
                print(f"cpdocs: skipping {ref.name}: it has no cpdocs.yml", file=sys.stderr)
                continue
            work = layout.work(ref.name)
            policy = ref_config.branch_variants if ref.kind == "branch" else ref_config.tag_variants
            try:
                graph = build_graph(
                    ref_config,
                    source=checkout,
                    work=work,
                    ref=ref.name,
                    ref_kind=ref.kind,
                    version=ref.name,
                    variants=policy,
                )
            except RuntimeError as error:
                if config.failure == "fail":
                    raise
                print(f"cpdocs: skipping {ref.name}: {error}", file=sys.stderr)
                continue
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

    _write_versions(layout.versions, built, default=config.default_version, aliases=config.aliases)
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
    "cmake_module",
    "describe",
    "recorded_default_version",
    "resolve_variant",
]
