# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Python bindings of the geometry library."""


def dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """Dot product of two 3-tuples."""
    return sum(x * y for x, y in zip(a, b, strict=True))
