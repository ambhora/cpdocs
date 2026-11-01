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

```python
def add(left: int, right: int) -> int:
    """Add two values.

    @param left Left operand.
    @param right Right operand.
    @return Their sum.
    """
```

`@tparam NAME`, `@param NAME`, `@return` and `@throws TYPE` are shown as titled lists below the
description, whatever their order in the comment. A field starts at a line that begins with its
command and runs to the next field or blank line, so it can wrap over several lines, and blank lines
between fields make no difference. A command in the middle of a sentence is ordinary text. The type
named by `@throws` links to its page when it is part of the documented API.

Prose may use inline code, `**strong**` text and Markdown links. Inline code that names an entity of
the documented API, such as `` `Algorithm` `` or `` `secret()` ``, links to it. Links to the project
website use `projectdocs:`.

A comment line of the form

```cpp
// CPDOCS-API-RELATES-TO: acme::other_entity
```

adds a related-entity link to the declaration that follows.
