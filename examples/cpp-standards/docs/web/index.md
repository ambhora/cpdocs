<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# C++ standard-dependent API

The [API reference](api.md) merges the C++17, C++20, and C++23 builds.

- @apidocs::demo::always is available in every configured standard.
- @apidocs::demo::legacy_only exists only in C++17.
- @apidocs::demo::cxx20_only exists in C++20 and C++23.
- @apidocs::demo::cxx23_only exists only in C++23.
- @apidocs::demo::convert gains overloads in C++20 and C++23.

The header uses ordinary `__cplusplus` guards, not cpdocs-specific annotations.
