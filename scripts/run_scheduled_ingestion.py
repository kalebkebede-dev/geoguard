"""
Entry point for the scheduled GitHub Actions ingestion job (see
.github/workflows/ingest.yml). Ingests a handful of real US cities each run
so the live deployed API has genuine, geographically diverse data rather
than a single location.

Each city is a separate run_ingestion() call, so each writes its own
ingestion_runs row — /health reports on whichever ran most recently.
"""

import logging

from app.ingestion.fetch_airnow import run_ingestion

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CITIES = [
    ("Seattle", 47.6062, -122.3321),
    ("Los Angeles", 34.0522, -118.2437),
    ("New York", 40.7128, -74.0060),
    ("Chicago", 41.8781, -87.6298),
    ("Denver", 39.7392, -104.9903),
]


def main():
    for name, lat, lon in CITIES:
        try:
            run_ingestion(lat, lon)
        except Exception as exc:
            logger.error("Ingestion failed for %s: %s", name, exc)


if __name__ == "__main__":
    main()
