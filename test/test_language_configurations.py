# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""End-to-end integration of Keyso language spaces and the existing build contract."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

import pytest

from conftest import fake_project
from cpdocs.build import build_current
from cpdocs.config import load_config
from cpdocs.providers.contract import language_template_values


def test_flatten_language_template_values_and_reject_non_scalars() -> None:
    assert language_template_values(
        {"cxx": {"standard": 23}, "python": {"version": "3.12"}, "optimized": True}
    ) == {"cxx.standard": "23", "python.version": "3.12", "optimized": "true"}
    with pytest.raises(RuntimeError, match="scalar"):
        language_template_values({"python": {"version": ["3.11", "3.12"]}})
    with pytest.raises(RuntimeError, match="reserved"):
        language_template_values({"source": "untrusted"})


def test_unspecified_languages_keep_single_legacy_configuration(tmp_path: Path) -> None:
    project = fake_project(tmp_path / "project")
    config = load_config(project / "docs" / "cpdocs.yml")
    assert config.language_configurations == ({},)
    result = build_current(config, output=project / "build")
    assert list(result.feature_sets) == ["feature-set-001"]
    assert result.metadata["language_configurations"] == [{}]


def _project_with_language_variants(root: Path, expression: str) -> Path:
    project = fake_project(root)
    (project / "language_provider.py").write_text(
        """import json
import sys
from pathlib import Path

phase, cxx, python, output = sys.argv[1:5]
with Path('build-records.jsonl').open('a', encoding='utf-8') as stream:
    stream.write(json.dumps({'phase': phase, 'cxx': cxx, 'python': python}) + '\\n')

if phase == 'feature-sets':
    combinations = [[]] if cxx == '17' else [[], ['new-api']]
    data = {
        'cpdocs-feature-sets': 1, 'generator': 'fake',
        'project': {'name': 'fake', 'version': '1.0'},
        'feature-sets': [{'features': values} for values in combinations],
    }
else:
    selection = json.loads(Path(sys.argv[5]).read_text())
    assert isinstance(selection['features'], list)
    data = {
        'cpdocs-manifest': 1,
        'units': [{'id': 'pkg', 'language': 'python', 'package': 'pkg',
                   'api': [{'path': 'src/pkg'}]}],
    }
Path(output).write_text(json.dumps(data), encoding='utf-8')
""",
        encoding="utf-8",
    )
    command = shlex.quote(sys.executable) + ' language_provider.py'
    (project / "docs" / "cpdocs.yml").write_text(
        "contract: 3\nlanguages:\n" + expression
        + "build:\n"
        + f'  feature-sets: >-\n    {command} feature-sets '
        + '"{{cxx.standard}}" "{{python.version}}" "{{output-file}}"\n'
        + f'  build: >-\n    {command} build '
        + '"{{cxx.standard}}" "{{python.version}}" "{{output-file}}" "{{feature-set}}"\n',
        encoding="utf-8",
    )
    return project


def test_explicit_keyso_pairs_and_variant_feature_discovery(tmp_path: Path) -> None:
    pytest.importorskip("keyso")
    project = _project_with_language_variants(
        tmp_path / "project",
        "  _set:\n"
        "    - cxx: {standard: 17}\n      python: {version: '3.11'}\n"
        "    - cxx: {standard: 23}\n      python: {version: '3.12'}\n",
    )
    graph = build_current(load_config(project / "docs/cpdocs.yml"), output=project / "build")
    assert len(graph.feature_sets) == 3  # one feature set for C++17, two for C++23
    records = [json.loads(line) for line in (project / "build-records.jsonl").read_text().splitlines()]
    assert {(item["cxx"], item["python"]) for item in records} == {
        ("17", "3.11"), ("23", "3.12")
    }
    assert len([item for item in records if item["phase"] == "feature-sets"]) == 2
    assert len([item for item in records if item["phase"] == "build"]) == 3
    configurations = {key: data["languages"] for key, data in graph.feature_sets.items()}
    assert {entry["cxx"]["standard"] for entry in configurations.values()} == {17, 23}
    assert len({key for key in graph.feature_sets}) == 3
    for language in ("language-001", "language-002"):
        assert (project / "build/cpdocs/work/current/language-configurations" / language
                / "feature-sets/feature-sets.json").exists()
    feature_page = (project / "build/cpdocs/current/feature-sets/index.html").read_text()
    assert "cxx.standard=17" in feature_page
    assert "cxx.standard=23" in feature_page
    assert "python.version=3.11" in feature_page


def test_keyso_product_without_implicit_cross_language_constraints(tmp_path: Path) -> None:
    pytest.importorskip("keyso")
    project = _project_with_language_variants(
        tmp_path / "project",
        "  _product:\n"
        "    - cxx:\n        _nested:\n          standard: [17, 23]\n"
        "    - python:\n        _nested:\n          version: ['3.11', '3.12']\n",
    )
    configuration = load_config(project / "docs/cpdocs.yml")
    assert len(configuration.language_configurations) == 4
    graph = build_current(configuration, output=project / "build")
    assert len(graph.feature_sets) == 6
