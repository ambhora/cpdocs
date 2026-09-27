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
`mount: reference/api`. `properdocs serve` rebuilds the API when a file tracked by Git changes.

Pages refer to API entities with `@apidocs::demo::solve`; see
[semantic links](../reference/links.md). With `checks.broken-references: fail`, a reference to an
entity that does not exist fails the build.
