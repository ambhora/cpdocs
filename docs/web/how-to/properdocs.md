<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Mount the API in a ProperDocs site

The project website lives in `docs/web`; the plugin builds the versioned API and mounts it:

```yaml
docs_dir: docs/web

plugins:
  - search
  - cpdocs:
      mount: reference/api
```

The plugin options and their defaults are `config: docs/cpdocs.yml`, `output: build` and
`mount: reference/api`. `properdocs serve` also documents the checked-out working tree in situ,
even when that branch is not selected by `versions.branches.include`. That working-tree version is
the default during the development server, so local and uncommitted API changes are immediately
visible. The plugin also registers the project source directories with ProperDocs' live-reload
server, so changing source files triggers a rebuild automatically. `properdocs build` keeps the
configured version-selection and default-version policy unchanged.

Pages refer to API entities with `@apidocs::demo::solve`; see
[semantic links](../reference/links.md). With `checks.broken-references: fail`, a reference to an
entity that does not exist fails the build.

## Mount nested ProperDocs sites

A root site can ask the cpdocs plugin to build nested ProperDocs projects directly into the same
output tree:

```yaml
plugins:
  - cpdocs:
      mount: reference/python-api
      subsites:
        - examples/basic-cpp
        - examples/python-basic
```

Each path is relative to the root `properdocs.yml` and must contain its own `properdocs.yml`. No
separate pre-build command is needed. `properdocs build` writes the nested site at that same path
under `site_dir`; `properdocs serve` does the same on every relevant live rebuild and gives the
nested cpdocs plugin the current-working-tree semantics used by the parent development server.
