# GeoGuard — Real-Time Geospatial Air Quality Intelligence

Working title. Folder name stayed `Wildfire Risk Platform` for continuity; rename
the GitHub repo itself to `geoguard` when you create it.

## The problem

Wildfire seasons are getting longer and smoke-driven air quality crises now affect
tens of millions of people every year, including regions that never used to worry
about it. AirNow.gov shows current conditions, but there's no lightweight, personal
tool that ingests that data continuously, stores a real history, and flags risk for
the specific places you care about.

## Scope discipline — read this before writing code

The first draft of this plan included React+TypeScript, Redis, full JWT auth with
rate limiting, SMS alerts, an admin dashboard, and multi-source data fusion. All of
it got cut from the MVP for one reason: a portfolio project with twelve
half-finished features loses to a project with four features that are provably
correct. Every item below is either in **MVP** (build this) or **Phase 2**
(earns you a legitimate "here's what I'd add next and why" answer in an interview
— don't feel behind for not building it now).

## MVP — what actually ships

- Ingestion job: scheduled polling of the AirNow API, retry/backoff, structured
  logging, data validation, **idempotent upserts** (rerunning the job must never
  duplicate or corrupt data — enforced at the database level, see `app/db/models.py`)
- PostgreSQL + PostGIS with a real spatial index, plus **one benchmarked query**
  (naive lat/lon filtering vs. `ST_DWithin` with a GiST index — real numbers, not
  a claim)
- FastAPI backend: current-conditions-by-location, historical-trend,
  saved-locations (scoped auth — just enough for per-user saved locations to work,
  not a full identity platform), and a `/health` endpoint reporting the last
  successful ingestion run
- One alert path, end-to-end, through one channel (email via SendGrid),
  built so it cannot double-fire the same alert
- A minimal but finished frontend: map + current-conditions lookup + saved
  locations. Plain JS + Leaflet, or a small focused React app if you want the
  React practice — pick one, finish it, don't build both halves in parallel
- Real pytest coverage on ingestion normalization and alert logic — the two
  places a silent bug would give wrong answers
- GitHub Actions CI running tests on every push
- Deployed and reachable at a real public URL
- A README with an architecture diagram, one ADR (`docs/adr/`), the benchmark
  number, a failure-modes section, and a short demo clip

## Phase 2 — sequenced after the MVP is provably solid

React + TypeScript rewrite of the frontend (region comparison, forecast
visualizations, exposure timeline). Redis — only if you can point to a specific
slow endpoint it fixes, with a before/after number, not "because it's expected."
NASA FIRMS wildfire data fused in alongside AQI. SMS/push alert channels.
An admin view. Calling the API "public" as a distinct feature. AWS
EventBridge + Lambda replacing the GitHub Actions cron scheduler.

## Architecture (MVP)

```
 AirNow API  -->  Ingestion job (Python, scheduled, idempotent)  -->  PostgreSQL + PostGIS
                                                                       (AWS RDS free tier)
                                                                             |
                                                                             v
                                                                  FastAPI service
                                                        /              |              \
                                              /aqi/current      /aqi/history      /health
                                                                             |
                                                                             v
                                                          Leaflet map + lookup frontend
```

## Tech stack and why

| Layer | Choice | Why |
|---|---|---|
| Ingestion | Plain Python + `requests` + `pandas` | Each API pull is a small payload — PySpark here would be overengineering, and a sharp interviewer will ask why you reached for a big-data tool on a few thousand rows. |
| Database | PostgreSQL + PostGIS on AWS RDS (free tier) | Real geospatial queries you can benchmark, and "AWS" + "PostGIS" are keywords you currently have zero evidence for. |
| API | FastAPI | Async, auto-generates OpenAPI docs, easy to test, Pydantic validation comes free. |
| Auth | Scoped to saved-locations only | Built because a real feature needs it, not decoration. No rate limiting yet — you have no traffic that justifies it. |
| Scheduling | GitHub Actions cron | Free, zero infra to manage. EventBridge + Lambda is a legitimate Phase 2 upgrade, not a Week 1 requirement. |
| Frontend | Leaflet.js + OpenStreetMap tiles, plain JS or minimal React | No API key friction, no billing risk, finishes fast enough to leave time for backend depth. |
| Alerts | SendGrid free tier, one channel | Prove the loop works end-to-end before adding more channels. |
| Historical trend analysis (Phase 2 stretch) | PySpark | Justified once you have an accumulated dataset worth batch-processing — not on the live ingestion path. |

## Build plan (6 weeks, flexible — extend if needed, don't rush past correctness)

**Week 1 — Setup + design.** Create all accounts (SETUP_CHECKLIST.md). Design the
schema in `app/db/models.py`, including the unique constraint that makes ingestion
idempotent. Get `fetch_airnow.py` calling the real API and printing live readings —
no database yet.

**Week 2 — Core pipeline.** Stand up Postgres+PostGIS locally (Docker). Write the
ingestion-to-database path using upserts. Build `/aqi/current` and `/aqi/history`
against real stored data.

**Week 3 — Idempotency, tests, CI.** Prove the ingestion job is safe to rerun.
Write pytest coverage for normalization and one endpoint. Get GitHub Actions
running tests on every push. Add the `/health` endpoint.

**Week 4 — Deploy + benchmark.** Move the database to AWS RDS free tier
(with a billing alarm). Deploy the API to a public URL. Run and document the
spatial-query benchmark in `BENCHMARKS.md`.

**Week 5 — Frontend + alerting.** Build the map/lookup/saved-locations frontend
against your now-real API. Wire up the one-channel alert path end-to-end and
verify it doesn't double-fire.

**Week 6 (flex) — Proof and polish.** Write the ADR(s) in `docs/adr/`, the
failure-modes section, and record the demo clip. If you're ahead of schedule,
this is where a *scoped* Phase 2 item (not all of them) is worth starting.

Throughout: LeetCode and applications continue every week regardless of where
the project timeline lands. This project supports the job search — it doesn't
replace the other two tracks.

## Failure modes

A system is only as trustworthy as what happens when something breaks. Four
failure modes this project handles deliberately, not accidentally:

**AirNow API is down or slow.** `fetch_current_observations()` retries up to
3 times with exponential backoff (1s, 2s, 4s) before giving up — but only for
transient failures (network errors, 5xx responses). A 4xx response (bad API
key, malformed request) fails immediately without retrying, since retrying a
request that's wrong won't make it right. If all retries are exhausted, the
run doesn't fail silently: `run_ingestion()` catches the exception, writes an
`ingestion_runs` row with `success=False` and the real error message, then
re-raises so the process still exits non-zero (visible to GitHub Actions).
`/health` reflects this immediately — `healthy = last_run.success and
time_since_last_run <= HEALTHY_INTERVAL`, so a failed run reports unhealthy
right away, not just once it becomes stale.

**A single malformed record.** Each reading in a batch is processed inside
its own `session.begin_nested()` (a SQL SAVEPOINT). If `normalize_reading()`
or the upsert raises for one reading — a missing field, an unexpected shape —
only that reading's SAVEPOINT rolls back; the exception is logged
(`logger.exception`, full traceback) and the loop continues. The rest of the
batch, including readings already saved earlier in the same run, is
unaffected. The run itself is still recorded as `success=True` with a
nonzero `error_count` — a malformed record and a broken run are different
signals, and conflating them would make `/health` cry wolf over data quality
issues that didn't actually stop the pipeline.

**Overlapping or rerun ingestion.** The `uq_reading_identity` UNIQUE
constraint on `(station_id, pollutant, observed_at)`, combined with `INSERT
... ON CONFLICT DO UPDATE`, means two overlapping runs (a scheduled run and a
manual test run, or a retried GitHub Actions job) converge on one row per
identity, not duplicates. This is enforced at the database level, not by
application-level "check before insert" logic that a race condition could
slip past.

**Double-firing the same alert.** Proven this session, not just designed:
`SavedLocation.alert_active_since` is a nullable gate — `NULL` means "not
currently alerted." A fresh unhealthy crossing sends one email and sets the
gate; every subsequent check while still unhealthy sees the gate is set and
suppresses; recovery to healthy clears the gate so a *future* crossing can
alert again. Verified end-to-end with a real saved location, a forced
unhealthy reading, and a real SendGrid send: exactly one email arrived, and a
second check against the same unhealthy state produced zero additional
emails and zero new `alert_log` rows — see `app/alerts/check_alerts.py` and
`tests/test_alerts.py` for the five scenarios this locks in (fresh crossing,
suppressed repeat, recovery, healthy-never-alerts, and a failed send not
falsely setting the gate).

## What "done" looks like for your resume

- A live public API URL you can click and see real data
- A GitHub Actions badge showing tests passing
- A real, measured benchmark number in the README, not a claim
- A short demo video showing the alert firing end-to-end
- One truthful metric you can defend without flinching in an interview
