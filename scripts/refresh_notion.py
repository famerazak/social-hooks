#!/usr/bin/env python3
"""Validate a fresh snapshot before replacing the last successful export."""
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

import import_notion


def refresh():
    destination = import_notion.OUT
    with tempfile.TemporaryDirectory(prefix='notion-refresh-', dir=destination.parent) as temp:
        staging = Path(temp)
        import_notion.OUT = staging
        import_notion.RAW = staging / 'raw'
        import_notion.main()  # Any network/incomplete-content failure leaves live data untouched.
        rows = json.loads((staging / 'prompts.json').read_text())
        if not rows or any(not row['Content Prompt'].strip() for row in rows):
            raise RuntimeError('Refusing an empty snapshot or a record without a prompt')
        if len({row['id'] for row in rows}) != len(rows):
            raise RuntimeError('Duplicate record IDs')
        with (staging / 'prompts.csv').open(newline='') as file:
            csv_rows = list(csv.DictReader(file))
        if [row['id'] for row in csv_rows] != [row['id'] for row in rows]:
            raise RuntimeError('CSV/JSON IDs differ')
        with sqlite3.connect(staging / 'prompts.sqlite3') as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('SQLite integrity check failed')
            if db.execute('SELECT count(*) FROM prompts').fetchone()[0] != len(rows):
                raise RuntimeError('SQLite/JSON counts differ')
        previous = destination / 'prompts.json'
        old = json.loads(previous.read_text()) if previous.exists() else []
        # Compare by ID: a reordered view alone does not require a new data snapshot.
        if {r['id']: r for r in old} == {r['id']: r for r in rows}:
            print(f'No content changes: {len(rows)} entries. Existing exports retained.')
            return
        old_by_id = {r['id']: r for r in old}
        new_by_id = {r['id']: r for r in rows}
        changes = {
            'added': sorted(new_by_id.keys() - old_by_id.keys()),
            'removed': sorted(old_by_id.keys() - new_by_id.keys()),
            'updated': sorted(i for i in old_by_id.keys() & new_by_id.keys() if old_by_id[i] != new_by_id[i]),
        }
        manifest_path = staging / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['changes'] = changes
        # Preserve documentation from the live dataset; it is not a generated export.
        if (destination / 'README.md').exists():
            manifest['files']['README.md'] = hashlib.sha256((destination / 'README.md').read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        destination.mkdir(parents=True, exist_ok=True)
        for source in sorted(staging.rglob('*')):
            if source.is_file():
                target = destination / source.relative_to(staging)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, target)
        print('Updated snapshot:', {k: len(v) for k, v in changes.items()})


if __name__ == '__main__':
    refresh()
