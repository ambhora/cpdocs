<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs example: feature sets

A header-only solver whose API depends on `PROJECT_FEATURES`. CMake exposes the three concrete feature sets directly through the cpdocs contract. `tools/minibuild.py` answers the same requests without CMake: `cpdocs build --config docs/cpdocs-minibuild.yml`.

```console
cpdocs build          # API reference in build/cpdocs/current
properdocs build      # project site with the versioned API, needs a Git repository
```
