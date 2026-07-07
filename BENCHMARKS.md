# Benchmarks

This file is not optional decoration — it's the single highest-leverage piece of
credibility evidence in this whole project. A claim like "uses spatial indexing
for efficient queries" is worth nothing in an interview. A real number is worth
more than every other line on your resume bullet for this project combined.

## Spatial query: naive filter vs. PostGIS + GiST index

Once you have a meaningful number of rows in `readings` (a few thousand is
enough to show a real difference):

1. Run the same "find all stations within 50 miles of point X" query two ways:
   - Naive: pull all rows, filter by a manual lat/lon bounding-box calculation
     in Python
   - Indexed: `ST_DWithin(location, ST_MakePoint(:lon, :lat)::geography, :meters)`
     with a GiST index on the `location` column
2. Time both with `EXPLAIN ANALYZE` in Postgres, and with a simple Python
   `time.perf_counter()` wrapper around the actual API call.
3. Record both numbers here, with your row count and hardware/instance size
   noted, so the comparison is honest and reproducible.

| Approach | Row count | Time | Notes |
|---|---|---|---|
| Naive (no index) | TODO | TODO | TODO |
| PostGIS + GiST index | TODO | TODO | TODO |

## Ingestion job

| Metric | Value |
|---|---|
| Stations polled per run | TODO |
| Average run duration | TODO |
| Scheduled interval | TODO |

Fill these in for real once the pipeline is running — don't estimate them.
