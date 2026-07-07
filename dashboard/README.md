# Dashboard

Week 4 goal: a static Leaflet.js page that calls your own `/aqi/current` and
`/aqi/history` endpoints and renders color-coded risk markers on a map.

Nothing to build here yet — don't start this until the API endpoints in
`app/api/main.py` actually return real data. Building the frontend against a
fake/incomplete API just means redoing it later.

Suggested approach when you get here: plain HTML + Leaflet.js loaded from a
CDN, no build step needed. Keep it simple — the API and pipeline are what
demonstrate engineering depth, the map just needs to make that data legible.
