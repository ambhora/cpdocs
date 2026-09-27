// SPDX-FileCopyrightText: 2026 cpdocs developers
// SPDX-License-Identifier: Apache-2.0
#pragma once

/// Public declarations produced by a CMake build target.
namespace acme::generated {

/// Build-generated configuration data.
struct configuration {
    int value{};
};

/// Return generated configuration information.
configuration current() noexcept;

} // namespace acme::generated
