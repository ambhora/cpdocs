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
    persist-credentials: false
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

## What a documentation build trusts

Building documentation runs code. cpdocs runs the `build.feature-sets` and `build.build` commands
from `cpdocs.yml`, which build the project, for every documented ref; the build scripts of an older
tag run as they are in that tag; and the compiler flags a compile database supplies, plugins
included, are passed to Clang. Treat `cpdocs.yml`, the build system and every documented ref as
code the job executes:

- do not build documentation for untrusted changes in a job that holds secrets or write
  permissions, and never under `pull_request_target`;
- give the documentation job read-only repository permissions and no persisted Git credentials,
  and deploy from a separate job that does not build;
- keep secrets out of the checkout: cpdocs publishes the source files units declare, limited to
  files Git tracks in the checkout and to symbolic links that stay inside the project.
