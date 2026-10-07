<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Integrate another build system

A build system integrates with cpdocs by producing the two JSON files in the
[build-system contract](../reference/contract.md). cpdocs does not require CMake.

For example, a small project-specific adapter can be configured as:

```yaml
contract: 3
build:
  feature-sets: >
    python tools/minibuild.py feature-sets "{{output-file}}"
  build: >
    python tools/minibuild.py build "{{feature-set}}" "{{output-file}}"
```

The first command writes every configuration worth documenting. The second receives one selected
`feature-set.json`; it may configure, build, run generators, or inspect the build system in any way
needed before writing `manifest.json`.

Python projects can use cpdocs' bundled helper:

```yaml
contract: 3
build:
  feature-sets: >
    "{{python}}" -m cpdocs manifest python feature-sets
    --source "{{source}}" --output "{{output-file}}"
  build: >
    "{{python}}" -m cpdocs manifest python build
    --source "{{source}}" --feature-set "{{feature-set}}" --output "{{output-file}}"
    --package mypackage --package-source src/mypackage
```

Rust projects need no project-local adapter. The bundled Cargo provider implements the same two
commands directly:

```yaml
contract: 3
build:
  feature-sets: >
    cpdocs rust feature-sets
    --source "{{source}}" --output "{{output-file}}"
  build: >
    cpdocs rust build
    --source "{{source}}" --feature-set "{{feature-set}}" --output "{{output-file}}"
```

The build command uses Cargo's nightly rustdoc JSON output. Pin a nightly toolchain with
`rust-toolchain.toml`, or pass `--toolchain nightly-YYYY-MM-DD` to both commands when a project
needs an exact schema version.

Without additional configuration, every Cargo feature is considered independent and becomes one
cpdocs feature set. For example, `simd` and `mpi` produce `features: [simd]` and `features: [mpi]`,
not their Cartesian product. If the real project supports coupled configurations, declare the exact
sets explicitly:

```toml
[package.metadata.cpdocs]
feature-sets = [
  ["mpi"],
  ["cuda"],
  ["mpi", "cuda"],
]
```
