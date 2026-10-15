import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import refresh_notion as refresh


class RefreshTest(unittest.TestCase):
    def test_refresh_preserves_or_updates_snapshot(self):
        for outcome in ('failure', 'unchanged', 'changed', 'empty'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as temp:
                destination = Path(temp) / 'notion'
                destination.mkdir()
                original = [{'id': 'one', 'Content Prompt': 'Original'}]
                path = destination / 'prompts.json'
                path.write_text(json.dumps(original))
                before = path.read_bytes()

                def fetch():
                    stage = refresh.import_notion.OUT
                    if outcome == 'failure':
                        (stage / 'prompts.json').write_text('partial')
                        raise RuntimeError('Simulated network failure')
                    rows = [] if outcome == 'empty' else [dict(original[0])]
                    if outcome == 'changed':
                        rows[0]['Content Prompt'] = 'Updated'
                    (stage / 'prompts.json').write_text(json.dumps(rows))
                    with (stage / 'prompts.csv').open('w', newline='') as file:
                        writer = csv.DictWriter(file, fieldnames=['id', 'Content Prompt'])
                        writer.writeheader()
                        writer.writerows(rows)
                    with sqlite3.connect(stage / 'prompts.sqlite3') as db:
                        db.execute('CREATE TABLE prompts (id TEXT)')
                        db.executemany('INSERT INTO prompts VALUES (?)', [(r['id'],) for r in rows])
                    (stage / 'manifest.json').write_text('{"files": {}}')

                with patch.object(refresh.import_notion, 'OUT', destination), patch.object(refresh.import_notion, 'RAW', destination / 'raw'), patch.object(refresh.import_notion, 'main', fetch), contextlib.redirect_stdout(io.StringIO()):
                    if outcome in ('failure', 'empty'):
                        with self.assertRaises(RuntimeError):
                            refresh.refresh()
                    else:
                        refresh.refresh()
                if outcome == 'changed':
                    self.assertEqual(json.loads(path.read_text())[0]['Content Prompt'], 'Updated')
                    self.assertEqual(json.loads((destination / 'manifest.json').read_text())['changes']['updated'], ['one'])
                else:
                    self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
