# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""C-family extraction and rendering."""

from .extract import extract_clang_graph
from .render import RENDERING

__all__ = ["RENDERING", "extract_clang_graph"]
