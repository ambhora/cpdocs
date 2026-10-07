<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Build the documentation in CI

cpdocs runs from a fresh checkout: it builds every feature set of every selected ref itself. The
checkout needs the history, tags and branches it documents, and the job needs Clang for C and C++
units.

## GitHub Actions

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
- run: pip install 'cpdocs[properdocs]' mkdocs-materialx
- run: properdocs build
- uses: actions/upload-pages-artifact@v3
  with:
    path: build/site
```

## GitLab CI

```yaml
docs:
  variables:
    GIT_DEPTH: 0
  script:
    - git fetch --tags origin '+refs/heads/*:refs/remotes/origin/*'
    - pip install 'cpdocs[properdocs]' mkdocs-materialx
    - properdocs build
  artifacts:
    paths: [build/site]
```

Branch names are matched against local and remote-tracking branches. The branch being built is
read from `CI_COMMIT_BRANCH`, `GITHUB_HEAD_REF` or `GITHUB_REF_NAME`, so the detached checkout of a
CI job is documented as its working tree. `CPDOCS_CURRENT_BRANCH` overrides all three.

A project may live in a subdirectory of its repository. Every ref is then checked out as a whole
and the same subdirectory is documented. Because `versions` is explicit, a configured ref that does not
contain the project is an error rather than being silently skipped. The examples in the cpdocs repository
use this same mechanism.

A build system that runs cpdocs itself passes its own build directory:

```console
cpdocs versions --output "$BUILD_DIR"
```
