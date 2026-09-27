<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs.yml

`docs/cpdocs.yml` holds documentation and publishing policy. It never names a feature or a
variant; those come from the build system. Paths are relative to the repository root, which is the
parent of `docs/`, or the directory of the file when it lives elsewhere.

```yaml
contract: 1

build:
  describe:
    - [cmake, -S, "{source}", -B, "{build}", "-DCPDOCS_REQUEST={request}",
       "-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES={cpdocs.cmake}"]

versions:
  branches:
    include: [main, "release/*"]
    variants: primary
  tags:
    select: "range:>=0.3"
    variants: all
  default: latest-tag
  aliases: {stable: latest-tag, dev: main}
  failure: skip
  legacy: current

site:
  index: docs/api/index.md
  copyright: Copyright © demo developers · Apache-2.0
  project-docs: auto

api:
  hide:
    cpp-namespaces: ["*::detail"]
    python-modules: private

checks:
  undocumented: warn
  broken-references: fail
```

Only `contract` and `build.describe` are required.

| Key | Default | Meaning |
| --- | --- | --- |
| `build.describe` | | commands answering the describe request, see the [contract](contract.md) |
| `versions.branches.include` | `[main]` | branches always built; globs allowed; a missing exact name is an error |
| `versions.branches.variants` | `all` | `all` or `primary` variants for branches |
| `versions.tags.select` | `all` | `all`, `none`, `latest:N`, `range:>=A,<B` or `refs:t1,t2`, over tags that are versions |
| `versions.tags.variants` | `all` | `all` or `primary` variants for tags |
| `versions.default` | `latest-tag` | version the site opens with: `latest-tag` or a ref name |
| `versions.aliases` | none | extra names redirecting to `latest-tag` or a ref |
| `versions.failure` | `fail` | `skip` omits a ref whose build fails |
| `versions.legacy` | `current` | refs without `cpdocs.yml` use the current one, or `skip` them |
| `site.index` | `docs/api/index.md` | introduction of the API reference |
| `site.copyright` | project developers | footer text |
| `site.project-docs` | `auto` | URL of the project website, target of `projectdocs:` links |
| `api.hide.cpp-namespaces` | none | glob patterns of C++ namespaces left out with their contents |
| `api.hide.python-modules` | `private` | `private` hides modules starting with `_`; `none` shows them |
| `checks.undocumented` | `ignore` | `warn` or `fail` when public entities have no documentation |
| `checks.broken-references` | `warn` | `ignore`, `warn` or `fail` for unknown `@apidocs` targets |

Each ref is documented with its own `cpdocs.yml`.
