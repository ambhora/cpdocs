# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""The die model."""

from __future__ import annotations

import random as _random

from ._rng import seeded


class Die:
    """A die with a fixed number of sides."""

    def __init__(self, sides: int, *, seed: int) -> None:
        """Create a die with sides faces whose rolls are reproducible from seed."""
        self.sides = sides
        self._rng: _random.Random = seeded(seed)

    def roll(self) -> int:
        """Return a face between 1 and sides."""
        return self._rng.randint(1, self.sides)


def roll(die: Die, times: int) -> list[int]:
    """Roll die times times."""
    return [die.roll() for _ in range(times)]
