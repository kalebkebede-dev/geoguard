"""
Week 1 goal: make this script call the real AirNow API and print live readings.
Don't touch the database from this file yet — prove the API call works first.

AirNow API docs: https://docs.airnowapi.org/
Look at the "Current Observations by Lat/Long" endpoint to start.
"""

import logging
import os
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from app.db.models import IngestionRun
from app.db.persistence import save_reading
from app.db.session import SessionLocal

load_dotenv()

logger = logging.getLogger(__name__)

AIRNOW_API_KEY = os.getenv("AIRNOW_API_KEY")
AIRNOW_BASE_URL = "https://www.airnowapi.org/aq/observation/latLong/current/"

MAX_ATTEMPTS = 3
INITIAL_BACKOFF_SECONDS = 1  # doubles each retry: 1s, 2s, 4s


def fetch_current_observations(lat: float, lon: float, distance_miles: int = 25) -> list[dict]:
    """
    TODO: Call the AirNow current-observations-by-lat/long endpoint and return
    the parsed JSON response as a list of reading dicts.

    Params you'll need to pass: format=application/json, latitude, longitude,
    distance, API_KEY.

    Handle the case where the API returns an empty list (no stations nearby)
    and the case where the request fails (bad key, network error, etc.) —
    don't let this crash silently. Decide what "no data" should look like to
    the rest of the pipeline.
    """
    params = {
        "format": "application/json",
        "latitude": lat,
        "longitude": lon,
        "distance": distance_miles,
        "API_KEY": AIRNOW_API_KEY,
    }

    backoff = INITIAL_BACKOFF_SECONDS
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(AIRNOW_BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and 400 <= status < 500:
                logger.error("AirNow rejected the request (HTTP %s) — not retrying: %s", status, exc)
                raise
            if attempt == MAX_ATTEMPTS:
                logger.error("AirNow still failing after %s attempts (HTTP %s): %s", MAX_ATTEMPTS, status, exc)
                raise
            logger.warning("AirNow returned HTTP %s, retrying (attempt %s/%s)", status, attempt, MAX_ATTEMPTS)
        except requests.exceptions.RequestException as exc:
            if attempt == MAX_ATTEMPTS:
                logger.error("Network error calling AirNow after %s attempts: %s", MAX_ATTEMPTS, exc)
                raise
            logger.warning("Network error calling AirNow, retrying (attempt %s/%s): %s", attempt, MAX_ATTEMPTS, exc)

        time.sleep(backoff)
        backoff *= 2


def normalize_reading(raw_reading: dict) -> dict:
    """
    TODO: Take one raw reading from the AirNow response and reshape it into
    the schema you designed for your database (station id/name, lat, lon,
    pollutant type, AQI value, category, observed timestamp).

    This is also where you'd handle unit differences if you add a second
    data source (e.g., NASA FIRMS) later — normalize everything to one
    consistent shape before it reaches storage.
    """
    observed_at = datetime.strptime(raw_reading["DateObserved"].strip(), "%Y-%m-%d").replace(
        hour=raw_reading["HourObserved"]
    )
    return {
        "station_id": f"{raw_reading['ReportingArea']}, {raw_reading['StateCode']}",
        "station_name": raw_reading["ReportingArea"],
        "latitude": raw_reading["Latitude"],
        "longitude": raw_reading["Longitude"],
        "pollutant": raw_reading["ParameterName"],
        "aqi_value": raw_reading["AQI"],
        "category": raw_reading["Category"]["Name"],
        "observed_at": observed_at,
    }


def _record_run(session, started_at, success, fetched_count=0, new_count=0,
                 updated_count=0, error_count=0, error_message=None):
    """Write one row to ingestion_runs — the /health endpoint's data source."""
    session.add(IngestionRun(
        started_at=started_at,
        completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        success=success,
        fetched_count=fetched_count,
        new_count=new_count,
        updated_count=updated_count,
        error_count=error_count,
        error_message=error_message,
    ))


def run_ingestion(lat: float, lon: float) -> None:
    """
    Fetch current observations for one location and persist them. A single
    malformed reading is logged and skipped — it must not abort the rest
    of the batch. Every run, success or failure, writes one row to
    ingestion_runs for /health to report on.
    """
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session = SessionLocal()

    try:
        raw_readings = fetch_current_observations(lat, lon)
    except Exception as exc:
        # Fetch itself failed even after retries — a real run failure, not a
        # per-reading issue. Record it so /health can report it, then let the
        # exception propagate so the process still exits non-zero (visible
        # to whatever scheduler is watching, e.g. GitHub Actions cron later).
        logger.error("Ingestion run failed before fetching any data: %s", exc)
        _record_run(session, started_at, success=False, error_message=str(exc))
        session.commit()
        session.close()
        raise

    logger.info("Fetched %d raw readings for (%s, %s)", len(raw_readings), lat, lon)

    new_count = 0
    updated_count = 0
    error_count = 0

    for raw in raw_readings:
        try:
            # A SAVEPOINT scoped to just this reading: session.rollback() would
            # undo the *entire* transaction, including earlier readings in this
            # same batch that already succeeded. begin_nested() means a failure
            # here only undoes this one reading, leaving the rest of the batch intact.
            with session.begin_nested():
                reading = normalize_reading(raw)
                is_new = save_reading(session, reading)
        except Exception:
            error_count += 1
            logger.exception("Skipping malformed reading: %r", raw)
            continue

        if is_new:
            new_count += 1
        else:
            updated_count += 1

    # success=True here even if some individual readings errored out — that's
    # the per-record resilience working as designed, not a run failure. A
    # malformed record and a fully broken run are different signals; error_count
    # surfaces the former without conflating it with the latter.
    _record_run(
        session,
        started_at,
        success=True,
        fetched_count=len(raw_readings),
        new_count=new_count,
        updated_count=updated_count,
        error_count=error_count,
    )
    session.commit()
    session.close()

    logger.info(
        "Ingestion run complete: %d fetched, %d new, %d updated, %d errors",
        len(raw_readings), new_count, updated_count, error_count,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Quick manual test while building: pick a real lat/lon (e.g., Seattle)
    # and confirm you get real data back before wiring up anything else.
    test_lat, test_lon = 47.6062, -122.3321
    run_ingestion(test_lat, test_lon)
