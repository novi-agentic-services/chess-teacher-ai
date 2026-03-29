# M2 Progress

## Completed
- Added batch extraction script and extracted TWIC corpus from downloaded zips.
- Added PGN parser/import script:
  - `scripts/parse_pgns_to_db.py`
  - supports `--dry-run` and `--limit-games`
- Added tree aggregation SQL + runner:
  - `scripts/aggregate_tree_stats.sql`
  - `scripts/aggregate_tree_stats.py`

## Smoke Validation
- Dry-run parse validation completed:
  - games parsed: `5000`
  - game position rows walked: `433,485`

## Next execution step
Once PostgreSQL service is live in runtime, execute:

```bash
python scripts/parse_pgns_to_db.py --limit-games 50000
python scripts/aggregate_tree_stats.py
```

Then scale to full corpus with repeated runs.
