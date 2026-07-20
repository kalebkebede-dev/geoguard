"""
SendGrid email sending via plain `requests` against their REST API --
consistent with how app/ingestion/fetch_airnow.py talks to AirNow, rather
than adding the full `sendgrid` SDK dependency for one API call.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ALERT_FROM_EMAIL = os.getenv("ALERT_FROM_EMAIL")
SENDGRID_SEND_URL = "https://api.sendgrid.com/v3/mail/send"


def send_alert_email(to_email: str, location_label: str, pollutant: str, aqi_value: int, category: str) -> None:
    """Raises on failure -- the caller decides what that means for the alert-state gate."""
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": ALERT_FROM_EMAIL},
        "subject": f"Air quality alert: {location_label} is {category}",
        "content": [{
            "type": "text/plain",
            "value": (
                f"Air quality near '{location_label}' has crossed into an unhealthy range.\n\n"
                f"Pollutant: {pollutant}\n"
                f"AQI: {aqi_value}\n"
                f"Category: {category}\n"
            ),
        }],
    }
    response = requests.post(
        SENDGRID_SEND_URL,
        json=payload,
        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}"},
        timeout=10,
    )
    response.raise_for_status()
