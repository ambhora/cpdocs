// --------------------------------------------------------------------------------------------------
// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 cpdocs developers
// --------------------------------------------------------------------------------------------------
#pragma once

#include <cstddef>

namespace demo {

/// A stream of GPU work.
struct stream {
    /// The device the stream runs on.
    int device{};
};

/// Multiply every element of a vector in device memory by a factor.
///
/// @param values  the elements in device memory, scaled in place
/// @param count   the number of elements
/// @param factor  the factor
/// @param queue   the stream the kernel is queued on
void scale(double* values, std::size_t count, double factor, stream const& queue);

} // namespace demo
