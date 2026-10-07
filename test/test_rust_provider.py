# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import sys
from pathlib import Path

from cpdocs.cli import main
from cpdocs.contract import read_feature_sets
from cpdocs.providers.cargo import _feature_sets


def _fake_cargo(path: Path) -> Path:
    script = path / "cargo"
    script.write_text(
        f"""#!{sys.executable}
import json
import pathlib
import sys

root = pathlib.Path.cwd()
with (root / "cargo-commands.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\\n")

args = sys.argv[1:]
if args and args[0].startswith("+"):
    args = args[1:]

if args[0] == "metadata":
    manifest = root / "Cargo.toml"
    value = {{
        "packages": [{{
            "name": "rust-geometry",
            "version": "1.0.0",
            "manifest_path": str(manifest),
            "features": {{"checked": [], "batch": []}},
            "metadata": {{}},
            "targets": [{{
                "name": "rust_geometry",
                "kind": ["lib"],
                "src_path": str(root / "src" / "lib.rs"),
            }}],
        }}],
    }}
    print(json.dumps(value))
elif args[0] == "rustdoc":
    target = pathlib.Path(args[args.index("--target-dir") + 1])
    output = target / "doc" / "rust_geometry.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({{
        "root": "0",
        "format_version": 61,
        "includes_private": False,
        "index": {{
            "0": {{
                "crate_id": 0,
                "name": "rust_geometry",
                "visibility": "public",
                "inner": {{"module": {{"items": ["1"]}}}},
            }},
            "1": {{
                "crate_id": 0,
                "name": "dot",
                "visibility": "public",
                "docs": "Return a dot product.",
                "inner": {{
                    "function": {{
                        "sig": {{"inputs": [], "output": {{"primitive": "f64"}}}},
                        "header": {{
                            "is_const": False,
                            "is_async": False,
                            "is_unsafe": False,
                            "abi": "rust",
                        }},
                    }}
                }},
            }},
        }},
        "paths": {{
            "0": {{"crate_id": 0, "path": ["rust_geometry"], "kind": "module"}},
            "1": {{
                "crate_id": 0,
                "path": ["rust_geometry", "dot"],
                "kind": "function",
            }},
        }},
        "external_crates": {{}},
        "target": {{}},
    }}), encoding="utf-8")
else:
    raise SystemExit("unexpected fake cargo command: " + repr(args))
""",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | 0o111)
    return script


def test_default_cargo_features_are_disjoint_and_sorted() -> None:
    package = {
        "features": {"simd": [], "default": ["simd"], "mpi": []},
        "metadata": {},
    }
    assert _feature_sets(package) == [["default"], ["mpi"], ["simd"]]
    assert _feature_sets({"features": {}, "metadata": {}}) == [[]]


def test_metadata_can_override_disjoint_default() -> None:
    package = {
        "features": {"mpi": [], "cuda": []},
        "metadata": {"cpdocs": {"feature-sets": [["mpi"], ["mpi", "cuda"]]}},
    }
    assert _feature_sets(package) == [["mpi"], ["mpi", "cuda"]]


def test_rust_cli_provider_uses_cargo_metadata_and_nightly_rustdoc(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "project"
    (source / "src").mkdir(parents=True)
    (source / "Cargo.toml").write_text(
        '[package]\nname = "rust-geometry"\nversion = "1.0.0"\nedition = "2024"\n',
        encoding="utf-8",
    )
    (source / "src" / "lib.rs").write_text("pub fn dot() -> f64 { 0.0 }\n", encoding="utf-8")
    cargo = _fake_cargo(tmp_path)
    monkeypatch.setenv("CPDOCS_CARGO", str(cargo))

    feature_sets_file = tmp_path / "feature-sets.json"
    assert main(
        [
            "rust",
            "feature-sets",
            "--source",
            str(source),
            "--output",
            str(feature_sets_file),
        ]
    ) == 0
    feature_sets = read_feature_sets(feature_sets_file)
    assert [item.features for item in feature_sets.feature_sets] == [("batch",), ("checked",)]

    selected = tmp_path / "feature-set.json"
    selected.write_text(
        json.dumps({"cpdocs-feature-set": 1, "features": ["batch"]}), encoding="utf-8"
    )
    manifest_file = tmp_path / "manifest.json"
    assert main(
        [
            "rust",
            "build",
            "--source",
            str(source),
            "--feature-set",
            str(selected),
            "--output",
            str(manifest_file),
        ]
    ) == 0

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    unit = manifest["units"][0]
    assert unit["language"] == "rust"
    assert unit["rustdoc-json"].endswith("cargo-target/doc/rust_geometry.json")
    assert "src" in unit["sources"]

    commands = [
        json.loads(line)
        for line in (source / "cargo-commands.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    rustdoc = next(command for command in commands if "rustdoc" in command)
    assert rustdoc[rustdoc.index("--features") + 1] == "batch"
    assert "--no-default-features" in rustdoc
    assert rustdoc[rustdoc.index("--output-format") + 1] == "json"
    assert rustdoc[rustdoc.index("-Z") + 1] == "unstable-options"


def test_rustdoc_backend_keeps_local_public_api_and_default_public_members(tmp_path: Path) -> None:
    from cpdocs.model import stable_entity_id
    from cpdocs.languages.rust.extract import build_rust_graph

    rustdoc = tmp_path / "rustdoc.json"
    rustdoc.write_text(
        json.dumps(
            {
                "root": "0",
                "format_version": 61,
                "includes_private": False,
                "index": {
                    "0": {
                        "crate_id": 0,
                        "name": "demo",
                        "visibility": "public",
                        "inner": {"module": {"items": ["1"]}},
                    },
                    "1": {
                        "crate_id": 0,
                        "name": "Mode",
                        "visibility": "public",
                        "inner": {"enum": {"variants": ["2"], "impls": []}},
                    },
                    "2": {
                        "crate_id": 0,
                        "name": "Fast",
                        "visibility": "default",
                        "inner": {"variant": {}},
                    },
                    "99": {
                        "crate_id": 1,
                        "name": "External",
                        "visibility": "public",
                        "inner": {"struct": {}},
                    },
                },
                "paths": {
                    "0": {"crate_id": 0, "path": ["demo"], "kind": "module"},
                    "1": {"crate_id": 0, "path": ["demo", "Mode"], "kind": "enum"},
                    "2": {
                        "crate_id": 0,
                        "path": ["demo", "Mode", "Fast"],
                        "kind": "variant",
                    },
                    "99": {"crate_id": 1, "path": ["other", "External"], "kind": "struct"},
                },
                "external_crates": {"1": {"name": "other", "html_root_url": None}},
                "target": {},
            }
        ),
        encoding="utf-8",
    )

    graph = build_rust_graph(rustdoc_json=rustdoc, project="demo", project_root=tmp_path)
    variant = stable_entity_id("rust", "enum_value", "demo::Mode::Fast")
    assert variant in graph.entities
    assert graph.entities[variant].parent == stable_entity_id("rust", "enum", "demo::Mode")
    assert stable_entity_id("rust", "struct", "other::External") not in graph.entities


def test_rustdoc_backend_uses_semantic_owners_for_fields_and_impl_items(tmp_path: Path) -> None:
    from cpdocs.model import stable_entity_id
    from cpdocs.languages.rust.extract import build_rust_graph

    rustdoc = tmp_path / "rustdoc.json"
    rustdoc.write_text(
        json.dumps(
            {
                "root": "0",
                "format_version": 61,
                "includes_private": False,
                "index": {
                    "0": {
                        "crate_id": 0,
                        "name": "demo",
                        "visibility": "public",
                        "inner": {"module": {"items": ["1"]}},
                    },
                    "1": {
                        "crate_id": 0,
                        "name": "Vector3",
                        "visibility": "public",
                        "inner": {
                            "struct": {
                                "kind": {
                                    "plain": {
                                        "fields": ["2", "3", "4"],
                                        "has_stripped_fields": False,
                                    }
                                },
                                "generics": {},
                                "impls": ["5", "7"],
                            }
                        },
                    },
                    "2": {
                        "crate_id": 0,
                        "name": "x",
                        "visibility": "public",
                        "inner": {"struct_field": {"primitive": "f64"}},
                    },
                    "3": {
                        "crate_id": 0,
                        "name": "y",
                        "visibility": "public",
                        "inner": {"struct_field": {"primitive": "f64"}},
                    },
                    "4": {
                        "crate_id": 0,
                        "name": "z",
                        "visibility": "public",
                        "inner": {"struct_field": {"primitive": "f64"}},
                    },
                    "5": {
                        "crate_id": 0,
                        "name": None,
                        "visibility": "default",
                        "inner": {
                            "impl": {
                                "trait": None,
                                "for": {
                                    "resolved_path": {
                                        "name": "Vector3",
                                        "id": "1",
                                        "args": None,
                                    }
                                },
                                "items": ["6"],
                            }
                        },
                    },
                    "6": {
                        "crate_id": 0,
                        "name": "norm",
                        "visibility": "public",
                        "inner": {
                            "function": {
                                "sig": {"inputs": [], "output": {"primitive": "f64"}},
                                "header": {},
                            }
                        },
                    },
                    "7": {
                        "crate_id": 0,
                        "name": None,
                        "visibility": "default",
                        "inner": {
                            "impl": {
                                "trait": {"name": "Clone", "id": "99", "args": None},
                                "for": {
                                    "resolved_path": {
                                        "name": "Vector3",
                                        "id": "1",
                                        "args": None,
                                    }
                                },
                                "items": ["8"],
                            }
                        },
                    },
                    "8": {
                        "crate_id": 0,
                        "name": "clone",
                        "visibility": "default",
                        "inner": {"function": {"sig": {"inputs": [], "output": None}, "header": {}}},
                    },
                },
                # Deliberately flat field/method paths reproduce the nightly rustdoc shape that
                # originally caused cpdocs to render these declarations at crate scope.
                "paths": {
                    "0": {"crate_id": 0, "path": ["demo"], "kind": "module"},
                    "1": {"crate_id": 0, "path": ["demo", "Vector3"], "kind": "struct"},
                    "2": {"crate_id": 0, "path": ["demo", "x"], "kind": "struct_field"},
                    "3": {"crate_id": 0, "path": ["demo", "y"], "kind": "struct_field"},
                    "4": {"crate_id": 0, "path": ["demo", "z"], "kind": "struct_field"},
                    "6": {"crate_id": 0, "path": ["demo", "norm"], "kind": "function"},
                    "8": {"crate_id": 0, "path": ["demo", "clone"], "kind": "function"},
                },
                "external_crates": {},
                "target": {},
            }
        ),
        encoding="utf-8",
    )

    graph = build_rust_graph(rustdoc_json=rustdoc, project="demo", project_root=tmp_path)
    vector = stable_entity_id("rust", "struct", "demo::Vector3")
    assert vector in graph.entities
    for field_name in ("x", "y", "z"):
        field = stable_entity_id("rust", "field", f"demo::Vector3::{field_name}")
        assert field in graph.entities
        assert graph.entities[field].parent == vector
    method = stable_entity_id("rust", "method", "demo::Vector3::norm")
    assert method in graph.entities
    assert graph.entities[method].parent == vector
    assert stable_entity_id("rust", "function", "demo::clone") not in graph.entities
    assert stable_entity_id("rust", "method", "demo::Vector3::clone") not in graph.entities
