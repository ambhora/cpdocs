<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Entity kinds

Every documented declaration is an entity of one kind, such as a `struct` or a `function`. Kinds
belong to a language: each language declares the kinds its extractor produces, in
`cpdocs.languages.<language>.entities`, together with the label and badge readers see, the position
of the kind in member lists, and the heading it is listed under on the page of a type. A kind that
is not declared for its language is an error, so the tables below are complete.

## C, C++, CUDA and HIP

| Kind | Declaration |
| --- | --- |
| `namespace` | a namespace |
| `class`, `struct`, `union` | a record, including class templates and their specializations |
| `enum` | an enumeration; its enumerators are `constant` members |
| `type_alias` | a `typedef` or `using` alias |
| `concept` | a C++20 concept |
| `constructor` | a constructor of a record |
| `deduction_guide` | a class template argument deduction guide |
| `function` | a free function, including function templates |
| `method` | a member function, destructor or conversion function |
| `attribute` | a data member of a record |
| `variable` | a variable at namespace scope or a static data member |
| `constant` | an enumerator |
| `macro` | a function-like or object-like macro defined in a public header |

## Fortran

| Kind | Declaration |
| --- | --- |
| `module` | a module |
| `derived_type` | a derived type, `type :: name` |
| `function` | a function of a module |
| `subroutine` | a subroutine of a module |

## Python

| Kind | Declaration |
| --- | --- |
| `package` | a package, a directory with `__init__.py` |
| `module` | a module, one `.py` or `.pyi` file |
| `class` | a class |
| `protocol` | a class deriving from `typing.Protocol` |
| `enum` | a class deriving from `enum.Enum`; its members are `constant` members |
| `type_alias` | a type alias, such as `Vector = list[float]` or a `type` statement |
| `constructor` | the `__init__` method of a class |
| `function` | a function of a module |
| `method` | a function of a class |
| `property` | a `@property` of a class |
| `attribute` | an annotated or assigned name of a module or class |
| `constant` | an upper-case module-level name or an enumeration member |

## Rust

| Kind | Declaration |
| --- | --- |
| `module` | a module, the crate root included |
| `struct`, `union` | a struct or union |
| `enum` | an enumeration; its variants are `enum_value` members |
| `trait` | a trait |
| `trait_alias` | a trait alias |
| `type_alias` | a type alias or an associated type |
| `function` | a free function |
| `method` | a function of an inherent `impl` block |
| `field` | a field of a struct |
| `enum_value` | a variant of an enumeration |
| `variable` | a `static` item |
| `constant` | a `const` item or an associated constant |
| `macro` | a `macro_rules!` macro or a procedural macro |
