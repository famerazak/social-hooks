# Social hooks data source

A local copy of the public IG Growth Club content-prompt database, with JSON, CSV, and searchable SQLite exports under [`data/notion`](data/notion/README.md).

## Daily refresh

GitHub Actions runs `.github/workflows/refresh-notion.yml` daily at **07:17 UTC** (08:17 Madrid in winter, 09:17 in summer). Scheduled runs may be delayed by GitHub. Use **Actions → Refresh Notion content → Run workflow** for an immediate refresh.

The job fetches and validates a temporary snapshot first. Fetch/validation failures preserve the previous exports and fail the Actions run. No content changes means no commit. New entries, edits, and removals update the snapshot and create a commit, including source links and change IDs in the manifest.

The workflow requires Actions to be enabled and its `GITHUB_TOKEN` to have repository contents write permission. It uses the built-in Actions token; no Notion secret is required while the source remains public. Scheduled workflows run from the default branch. GitHub can disable inactive scheduled workflows in public repositories after 60 days without repository activity; re-enable the workflow in Actions if needed.

Run manually with Python 3 and curl:

```sh
python scripts/refresh_notion.py
```

Run safeguard tests:

```sh
python -m unittest discover -s tests -v
```

The original importer remains available in `scripts/import_notion.py`; use the refresh wrapper for routine updates because it protects the last successful snapshot during retrieval and validation.
