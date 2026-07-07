"""
Week 1 goal: make this script call the real AirNow API and print live readings.
Don't touch the database from this file yet — prove the API call works first.

AirNow API docs: https://docs.airnowapi.org/
Look at the "Current Observations by Lat/Long" endpoint to start.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

AIRNOW_API_KEY = os.getenv("AIRNOW_API_KEY")
AIRNOW_BASE_URL = "https://www.airnowapi.org/aq/observation/latLong/current/"


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
    raise NotImplementedError("Implement the AirNow API call here")


def normalize_reading(raw_reading: dict) -> dict:
    """
    TODO: Take one raw reading from the AirNow response and reshape it into
    the schema you designed for your database (station id/name, lat, lon,
    pollutant type, AQI value, category, observed timestamp).

    This is also where you'd handle unit differences if you add a second
    data source (e.g., NASA FIRMS) later — normalize everything to one
    consistent shape before it reaches storage.
    """
    raise NotImplementedError("Implement normalization here")


if __name__ == "__main__":
    # Quick manual test while building: pick a real lat/lon (e.g., Seattle)
    # and confirm you get real data back before wiring up anything else.
    test_lat, test_lon = 47.6062, -122.3321
    readings = fetch_current_observations(test_lat, test_lon)
    for r in readings:
        print(normalize_reading(r))
