# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Python extraction and rendering."""

from .extract import build_python_graph
from .render import RENDERING

__all__ = ["RENDERING", "build_python_graph"]
