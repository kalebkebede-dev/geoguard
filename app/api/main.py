"""
Week 2 goal: get the first two endpoints returning real data from your database.

Run locally with: uvicorn app.api.main:app --reload
Auto-generated docs will be at http://127.0.0.1:8000/docs — useful for testing
and a good thing to screenshot for your README later.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Wildfire & Air Quality Risk API",
    description="Real-time air quality and wildfire risk data.",
    version="0.1.0",
)


@app.get("/")
def root():
    return {"status": "ok", "service": "wildfire-risk-api"}


@app.get("/health")
def health():
    """
    Week 3 goal: this is your pipeline-observability signal, and almost no
    student project has one — it's a cheap, high-value addition.

    TODO: Query the database for the most recent ingestion run (you'll need
    to record run metadata somewhere — e.g., a simple `ingestion_runs` table
    with a timestamp and row count written at the end of every run). Return
    whether the last run succeeded and how long ago it was. If it's been
    longer than your scheduled interval plus some buffer, this should report
    unhealthy, not just "ok" by default.
    """
    raise NotImplementedError("Report last successful ingestion run status")


@app.get("/aqi/current")
def current_aqi(lat: float, lon: float):
    """
    TODO: Query your database for the most recent reading(s) near this
    lat/lon (this is where PostGIS earns its place — a radius query).
    Return AQI value, category (Good/Moderate/Unhealthy/etc.), and the
    station it came from.
    """
    raise NotImplementedError("Query the database and return current AQI")


@app.get("/aqi/history")
def aqi_history(lat: float, lon: float, days: int = 7):
    """
    TODO: Return a time series of readings for this location over the
    requested window. This is what your dashboard's trend chart will call.
    """
    raise NotImplementedError("Query historical readings")


@app.get("/alerts")
def alerts():
    """
    TODO (Week 5 stretch): Return locations currently above an unhealthy
    AQI threshold. Only build this after /aqi/current and /aqi/history
    are solid — don't start the stretch goal early and leave the core
    incomplete.
    """
    raise NotImplementedError("Implement threshold-based alerting")
