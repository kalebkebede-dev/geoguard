"""
Week 2 goal: get the first two endpoints returning real data from your database.

Run locally with: uvicorn app.api.main:app --reload
Auto-generated docs will be at http://127.0.0.1:8000/docs — useful for testing
and a good thing to screenshot for your README later.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.aqi.lookup import indexed_nearby_stations, naive_nearby_stations, readings_for_stations
from app.api.auth_routes import router as auth_router
from app.api.locations_routes import router as locations_router
from app.db.models import IngestionRun
from app.db.session import get_db

app = FastAPI(
    title="Wildfire & Air Quality Risk API",
    description="Real-time air quality and wildfire risk data.",
    version="0.1.0",
)
app.include_router(auth_router)
app.include_router(locations_router)

# Mounted at /app (not /) so it doesn't collide with the JSON status route
# at "/" below. Served from this same FastAPI process, not a separate
# frontend host -- keeps it same-origin (no CORS) and one deployment target.
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

# Placeholder until the real GitHub Actions cron schedule is set (Week 3/4) —
# AirNow updates roughly hourly, so 2 hours gives a buffer before flagging
# unhealthy. Tune this once the actual scheduled interval is fixed.
HEALTHY_INTERVAL = timedelta(hours=2)


@app.get("/")
def root():
    return {"status": "ok", "service": "wildfire-risk-api"}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """
    Reports whether the last ingestion run succeeded and how long ago it
    was — see app.ingestion.fetch_airnow.run_ingestion, which writes one
    ingestion_runs row per run, success or failure.
    """
    last_run = db.query(IngestionRun).order_by(IngestionRun.completed_at.desc()).first()

    if last_run is None:
        return {"status": "unhealthy", "detail": "no ingestion runs recorded yet"}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    time_since_last_run = now - last_run.completed_at
    healthy = last_run.success and time_since_last_run <= HEALTHY_INTERVAL

    return {
        "status": "healthy" if healthy else "unhealthy",
        "minutes_since_last_run": round(time_since_last_run.total_seconds() / 60, 1),
        "last_run": {
            "completed_at": last_run.completed_at.isoformat(),
            "success": last_run.success,
            "fetched_count": last_run.fetched_count,
            "new_count": last_run.new_count,
            "updated_count": last_run.updated_count,
            "error_count": last_run.error_count,
            "error_message": last_run.error_message,
        },
    }


@app.get("/aqi/current")
def current_aqi(
    lat: float,
    lon: float,
    radius_miles: float = 25,
    method: str = "naive",
    db: Session = Depends(get_db),
):
    """
    method="naive" (default, unchanged from Week 3): Python-side bounding
    box filter. method="indexed": PostGIS ST_DWithin using the GiST index.
    Both exist side by side — not a replacement — so BENCHMARKS.md's
    before/after numbers come from real, directly comparable code paths.
    """
    if method == "indexed":
        nearby_stations = indexed_nearby_stations(db, lat, lon, radius_miles)
    else:
        nearby_stations = naive_nearby_stations(db, lat, lon, radius_miles)

    readings = readings_for_stations(db, nearby_stations)
    return {"count": len(readings), "readings": readings, "method": method}


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
