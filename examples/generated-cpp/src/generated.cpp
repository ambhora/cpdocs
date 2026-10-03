// SPDX-FileCopyrightText: 2026 cpdocs developers
// SPDX-License-Identifier: Apache-2.0
#include <acme/core.hpp>
#include <acme/generated.hpp>

namespace acme {
int source_value() noexcept { return 7; }
}

namespace acme::generated {
configuration current() noexcept { return {42}; }
}
