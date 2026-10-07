# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from cpdocs.properdocs_core import publish_api, resolve_api_references


def test_semantic_api_links_resolve_against_mount() -> None:
    rendered = resolve_api_references(
        "See @apidocs::dice::meta::build and @apidocs[v1.2]::dice.solve.",
        page_dest_uri="reference/index.html",
        mount="reference/api",
        default_version="main",
    )
    assert "(api/main/_symbols/dice/meta/build/)" in rendered
    assert "(api/v1.2/_symbols/dice/solve/)" in rendered


def test_publish_replaces_api_subtree(tmp_path: Path) -> None:
    source = tmp_path / "cpdocs"
    (source / "main").mkdir(parents=True)
    (source / "main" / "index.html").write_text("new", encoding="utf-8")
    site = tmp_path / "site"
    stale = site / "reference" / "api" / "old"
    stale.mkdir(parents=True)
    (stale / "index.html").write_text("old", encoding="utf-8")
    destination = publish_api(source, site, "reference/api")
    assert (destination / "main" / "index.html").read_text(encoding="utf-8") == "new"
    assert not (destination / "old").exists()
    assert (site / ".nojekyll").is_file()


def test_sentence_final_period_is_not_part_of_the_symbol() -> None:
    rendered = resolve_api_references(
        "Call @apidocs::dice::roll.",
        page_dest_uri="index.html",
        mount="reference/api",
        default_version="main",
    )
    assert rendered == "Call [`dice::roll`](reference/api/main/_symbols/dice/roll/)."


def test_unknown_references_are_reported() -> None:
    missing: list[tuple[str, str]] = []
    resolve_api_references(
        "@apidocs::a::b and @apidocs[v1]::c",
        page_dest_uri="index.html",
        mount="api",
        default_version="main",
        locate=lambda version, symbol: "api/a/function-b/" if symbol == "a::b" else None,
        missing=missing,
    )
    assert missing == [("v1", "c")]


def test_known_references_link_straight_to_the_page() -> None:
    rendered = resolve_api_references(
        "See @apidocs::a::b and @apidocs::a::c.",
        page_dest_uri="guide/index.html",
        mount="reference/api",
        default_version="1.0",
        locate=lambda version, symbol: {"a::b": "api/a/function-b/", "a::c": "api/a/#member-c"}.get(
            symbol
        ),
    )
    assert "(../reference/api/1.0/api/a/function-b/)" in rendered
    assert "(../reference/api/1.0/api/a/#member-c)" in rendered


def test_versions_directive_lists_every_version() -> None:
    from cpdocs.properdocs_core import expand_versions_directive

    rendered = expand_versions_directive(
        "Versions:\n\n@apidocs-versions\n",
        page_dest_uri="reference/api.html",
        mount="reference/api",
        metadata={
            "default": "1.1",
            "aliases": {"stable": "1.1", "dev": "main"},
            "versions": [
                {"name": "main", "kind": "branch"},
                {"name": "1.1", "kind": "tag"},
            ],
        },
    )
    assert "- [main](api/main/) — branch, `dev`" in rendered
    assert "- [1.1](api/1.1/) — tag, default, `stable`" in rendered


def test_code_is_left_alone() -> None:
    markdown = (
        "Use `@apidocs::a::b` like this:\n\n```text\n@apidocs::a::b\n```\n\nSee @apidocs::a::b.\n"
    )
    rendered = resolve_api_references(
        markdown, page_dest_uri="index.html", mount="api", default_version="main"
    )
    assert rendered.count("@apidocs::a::b") == 2
    assert rendered.endswith("See [`a::b`](api/main/_symbols/a/b/).\n")


def test_subsite_mounts_are_relative_to_project_root(tmp_path: Path) -> None:
    from cpdocs.properdocs_plugin import CpdocsPlugin

    (tmp_path / "examples" / "demo").mkdir(parents=True)
    (tmp_path / "examples" / "demo" / "properdocs.yml").write_text("site_name: demo\n")
    plugin = CpdocsPlugin()
    plugin._project_root = tmp_path
    plugin.config = {"subsites": ["examples/demo"]}
    assert plugin._subsites() == [(tmp_path / "examples" / "demo", Path("examples/demo"))]


def test_serve_reuses_cached_subsites_until_their_inputs_change(
    tmp_path: Path, monkeypatch
) -> None:
    from cpdocs.properdocs_plugin import CpdocsPlugin

    project = tmp_path / "examples" / "demo"
    project.mkdir(parents=True)
    config_file = project / "properdocs.yml"
    config_file.write_text("site_name: demo\n", encoding="utf-8")
    root_doc = tmp_path / "docs" / "index.md"
    root_doc.parent.mkdir()
    root_doc.write_text("root\n", encoding="utf-8")

    plugin = CpdocsPlugin()
    plugin._project_root = tmp_path
    plugin._serve_active = True
    plugin.config = {"subsites": ["examples/demo"], "output": "build"}

    builds: list[Path] = []

    def fake_build(project_arg, mount, destination, *, strict):
        del project_arg, mount, strict
        builds.append(destination)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "index.html").write_text(
            f"build {len(builds)}\n", encoding="utf-8"
        )

    monkeypatch.setattr(plugin, "_run_subsite_build", fake_build)

    site = tmp_path / "build" / "site"
    plugin._build_subsites(site, strict=False)
    mounted = site / "examples" / "demo" / "index.html"
    assert mounted.read_text(encoding="utf-8") == "build 1\n"
    assert len(builds) == 1
    assert builds[0] != site / "examples" / "demo"

    # A normal serve rebuild cleans site_dir. The cached subsite is copied back without running
    # ProperDocs for the example again.
    import shutil

    shutil.rmtree(site)
    root_doc.write_text("root changed\n", encoding="utf-8")
    plugin._build_subsites(site, strict=False)
    assert mounted.read_text(encoding="utf-8") == "build 1\n"
    assert len(builds) == 1

    # Editing the example invalidates only that subsite cache.
    config_file.write_text("site_name: demo changed\n", encoding="utf-8")
    shutil.rmtree(site)
    plugin._build_subsites(site, strict=False)
    assert mounted.read_text(encoding="utf-8") == "build 2\n"
    assert len(builds) == 2
