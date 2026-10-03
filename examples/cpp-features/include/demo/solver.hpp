// SPDX-FileCopyrightText: 2026 cpdocs developers
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <cstddef>

/// A small solver whose API grows with the enabled project features.
namespace demo {

/// Settings shared by every solver configuration.
struct settings {
    /// Maximum number of iterations.
    std::size_t iterations{100};
    /// Convergence tolerance.
    double tolerance{1e-8};
};

/// Solve on the calling thread.
double solve(settings const& options) noexcept;

#if DEMO_HAVE_MPI
/// Opaque MPI communicator handle.
struct communicator {
    /// Rank of the calling process.
    int rank{};
};

/// Solve distributed over the ranks of a communicator.
double solve(settings const& options, communicator const& world) noexcept;
#endif

#if DEMO_HAVE_CUDA
/// CUDA device selection.
struct device {
    /// Device ordinal.
    int ordinal{};
};

/// Solve on a CUDA device.
double solve(settings const& options, device const& gpu) noexcept;
#endif

namespace detail {
/// Implementation detail, hidden by api.hide.cpp-namespaces.
int scratch_size(settings const& options) noexcept;
} // namespace detail

} // namespace demo
