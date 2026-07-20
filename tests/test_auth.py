"""
Auth + saved-locations coverage. Runs against the real local Postgres
(same reasoning as test_api.py) since this exercises real password hashing,
JWT signing/verification, and per-user row scoping -- not something worth
mocking away.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.db.models import SavedLocation, User
from app.db.session import SessionLocal

TEST_EMAIL = "auth_test_user@example.com"
TEST_PASSWORD = "correct_horse_battery_staple"


@pytest.fixture
def client():
    session = SessionLocal()
    session.query(SavedLocation).filter(
        SavedLocation.user_id.in_(session.query(User.id).filter(User.email == TEST_EMAIL))
    ).delete(synchronize_session=False)
    session.query(User).filter_by(email=TEST_EMAIL).delete()
    session.commit()
    session.close()

    yield TestClient(app)

    session = SessionLocal()
    session.query(SavedLocation).filter(
        SavedLocation.user_id.in_(session.query(User.id).filter(User.email == TEST_EMAIL))
    ).delete(synchronize_session=False)
    session.query(User).filter_by(email=TEST_EMAIL).delete()
    session.commit()
    session.close()


def test_signup_login_and_duplicate_rejection(client):
    r = client.post("/auth/signup", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert r.status_code == 201
    assert "access_token" in r.json()

    r = client.post("/auth/signup", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert r.status_code == 409

    r = client.post("/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert r.status_code == 200

    r = client.post("/auth/login", json={"email": TEST_EMAIL, "password": "wrong_password"})
    assert r.status_code == 401


def test_locations_require_auth(client):
    assert client.get("/locations").status_code == 401
    assert client.post("/locations", json={"label": "x", "latitude": 0, "longitude": 0}).status_code == 401


def test_saved_locations_are_scoped_to_owner(client):
    signup = client.post("/auth/signup", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    add = client.post(
        "/locations", json={"label": "Home", "latitude": 47.6, "longitude": -122.3}, headers=headers
    )
    assert add.status_code == 201
    location_id = add.json()["id"]

    listed = client.get("/locations", headers=headers)
    assert listed.status_code == 200
    assert [loc["id"] for loc in listed.json()] == [location_id]

    deleted = client.delete(f"/locations/{location_id}", headers=headers)
    assert deleted.status_code == 204

    assert client.get("/locations", headers=headers).json() == []
    assert client.delete(f"/locations/{location_id}", headers=headers).status_code == 404
