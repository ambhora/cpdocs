// SPDX-FileCopyrightText: 2026 cpdocs developers
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <string_view>

/// Public API for the small arithmetic example.
namespace acme {

/// Result returned by a checked division.
struct division_result {
    /// Quotient when the operation succeeds.
    double value{};

    /// Whether a value is available.
    bool valid{};

    /// Return true when the division succeeded.
    bool ok() const noexcept { return valid; }
};

/// A compact status used by the string conversion overload family.
enum class status {
    ok,
    invalid,
};

/// Add two integers.
///
/// @param left Left operand.
/// @param right Right operand.
/// @return The sum of both operands.
int add(int left, int right) noexcept;

/// Divide two floating-point values.
///
/// A zero denominator returns an invalid result rather than throwing.
division_result divide(double numerator, double denominator) noexcept;

/// Return the textual representation of a status.
std::string_view to_string(status value) noexcept;

/// Return a textual boolean. This overload intentionally shares the same function family page.
std::string_view to_string(bool value) noexcept;

} // namespace acme

/// Major version of the example API.
#define ACME_API_VERSION_MAJOR 1
