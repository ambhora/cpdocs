# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
import json
import pathlib
import sys

root = pathlib.Path.cwd()
with (root / "cargo-commands.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\n")

args = sys.argv[1:]
if args and args[0].startswith("+"):
    args = args[1:]

if args[0] == "metadata":
    manifest = root / "Cargo.toml"
    value = {
        "packages": [{
            "name": "rust-geometry",
            "version": "1.0.0",
            "manifest_path": str(manifest),
            "features": {"checked": [], "batch": []},
            "metadata": {},
            "targets": [{
                "name": "rust_geometry",
                "kind": ["lib"],
                "src_path": str(root / "src" / "lib.rs"),
            }],
        }],
    }
    print(json.dumps(value))
elif args[0] == "rustdoc":
    target = pathlib.Path(args[args.index("--target-dir") + 1])
    output = target / "doc" / "rust_geometry.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "root": "0",
        "format_version": 61,
        "includes_private": False,
        "index": {
            "0": {
                "crate_id": 0,
                "name": "rust_geometry",
                "visibility": "public",
                "inner": {"module": {"items": ["1"]}},
            },
            "1": {
                "crate_id": 0,
                "name": "dot",
                "visibility": "public",
                "docs": "Return a dot product.",
                "inner": {
                    "function": {
                        "sig": {"inputs": [], "output": {"primitive": "f64"}},
                        "header": {
                            "is_const": False,
                            "is_async": False,
                            "is_unsafe": False,
                            "abi": "rust",
                        },
                    }
                },
            },
        },
        "paths": {
            "0": {"crate_id": 0, "path": ["rust_geometry"], "kind": "module"},
            "1": {
                "crate_id": 0,
                "path": ["rust_geometry", "dot"],
                "kind": "function",
            },
        },
        "external_crates": {},
        "target": {},
    }), encoding="utf-8")
else:
    raise SystemExit("unexpected fake cargo command: " + repr(args))
