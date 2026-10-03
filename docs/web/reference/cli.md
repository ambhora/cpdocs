<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Command line

```text
cpdocs build [--config docs/cpdocs.yml] [--output build] [--label main]
cpdocs versions [--config docs/cpdocs.yml] [--output build]
cpdocs manifest python feature-sets ...
cpdocs manifest python build ...
```

`build` documents the working tree into `<output>/cpdocs/current`. It always documents every
feature set returned by `build.feature-sets`.

`versions` documents the exact ordered `versions:` list from `cpdocs.yml` into
`<output>/cpdocs/versions`.

`manifest python` is a small provider for plain Python projects.

Feature-set inputs, manifests, scratch/build directories and command logs are kept below
`<output>/cpdocs/work/<version>/feature-sets/`.
