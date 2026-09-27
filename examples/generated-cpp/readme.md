<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs example: generated headers

A public header produced by a build target. `cpdocs_api(... GENERATED ... DEPENDS ...)` makes `cpdocs-prepare` build it before extraction.

```console
cpdocs build          # API reference in build/cpdocs/current
properdocs build      # project site with the versioned API, needs a Git repository
```
