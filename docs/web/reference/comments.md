<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Documentation comments

In C and C++, Clang attaches documentation comments to declarations; cpdocs reads them from the
semantic AST, so a comment belongs to the declaration the compiler parsed.

```cpp
/// Add two values.
///
/// @param left Left operand.
/// @param right Right operand.
/// @return Their sum.
int add(int left, int right);
```

In Python, docstrings document modules, classes and functions; a string literal directly below an
assignment documents the assigned name.

`@tparam`, `@param`, `@return` and `@throws` are shown as titled lists below the description,
whatever their order in the comment.

Prose may use inline code, `**strong**` text and Markdown links. Links to the project website use
`projectdocs:`.

A comment line of the form

```cpp
// CPDOCS-API-RELATES-TO: acme::other_entity
```

adds a related-entity link to the declaration that follows.
