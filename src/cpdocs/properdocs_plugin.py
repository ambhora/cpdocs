# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""ProperDocs plugin which builds the versioned cpdocs API site and mounts it."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

from properdocs.config import config_options as c
from properdocs.exceptions import PluginError
from properdocs.plugins import BasePlugin

from cpdocs.build import Layout, build_versions, recorded_default_version
from cpdocs.config import DEFAULT_CONFIG, CpdocsConfig, load_config

from .properdocs_core import (
    default_issue_url,
    edit_url,
    expand_versions_directive,
    publish_api,
    repository_provider,
    resolve_api_references,
    source_url,
)

_LOG = logging.getLogger("properdocs.plugins.cpdocs")


def _symbol_key(symbol: str) -> tuple[str, ...]:
    return tuple(part for part in re.split(r"::|\.", symbol) if part)


class CpdocsPlugin(BasePlugin):
    """Build cpdocs before ProperDocs and mount it into the final static site."""

    config_scheme = (
        ("config", c.Type(str, default=str(DEFAULT_CONFIG))),
        ("output", c.Type(str, default="build")),
        ("mount", c.Type(str, default="reference/api")),
    )

    def __init__(self) -> None:
        self._project_root: Path | None = None
        self._cpdocs: CpdocsConfig | None = None
        self._last_fingerprint: tuple[tuple[str, int, int], ...] | None = None
        self._serve_active = False
        self._symbols: dict[str, dict[tuple[str, ...], str]] = {}

    @property
    def mount(self) -> str:
        value = str(self.config.get("mount", "reference/api")).strip("/")
        if not value:
            raise PluginError("cpdocs: mount must not be the site root")
        return value

    @property
    def output(self) -> Path:
        assert self._project_root is not None
        path = Path(str(self.config.get("output", "build")))
        return path if path.is_absolute() else self._project_root / path

    def on_startup(self, *, command: str, dirty: bool = False) -> None:
        del dirty
        self._serve_active = command == "serve"

    def _config_file(self, config) -> Path:
        value = getattr(config, "config_file_path", None)
        if value:
            return Path(value).resolve()
        return (Path.cwd() / "properdocs.yml").resolve()

    def on_config(self, config):
        self._project_root = self._config_file(config).parent
        cpdocs_file = Path(str(self.config.get("config", DEFAULT_CONFIG)))
        if not cpdocs_file.is_absolute():
            cpdocs_file = self._project_root / cpdocs_file
        try:
            self._cpdocs = load_config(cpdocs_file)
        except RuntimeError as error:
            raise PluginError(f"cpdocs: {error}") from error

        extra = dict(config.get("extra", {}) or {})
        repo_url = str(config.get("repo_url") or "").strip()
        if repo_url:
            provider = repository_provider(repo_url, extra)
            extra["cpdocs_repo_provider"] = provider
            extra["cpdocs_source_ref"] = os.environ.get("CPDOCS_SOURCE_REF") or self._source_ref()
            if not extra.get("cpdocs_issue_url"):
                extra["cpdocs_issue_url"] = default_issue_url(repo_url, provider)
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

    def _watched_files(self) -> list[Path]:
        """Files whose change should trigger a rebuild during ``properdocs serve``."""

        assert self._project_root is not None
        result = self._git("ls-files", "--cached", "--others", "--exclude-standard")
        if result.returncode == 0:
            files = [self._project_root / line for line in result.stdout.splitlines() if line]
        else:
            files = [path for path in self._project_root.rglob("*") if path.is_file()]
        output = self.output.resolve()
        watched = [
            path
            for path in files
            if output not in path.resolve().parents and ".git" not in path.parts
        ]
        refs = self._project_root / ".git" / "refs"
        if refs.is_dir():
            watched.extend(path for path in refs.rglob("*") if path.is_file())
        return watched

    def _fingerprint(self) -> tuple[tuple[str, int, int], ...]:
        values: list[tuple[str, int, int]] = []
        for path in self._watched_files():
            try:
                stat = path.stat()
            except OSError:
                continue
            values.append((str(path), stat.st_mtime_ns, stat.st_size))
        return tuple(sorted(values))

    def on_pre_build(self, *, config) -> None:
        del config
        assert self._cpdocs is not None
        fingerprint = self._fingerprint()
        versions = Layout.for_output(self.output).versions
        if self._serve_active and fingerprint == self._last_fingerprint and versions.is_dir():
            return
        try:
            build_versions(
                self._cpdocs,
                output=self.output,
                project_docs_root_depth=len(PurePosixPath(self.mount).parts),
            )
        except RuntimeError as error:
            raise PluginError(f"cpdocs: {error}") from error
        self._last_fingerprint = fingerprint
        self._symbols = {}

    def _symbol_pages(self, version: str) -> dict[tuple[str, ...], str]:
        if version not in self._symbols:
            path = Layout.for_output(self.output).versions / version / "symbols.json"
            try:
                names = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                names = {}
            self._symbols[version] = {
                _symbol_key(name): str(target) for name, target in names.items()
            }
        return self._symbols[version]

    def _locate(self, version: str, symbol: str) -> str | None:
        return self._symbol_pages(version).get(_symbol_key(symbol))

    def _versions_metadata(self) -> dict[str, object]:
        path = Layout.for_output(self.output).versions / "versions.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def on_page_markdown(self, markdown, page, config, files=None):
        del config, files
        assert self._cpdocs is not None
        level = self._cpdocs.check_broken_references
        missing: list[tuple[str, str]] = []
        markdown = expand_versions_directive(
            markdown,
            page_dest_uri=page.file.dest_uri,
            mount=self.mount,
            metadata=self._versions_metadata(),
        )
        result = resolve_api_references(
            markdown,
            page_dest_uri=page.file.dest_uri,
            mount=self.mount,
            default_version=recorded_default_version(self.output),
            locate=self._locate,
            missing=missing,
        )
        if missing and level != "ignore":
            listing = ", ".join(f"{symbol} ({version})" for version, symbol in missing)
            message = f"cpdocs: {page.file.src_uri} references unknown API entities: {listing}"
            if level == "fail":
                raise PluginError(message)
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
        source = Path(page.file.abs_src_path).resolve()
        try:
            relative_source = source.relative_to(self._project_root).as_posix()
        except ValueError:
            return context
        provider = repository_provider(repo_url, extra)
        context["cpdocs_source_url"] = source_url(repo_url, provider, str(ref), relative_source)
        context["cpdocs_edit_url"] = edit_url(repo_url, provider, str(ref), relative_source)
        return context

    def on_post_build(self, *, config) -> None:
        publish_api(
            Layout.for_output(self.output).versions, Path(config["site_dir"]).resolve(), self.mount
        )
