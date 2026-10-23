// --------------------------------------------------------------------------------------------------
// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 cpdocs developers
// --------------------------------------------------------------------------------------------------
#include <acme/core.hpp>

#include <limits>

namespace acme {

status add(int left, int right, int& sum) noexcept {
    if (left < 0 || right < 0) {
        return status::negative;
    }
    if (left > std::numeric_limits<int>::max() - right) {
        return status::overflow;
    }
    sum = left + right;
    return status::ok;
}

} // namespace acme
