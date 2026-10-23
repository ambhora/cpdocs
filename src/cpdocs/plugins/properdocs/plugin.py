# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""ProperDocs plugin which builds the versioned cpdocs API site and mounts it."""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import sys

import properdocs.config.config_options
import properdocs.exceptions
import properdocs.plugins

import cpdocs.build
import cpdocs.config
import cpdocs.filesystem
import cpdocs.plugins.properdocs.core

_LOG = logging.getLogger("properdocs.plugins.cpdocs")
_Fingerprint = tuple[tuple[str, int, int], ...]


def _symbol_key(symbol: str) -> tuple[str, ...]:
    return tuple(part for part in re.split(r"::|\.", symbol) if part)


class CpdocsPlugin(properdocs.plugins.BasePlugin):
    """Build cpdocs before ProperDocs and mount it into the final static site."""

    config_scheme = (
        ("config", properdocs.config.config_options.Type(str, default=str(cpdocs.config.DEFAULT_CONFIG))),
        ("output", properdocs.config.config_options.Type(str, default="build")),
        ("tmp_directory", properdocs.config.config_options.Type(str, default="")),
        ("mount", properdocs.config.config_options.Type(str, default="reference/api")),
        (
            "subsites",
            properdocs.config.config_options.ListOfItems(properdocs.config.config_options.Type(str), default=[]),
        ),
    )

    def __init__(self) -> None:
        self._project_root: pathlib.Path | None = None
        self._cpdocs: cpdocs.config.CpdocsConfig | None = None
        self._last_fingerprint: _Fingerprint | None = None
        self._subsite_build_state: dict[pathlib.Path, tuple[_Fingerprint, bool]] = {}
        self._serve_active = False
        self._symbols: dict[str, dict[tuple[str, ...], str]] = {}

    @property
    def mount(self) -> str:
        try:
            return cpdocs.plugins.properdocs.core.mount_path(str(self.config.get("mount", "reference/api"))).as_posix()
        except ValueError as error:
            raise properdocs.exceptions.PluginError(f"cpdocs: {error}") from error

    @property
    def output(self) -> pathlib.Path:
        assert self._project_root is not None
        path = pathlib.Path(str(self.config.get("output", "build")))
        return path if path.is_absolute() else self._project_root / path

    @property
    def tmp_directory(self) -> pathlib.Path | None:
        assert self._project_root is not None
        value = str(self.config.get("tmp_directory", "")).strip()
        if not value:
            return None
        path = pathlib.Path(value).expanduser()
        return path if path.is_absolute() else self._project_root / path

    def on_startup(self, *, command: str, dirty: bool = False) -> None:
        del dirty
        self._serve_active = command == "serve" or os.environ.get("_CPDOCS_SERVE_IN_SITU") == "1"

    def _config_file(self, config) -> pathlib.Path:
        value = getattr(config, "config_file_path", None)
        if value:
            return pathlib.Path(value).resolve()
        return (pathlib.Path.cwd() / "properdocs.yml").resolve()

    def on_config(self, config):
        self._project_root = self._config_file(config).parent
        cpdocs_file = pathlib.Path(str(self.config.get("config", cpdocs.config.DEFAULT_CONFIG)))
        if not cpdocs_file.is_absolute():
            cpdocs_file = self._project_root / cpdocs_file
        try:
            self._cpdocs = cpdocs.config.load_config(cpdocs_file)
        except RuntimeError as error:
            raise properdocs.exceptions.PluginError(f"cpdocs: {error}") from error

        extra = dict(config.get("extra", {}) or {})
        repo_url = str(config.get("repo_url") or "").strip()
        if repo_url:
            provider = cpdocs.plugins.properdocs.core.repository_provider(repo_url, extra)
            extra["cpdocs_repo_provider"] = provider
            extra["cpdocs_source_ref"] = os.environ.get("CPDOCS_SOURCE_REF") or self._source_ref()
            if not extra.get("cpdocs_issue_url"):
                extra["cpdocs_issue_url"] = cpdocs.plugins.properdocs.core.default_issue_url(repo_url, provider)
        config["extra"] = extra
        return config

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        assert self._project_root is not None
        return subprocess.run(
            ["git", *arguments],
            cwd=self._project_root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def _source_ref(self) -> str:
        result = self._git("symbolic-ref", "--quiet", "--short", "HEAD")
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        result = self._git("describe", "--tags", "--exact-match")
        return result.stdout.strip() if result.returncode == 0 else "main"

    def _watched_files(self) -> list[pathlib.Path]:
        """Files whose change should trigger a rebuild during ``properdocs serve``."""

        assert self._project_root is not None
        result = self._git("ls-files", "--cached", "--others", "--exclude-standard")
        if result.returncode == 0:
            files = [self._project_root / line for line in result.stdout.splitlines() if line]
        else:
            files = [path for path in self._project_root.rglob("*") if path.is_file()]
        output = self.output.resolve()
        watched = [path for path in files if output not in path.resolve().parents and ".git" not in path.parts]
        refs = self._project_root / ".git" / "refs"
        if refs.is_dir():
            watched.extend(path for path in refs.rglob("*") if path.is_file())
        return watched

    @staticmethod
    def _fingerprint_paths(paths) -> _Fingerprint:
        values: list[tuple[str, int, int]] = []
        for path in paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            values.append((str(path), stat.st_mtime_ns, stat.st_size))
        return tuple(sorted(values))

    def _fingerprint(self) -> _Fingerprint:
        return self._fingerprint_paths(self._watched_files())

    def _subsite_fingerprint(self, project: pathlib.Path, watched_files: list[pathlib.Path]) -> _Fingerprint:
        """Fingerprint one subsite and cpdocs itself, but not unrelated project docs."""

        assert self._project_root is not None
        project = project.resolve()
        refs = (self._project_root / ".git" / "refs").resolve()
        plugin_source = pathlib.Path(__file__).resolve().parent
        selected: list[pathlib.Path] = []
        for path in watched_files:
            resolved = path.resolve()
            if (
                project in resolved.parents
                or plugin_source in resolved.parents
                or refs == resolved
                or refs in resolved.parents
            ):
                selected.append(path)
        return self._fingerprint_paths(selected)

    def _watch_roots(self) -> list[pathlib.Path]:
        """Compact watch set which still notices new files in project directories."""

        assert self._project_root is not None
        project_root = self._project_root.resolve()
        roots: set[pathlib.Path] = set()
        for path in self._watched_files():
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(project_root)
            except ValueError:
                roots.add(resolved)
                continue

            if relative.parts and relative.parts[0] == ".git":
                # Do not recursively watch all of .git: cpdocs itself creates temporary
                # worktrees while documenting historical refs. Watching refs is enough to
                # notice commits/tag changes without creating rebuild loops.
                if len(relative.parts) >= 2 and relative.parts[1] == "refs":
                    roots.add(project_root / ".git" / "refs")
                else:
                    roots.add(resolved)
                continue

            roots.add(resolved if len(relative.parts) == 1 else project_root / relative.parts[0])
        return sorted(roots, key=str)

    def on_serve(self, server, config, builder):
        """Make source changes trigger ProperDocs rebuilds during ``serve``."""

        del config
        for path in self._watch_roots():
            server.watch(str(path), builder)
        return server

    def on_pre_build(self, *, config) -> None:
        del config
        assert self._cpdocs is not None
        fingerprint = self._fingerprint()
        versions = cpdocs.build.Layout.for_output(self.output).versions
        if self._serve_active and fingerprint == self._last_fingerprint and versions.is_dir():
            return
        try:
            cpdocs.build.build_versions(
                self._cpdocs,
                output=self.output,
                project_docs_root_depth=len(pathlib.PurePosixPath(self.mount).parts),
                include_working_tree=self._serve_active,
                tmp_directory=self.tmp_directory,
            )
        except RuntimeError as error:
            raise properdocs.exceptions.PluginError(f"cpdocs: {error}") from error
        self._last_fingerprint = fingerprint
        self._symbols = {}

    def _symbol_pages(self, version: str) -> dict[tuple[str, ...], str]:
        if version not in self._symbols:
            path = cpdocs.build.Layout.for_output(self.output).versions / version / "symbols.json"
            try:
                names = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                names = {}
            self._symbols[version] = {_symbol_key(name): str(target) for name, target in names.items()}
        return self._symbols[version]

    def _locate(self, version: str, symbol: str) -> str | None:
        return self._symbol_pages(version).get(_symbol_key(symbol))

    def _versions_metadata(self) -> dict[str, object]:
        path = cpdocs.build.Layout.for_output(self.output).versions / "versions.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def on_page_markdown(self, markdown, page, config, files=None):
        del config, files
        assert self._cpdocs is not None
        level = self._cpdocs.check_broken_references
        missing: list[tuple[str, str]] = []
        markdown = cpdocs.plugins.properdocs.core.expand_versions_directive(
            markdown, page_dest_uri=page.file.dest_uri, mount=self.mount, metadata=self._versions_metadata()
        )
        result = cpdocs.plugins.properdocs.core.resolve_api_references(
            markdown,
            page_dest_uri=page.file.dest_uri,
            mount=self.mount,
            default_version=cpdocs.build.recorded_default_version(self.output),
            locate=self._locate,
            missing=missing,
        )
        if missing and level != "ignore":
            listing = ", ".join(f"{symbol} ({version})" for version, symbol in missing)
            message = f"cpdocs: {page.file.src_uri} references unknown API entities: {listing}"
            if level == "fail":
                raise properdocs.exceptions.PluginError(message)
            _LOG.warning(message)
        return result

    def on_page_context(self, context, page, config, nav=None):
        del nav
        assert self._project_root is not None
        repo_url = str(config.get("repo_url") or "").strip()
        extra = config.get("extra", {}) or {}
        ref = extra.get("cpdocs_source_ref")
        context["cpdocs_source_url"] = None
        context["cpdocs_edit_url"] = None
        if not repo_url or not ref:
            return context
        source = pathlib.Path(page.file.abs_src_path).resolve()
        try:
            relative_source = source.relative_to(self._project_root).as_posix()
        except ValueError:
            return context
        provider = cpdocs.plugins.properdocs.core.repository_provider(repo_url, extra)
        context["cpdocs_source_url"] = cpdocs.plugins.properdocs.core.source_url(
            repo_url, provider, str(ref), relative_source
        )
        context["cpdocs_edit_url"] = cpdocs.plugins.properdocs.core.edit_url(
            repo_url, provider, str(ref), relative_source
        )
        return context

    def _subsites(self) -> list[tuple[pathlib.Path, pathlib.Path]]:
        """Return configured ProperDocs sub-sites and their site-relative mounts."""

        assert self._project_root is not None
        root = self._project_root.resolve()
        result: list[tuple[pathlib.Path, pathlib.Path]] = []
        seen: set[pathlib.Path] = set()
        for configured in self.config.get("subsites", []) or []:
            value = str(configured).strip().strip("/")
            if not value:
                raise properdocs.exceptions.PluginError("cpdocs: subsite paths must not be empty")
            relative = pathlib.Path(value)
            if relative.is_absolute() or ".." in relative.parts:
                raise properdocs.exceptions.PluginError(f"cpdocs: subsite must be below the project root: {configured}")
            project = (root / relative).resolve()
            try:
                mount = project.relative_to(root)
            except ValueError as error:
                raise properdocs.exceptions.PluginError(
                    f"cpdocs: subsite must be below the project root: {configured}"
                ) from error
            if project in seen:
                continue
            if not (project / "properdocs.yml").is_file():
                raise properdocs.exceptions.PluginError(f"cpdocs: subsite has no properdocs.yml: {configured}")
            seen.add(project)
            result.append((project, mount))
        return result

    def _run_subsite_build(
        self, project: pathlib.Path, mount: pathlib.Path, destination: pathlib.Path, *, strict: bool
    ) -> None:
        environment = os.environ.copy()
        if self._serve_active:
            # The nested invocation uses ``build`` so that it writes once into a persistent
            # cache. Tell its cpdocs plugin to use serve semantics for the checked-out tree.
            environment["_CPDOCS_SERVE_IN_SITU"] = "1"
        command = [sys.executable, "-m", "properdocs", "build", "--site-dir", str(destination)]
        if strict:
            command.append("--strict")
        result = subprocess.run(
            command,
            cwd=project,
            env=environment,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            raise properdocs.exceptions.PluginError(
                f"cpdocs: ProperDocs subsite build failed for {mount.as_posix()}:\n{result.stdout}"
            )
        _LOG.info("Built ProperDocs subsite %s", mount.as_posix())

    @staticmethod
    def _publish_subsite(source: pathlib.Path, destination: pathlib.Path, *, site_directory: pathlib.Path) -> None:
        cpdocs.filesystem.remove_tree(destination, owner=site_directory)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)

    def _build_subsites(self, site_directory: pathlib.Path, *, strict: bool) -> None:
        """Build and mount nested ProperDocs projects.

        During ``serve`` the parent site directory is cleaned on every normal rebuild. Building
        every example again just to repopulate that directory is unnecessarily expensive, so
        rendered subsites live in a persistent cache below cpdocs' output directory. A subsite is
        rebuilt only when files belonging to that subsite (or Git refs used by versioning) change;
        unchanged cached HTML is merely copied back into the freshly rebuilt parent site.
        """

        subsites = self._subsites()
        watched_files = self._watched_files() if self._serve_active else []
        cache_root = cpdocs.build.Layout.for_output(self.output).root / "subsites"

        for project, mount in subsites:
            destination = site_directory / mount
            if not self._serve_active:
                self._run_subsite_build(project, mount, destination, strict=strict)
                continue

            cache = cache_root / mount
            fingerprint = self._subsite_fingerprint(project, watched_files)
            state = (fingerprint, strict)
            if self._subsite_build_state.get(project) != state or not cache.is_dir():
                self._run_subsite_build(project, mount, cache, strict=strict)
                self._subsite_build_state[project] = state
            else:
                _LOG.debug("Reusing cached ProperDocs subsite %s", mount.as_posix())

            self._publish_subsite(cache, destination, site_directory=site_directory)

    def on_post_build(self, *, config) -> None:
        site_directory = pathlib.Path(config["site_dir"]).resolve()
        cpdocs.plugins.properdocs.core.publish_api(
            cpdocs.build.Layout.for_output(self.output).versions, site_directory, self.mount
        )
        self._build_subsites(site_directory, strict=bool(config.get("strict", False)))
