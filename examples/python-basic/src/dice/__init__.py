# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Roll dice and combine the results."""

from .core import Die, roll

__all__ = ["Die", "roll", "SIDES"]

SIDES = 6
"""Number of sides of a standard die."""
