# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""What every language extractor receives besides the manifest unit it documents.

Each language package provides one ``extract_unit(unit, context)`` function that turns a manifest
unit of its language into an API graph. The build loop knows nothing about languages: it looks the
function up with ``cpdocs.languages.extractor_for`` and passes it a ``UnitContext``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..config import CpdocsConfig
from ..contract import UnitManifest
from ..model import ApiGraph


@dataclass(frozen=True)
class UnitContext:
    """The build in which one unit is extracted.

    ``feature_set`` is the key the graph's entities are recorded under, ``work_directory`` a
    scratch directory reserved for this unit, and ``language_configuration`` the concrete Keyso
    language configuration being built, empty when ``cpdocs.yml`` has no ``languages``.
    """

    project: str
    version: str
    project_root: Path
    feature_set: str
    work_directory: Path
    language_configuration: dict[str, object]
    config: CpdocsConfig


UnitExtractor = Callable[[UnitManifest, UnitContext], ApiGraph]

__all__ = ["UnitContext", "UnitExtractor"]
