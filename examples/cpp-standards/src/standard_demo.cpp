// --------------------------------------------------------------------------------------------------
// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 cpdocs developers
// --------------------------------------------------------------------------------------------------
#include "demo/standard_demo.hpp"

namespace demo {

int always() { return 17; }
int convert(int value) { return value; }

#if __cplusplus < 202002L
int legacy_only() { return 17; }
#endif

#if __cplusplus >= 202002L
int cxx20_only() { return 20; }
int convert(double value) { return static_cast<int>(value); }
#endif

#if __cplusplus >= 202302L
int cxx23_only() { return 23; }
int convert(long double value) { return static_cast<int>(value); }
#endif

} // namespace demo
