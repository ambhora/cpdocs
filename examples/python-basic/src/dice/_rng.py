# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Private helpers; hidden from the API reference."""

import random as _random


def seeded(seed: int) -> _random.Random:
    """Return a seeded generator."""
    return _random.Random(seed)
