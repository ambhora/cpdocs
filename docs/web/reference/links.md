<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Semantic links

The API reference and the project website link to each other by meaning, not by deployment URL.

From the project website to an API entity:

```text
@apidocs::acme::division_result
@apidocs::dice.core.Die
@apidocs[v1.2.0]::acme::division_result
```

Without a version, the link goes to the default version of the site. Links point straight at the
entity's page; a symbol cpdocs does not know links to its stable `_symbols` alias instead and is
reported by `checks.broken-references`.

A line consisting of `@apidocs-versions` becomes a list of every published version, with its kind,
the default version and aliases.

From API documentation to the project website:

```markdown
[testing guide](projectdocs:reference/testing/)
```

C++ and Python entities with the same path, such as `geom::dot` and `geom.dot`, share one alias;
projects with both should keep the names distinct.
