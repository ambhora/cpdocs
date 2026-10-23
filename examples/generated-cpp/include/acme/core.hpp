// --------------------------------------------------------------------------------------------------
// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 cpdocs developers
// --------------------------------------------------------------------------------------------------
#pragma once

// Both headers below exist only in the build directory: the build generates them.
#include <acme/status.hpp>
#include <acme/version.hpp>

/// Checked arithmetic on counters.
namespace acme {

/// Add two counters without wrapping around.
///
/// @param left   the first counter
/// @param right  the second counter
/// @param sum    receives the sum when the result is status::ok
/// @return status::ok, status::negative for a negative argument, or status::overflow
status add(int left, int right, int& sum) noexcept;

} // namespace acme
