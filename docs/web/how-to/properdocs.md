<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Embed the API in a project website

A project website usually describes the current state of the project, while its API changes from
release to release. The cpdocs ProperDocs plugin keeps the two apart: the website is built once, and
every documented version of the API is published below one directory of it, the mount point. The
website itself needs no versioning.

The project website lives in `docs/web`; the plugin builds the versioned API and mounts it:

```yaml
docs_dir: docs/web

plugins:
  - search
  - cpdocs:
      mount: reference/api
```

The plugin options and their defaults are `config: docs/cpdocs.yml`, `output: build` and
`mount: reference/api`. The mount directory is replaced on every build, so it must be a proper
subdirectory of the site: the site root, `.`, `..` and absolute paths are rejected.

`properdocs build` publishes the versions listed in `cpdocs.yml`. `properdocs serve` also documents
the checked-out working tree and makes it the default, so changes to the API show up while editing,
and changing a source file triggers a rebuild. A page can list the published versions with
`@apidocs-versions`.

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
