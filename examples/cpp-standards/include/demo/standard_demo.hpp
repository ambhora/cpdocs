// --------------------------------------------------------------------------------------------------
// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 cpdocs developers
// --------------------------------------------------------------------------------------------------
#pragma once

/// An API whose available declarations change with the configured C++ standard.
namespace demo {

/// Available in C++17, C++20, and C++23.
int always();

/// The integer overload is available in all configured C++ standards.
int convert(int value);

#if __cplusplus < 202002L
/// Available only in C++17; removed from the public API in C++20.
int legacy_only();
#endif

#if __cplusplus >= 202002L
/// Introduced in C++20, also available in C++23.
int cxx20_only();

/// The double overload is available from C++20 onward.
int convert(double value);
#endif

#if __cplusplus >= 202302L
/// Introduced in C++23; absent from the C++17 and C++20 manifests.
int cxx23_only();

/// The long double overload is available in C++23.
int convert(long double value);
#endif

} // namespace demo
