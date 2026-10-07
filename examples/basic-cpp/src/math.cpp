// SPDX-FileCopyrightText: 2026 cpdocs developers
// SPDX-License-Identifier: Apache-2.0
#include <acme/math.hpp>

namespace acme {

int add(int left, int right) noexcept { return left + right; }

division_result divide(double numerator, double denominator) noexcept {
    if (denominator == 0.0) {
        return {0.0, false};
    }
    return {numerator / denominator, true};
}

std::string_view to_string(status value) noexcept {
    return value == status::ok ? "ok" : "invalid";
}

std::string_view to_string(bool value) noexcept { return value ? "true" : "false"; }

} // namespace acme
