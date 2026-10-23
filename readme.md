<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs

cpdocs generates semantic, versioned API documentation for C, C++, CUDA, HIP, Fortran, Python and
Rust projects.

- **Semantic.** cpdocs reads the source with each language's own tools, Clang for the C family,
  Python's `ast`, rustdoc for Rust and a module reader for Fortran, and works from the resulting
  comment-preserving syntax tree. The reference shows declarations as the compiler sees them:
  namespaces, types, overloads, templates and their documentation, rendered as HTML.
- **Versions.** It documents the branches and tags you list, each as its own version of the
  reference, with a version switcher between them.
- **Build variants.** Projects often expose different APIs in different builds, for example with
  or without MPI. Two hooks, commands run by cpdocs, connect it to the project's build system: the
  first lists every variant worth documenting, and the second builds one variant and describes its
  API. cpdocs runs the second hook once per variant.
- **One merged reference.** The APIs of all variants are merged into one reference. Every
  declaration and every overload shows the variants it is available in, and definitions in
  different languages, such as a C++ and a CUDA implementation, stay separate entries.
- **Language standards.** The same project can be documented for several language standards or
  versions, such as C++17, C++20 and C++23 or Python 3.11 and 3.12, with availability marked the
  same way.
- **ProperDocs.** The reference is a standalone HTML site, and cpdocs integrates with
  [ProperDocs](https://properdocs.org) for the project website around it.
- **Versioned API in an unversioned website.** The cpdocs ProperDocs plugin embeds the versioned
  API reference in the project website. Every version of the API lives below one mount point, so
  the website itself needs no versioning and links such as `@apidocs::demo::solve` resolve to the
  right page.

cpdocs keeps no knowledge of the project's features or build: everything it knows about a variant
comes from the build system through the hooks.

## Quick start

`docs/cpdocs.yml` names the two hooks and the versions to publish:

```yaml
contract: 3

build:
  feature-sets: >
    cmake -S "{{source}}" -B "{{tmpdir}}" -G Ninja
    -DCPDOCS_FEATURE_SETS_OUTPUT="{{output-file}}"
  build: >
    cmake -S "{{source}}" -B "{{tmpdir}}" -G Ninja
    -DCPDOCS_FEATURE_SET="{{feature-set}}"
    -DCPDOCS_MANIFEST_OUTPUT="{{output-file}}"

versions: [main, v2.0.0, v1.0.0]
```

```console
cpdocs build          # document the working tree into build/cpdocs/current
cpdocs versions       # document every listed version into build/cpdocs/versions
properdocs build      # build the project website with the versioned API mounted
```

The [documentation](https://ambhora.github.io/cpdocs/) starts with a tutorial and explains each
capability in a how-to guide. The `examples/` directory holds standalone projects, all built by the
test suite, covering plain CMake, generated headers, build variants, language standards, Python,
Fortran and Rust.

## Development

```console
uv sync
uv run pytest
uv run ruff check && uv run ruff format --check
```

The C and C++ tests need `clang++`, `cmake` and `ninja`. Building the Rust example also needs the
nightly toolchain pinned by `examples/rust-basic/rust-toolchain.toml`. How the code is organized is
described in the [architecture](https://ambhora.github.io/cpdocs/explanation/architecture/) page.
