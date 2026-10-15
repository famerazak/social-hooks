# IG Growth Club — Content Prompts

Local snapshot of the public [Notion database](https://workable-fedora-9e0.notion.site/31372a077ac78186b6fcfb89ffa02db8?v=31372a077ac7810398bb000ca2522c4b).

Retrieved on 15 October 2026. Contains **335 current database entries**.

## Files

- `prompts.json`: readable records with source IDs and URLs, all eight named database fields, page text, timestamps, and original rich-text properties.
- `prompts.csv`: the same human-readable fields for spreadsheets; original rich-text structures are in JSON.
- `prompts.sqlite3`: `prompts` table and full-text `prompts_fts` index for searching prompts, notes, niche examples, and page text.
- `raw/`: original successful Notion responses, including schema, view metadata, rich text, and descendant blocks.
- `manifest.json`: retrieval time, coverage, omissions, request errors, and export checksums.

Fields include Content Prompt, Content Pillar, Type of Content, Best For, Week, Example on IG, Notes, and Niche Adaptation Examples. Multiple selection values remain comma-separated as supplied by Notion. Date values are rendered as ISO dates; original date annotations remain in `properties_raw`.

## Search

Use Python's built-in SQLite module (no dependencies needed):

```python
import sqlite3
con = sqlite3.connect('data/notion/prompts.sqlite3')
rows = con.execute('''
    SELECT p.prompt, p.pillar, p.notes, p.source_url
    FROM prompts p JOIN prompts_fts f ON p.id = f.id
    WHERE prompts_fts MATCH ?
    LIMIT 20
''', ('business',)).fetchall()
```

## Refresh

From `/workspace/social-hooks`, run:

```sh
python scripts/import_notion.py
```

Requires Python 3, curl, and network access to `workable-fedora-9e0.notion.site`. The importer uses unauthenticated public web endpoints, checks collection truncation, follows page cursors and content children, and rebuilds exports and the search index. Notion's internal web API may change. Refresh overwrites the snapshot; copy it first if historical versions are needed.

## Coverage and limits

The collection query returned 335 IDs and `hasMore: false`. All 335 have nonempty prompts, unique IDs, and matching CSV/JSON/SQLite counts. SQLite integrity and representative full-text searches passed. All referenced content descendants of returned entries were retrieved; request errors and missing content blocks were empty.

The saved view also references 56 IDs absent from the current collection query. Their public page responses supplied no readable record for those IDs. They are recorded in the manifest as historical references not exported; their content and status cannot be established from the public response.

Instagram/example URLs are preserved as links. External posts, videos, image binaries, attachments, and content outside this database were not downloaded. The snapshot preserves accessible database content; it is not an archive of linked third-party media or inaccessible pages.
