<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs

cpdocs generates semantic, versioned API documentation for C, C++, CUDA, HIP, Fortran, Python and Rust projects.

It asks the project's build system, through a small JSON contract, for the concrete feature sets to
document. It builds each feature set independently, consumes the resulting manifest, extracts the API
with Clang for C-family languages, source modules for Fortran, `ast` for Python or rustdoc JSON for
Rust, and merges the results. Implementation files from the manifest are kept in the file hierarchy
without becoming API entities.
Feature-set availability and API language are tracked independently. The versions
to publish are an explicit ordered list in `cpdocs.yml`.

```console
cpdocs build          # document the working tree into build/cpdocs/current
cpdocs versions       # document the configured versions
properdocs build      # project website with the versioned API mounted
```

## Language configurations

The optional `languages` field in `docs/cpdocs.yml` is a [Keyso configuration
space](https://ambhora.github.io/keyso/language/syntax/). cpdocs expands it using pykeyso,
then runs `build.feature-sets` once per concrete configuration and `build.build` once per
feature set discovered for that configuration. Both command templates receive dotted placeholders
from the resulting nested dictionaries, such as `{{cxx.standard}}`, `{{c.standard}}`,
`{{fortran.standard}}`, `{{python.version}}`, or `{{rust.edition}}`. The build system decides
how to apply each value; cpdocs does not translate them into compiler flags.

```yaml
languages:
  _product:
    - cxx:
        _nested:
          standard: [17, 20, 23]
    - python:
        _nested:
          version: ["3.11", "3.12"]

build:
  feature-sets: >-
    cmake -S "{{source}}" -B "{{tmpdir}}"
    -DCMAKE_CXX_STANDARD="{{cxx.standard}}"
    -DPROJECT_FEATURE_SETS_OUTPUT="{{output-file}}"
  build: >-
    cmake -S "{{source}}" -B "{{tmpdir}}"
    -DCMAKE_CXX_STANDARD="{{cxx.standard}}"
    -DPROJECT_FEATURE_SET="{{feature-set}}"
    -DPROJECT_CPDOCS_OUTPUT="{{output-file}}"
    && cmake --build "{{tmpdir}}" --target project.cpdocs
```

Use `_set` for explicitly paired combinations rather than the `_product` Cartesian product:

```yaml
languages:
  _set:
    - cxx: {standard: 17}
      python: {version: "3.11"}
    - cxx: {standard: 23}
      python: {version: "3.12"}
```

Each concrete configuration has its own work directory. The merged API records both the
language configuration and feature set in symbol availability, including overload signatures.
If `languages` is omitted, cpdocs performs the original single build configuration, and the
existing `{{source}}`, `{{tmpdir}}`, `{{output-file}}`, `{{feature-set}}`, and `{{python}}`
placeholders continue to work unchanged.

The configuration lives in `docs/cpdocs.yml`, the API introduction in `docs/api/index.md` and the
ProperDocs pages in `docs/web`. The documentation starts at `docs/web/index.md`; the `examples/`
directory holds standalone projects that the test suite builds.

## Development

```console
uv sync
uv run pytest
uv run ruff check && uv run ruff format --check
```

The C and C++ tests need `clang++`, `cmake` and `ninja`. Building the Rust example/site also needs
the nightly toolchain pinned by `examples/rust-basic/rust-toolchain.toml`.
