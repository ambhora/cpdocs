# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
import json
import sys
from pathlib import Path

phase, cxx, python, output = sys.argv[1:5]
with Path('build-records.jsonl').open('a', encoding='utf-8') as stream:
    stream.write(json.dumps({'phase': phase, 'cxx': cxx, 'python': python}) + '\n')

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
