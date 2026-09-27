<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs

cpdocs generates semantic, versioned API documentation for C, C++, Python and Rust projects.

It asks the project's build system, through a small JSON contract, which variants of the API exist
and how to read each of them. It then extracts every variant, Clang for C and C++, `ast` for Python
and rustdoc JSON for Rust, merges them into one reference, and publishes one version per configured
branch and tag. A CMake adapter ships with cpdocs; other build systems implement the same contract.

```console
cpdocs build          # document the working tree into build/cpdocs/current
cpdocs versions       # document the configured branches and tags
properdocs build      # project website with the versioned API mounted
```

The configuration lives in `docs/cpdocs.yml`, the API introduction in `docs/api/index.md` and the
ProperDocs pages in `docs/web`. The documentation starts at `docs/web/index.md`; the `examples/`
directory holds standalone projects that the test suite builds.

## Development

```console
uv sync
uv run pytest
uv run ruff check && uv run ruff format --check
```

The C and C++ tests need `clang++`, `cmake` and `ninja`; they are skipped when these are missing.
