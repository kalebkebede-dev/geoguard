# ADR 0001: PostgreSQL + PostGIS over MongoDB with geo-indexes

Status: Decided and shipped. Written after living with the choice through
ingestion, benchmarking, and two schema expansions (Week 3's `ingestion_runs`,
Week 5's `users`/`saved_locations`/`alert_log`), not before.

## Context

The project needed: radius queries around an arbitrary point ("what's the
AQI within N miles of here"), a real spatial index we could benchmark against
a naive filter with actual numbers, an idempotency mechanism that survives
overlapping/rerun ingestion jobs, and — as the project grew — genuine
relational structure: readings belong to stations, saved locations belong to
users, alert log entries belong to saved locations.

## Options considered

- PostgreSQL + PostGIS
- MongoDB with `2dsphere` geo-indexes and `$geoNear`/`$nearSphere`
- SQLite with a manual bounding-box filter (rejected early — no real spatial
  index to benchmark against, defeats the point of the benchmark deliverable)

## Decision

PostgreSQL + PostGIS, on AWS RDS.

## Reasoning

Not "Postgres is popular." Three specific things that were actually true for
this project:

1. **The idempotency story is a relational database feature, used directly.**
   `uq_reading_identity` — a UNIQUE constraint on `(station_id, pollutant,
   observed_at)` — combined with `INSERT ... ON CONFLICT DO UPDATE` is the
   entire mechanism that makes rerunning ingestion safe. That's not a design
   pattern layered on top of Postgres; it's Postgres's own conflict-resolution
   primitive doing the actual work. MongoDB has unique indexes too, but the
   atomic "insert-or-update-in-one-statement" semantics we needed map onto
   `ON CONFLICT` exactly, not onto an application-level find-then-upsert.

2. **The schema turned out to be genuinely relational, not document-shaped.**
   By Week 5 there were real foreign keys everywhere — `readings.station_id`,
   `saved_locations.user_id`, `alert_log.saved_location_id` — and real
   cross-table queries (find a user's saved locations, find the latest
   reading per station per pollutant). That's the access pattern relational
   databases are built for. Modeling this in MongoDB would mean either
   denormalizing (accepting update-anomaly risk on data that legitimately
   changes, like AQI values) or doing the joins in application code anyway.

3. **We could prove the spatial index claim with real numbers, using tooling
   we already had.** `EXPLAIN ANALYZE` against a real GiST index let us
   measure, not assert, the naive-vs-indexed difference (see
   `BENCHMARKS.md`). That same investigation is what caught a real bug: an
   early version of the indexed query cast the column to `::geography`,
   which silently prevented Postgres from using the GiST index built on the
   raw `geometry` column — confirmed by seeing a `Seq Scan` in the query plan
   where an `Index Scan` was expected, not by assuming the index was working.
   MongoDB's `2dsphere` + `$nearSphere` would have avoided that specific
   geometry/geography distinction entirely, but at the cost of not having
   this project's actual benchmark deliverable to point to.

## Consequences

- **Real, earned complexity cost**: PostGIS's `geometry` vs `geography` type
  distinction is not obvious, and got a query wrong on the first attempt.
  That mistake only got caught because we checked `EXPLAIN ANALYZE` instead
  of trusting the code. This is a real skill/context cost MongoDB's simpler
  point-radius model doesn't have.
- **Migrations are more ceremony than a document store.** Every schema
  change — adding `ingestion_runs`, adding the `location` geometry column
  (with an explicit add-nullable → backfill → set-NOT-NULL sequence to avoid
  breaking existing rows), adding `users`/`saved_locations`/`alert_log` —
  went through an Alembic migration. A document store would have let some of
  this happen implicitly. That ceremony is also exactly what gives us
  enforced `NOT NULL`, `UNIQUE`, and foreign-key guarantees at the database
  level rather than convention in application code — a deliberate trade,
  not a free win either direction.
- **Local dev needed the PostGIS-flavored Postgres image** (`postgis/postgis`,
  not plain `postgres`), and RDS needed an explicit `CREATE EXTENSION postgis`
  step after the instance came up — a small extra step a document store
  wouldn't have required.
- **The trade-off was validated, not just assumed**: the real benchmark
  numbers show the indexed approach winning ~5x at the full request level
  once ORM hydration cost is accounted for, even though raw SQL execution
  time alone favored a sequential scan at this row count. That nuance is
  worth being able to explain, and it's evidence the decision to invest in
  PostGIS specifically (not just "a database with an index") paid off.
