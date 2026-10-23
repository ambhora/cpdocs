<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Document several versions

`versions` in `cpdocs.yml` lists the branches and tags to publish, in order:

```yaml
versions: [main, v2.0.0, v1.0.0]
```

```console
cpdocs versions
```

cpdocs checks out each entry in a temporary Git worktree, documents it with all its build variants,
and writes it to `build/cpdocs/versions/<name>/`. The first entry is the default version: the
version index redirects to it and links without a version go to it. Readers switch between versions
on every page.

- **Branches and tags.** A name is looked up among tags, local branches and remote-tracking
  branches, so a CI checkout with fetched branches works without creating local ones.
- **The hooks of today.** Every version is built with the hooks in the current `cpdocs.yml`, so old
  tags need no cpdocs configuration of their own; their own build scripts still run as they are in
  that tag. The theme also comes from the current tree, and the API introduction from each version.
- **The checked-out branch.** A listed branch that is checked out is documented from the working
  tree rather than from Git, so its reference matches the code at hand. In a detached CI checkout
  the branch is read from `GITHUB_HEAD_REF`, `CI_COMMIT_BRANCH` or `GITHUB_REF_NAME`, and
  `CPDOCS_CURRENT_BRANCH` overrides all of them. `properdocs serve` also puts the working tree first,
  so uncommitted changes are visible while editing.

To publish the versions inside the project website, see
[Embed the API in a project website](properdocs.md).
