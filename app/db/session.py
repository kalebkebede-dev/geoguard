"""
Database engine and session setup. Shared by the ingestion job and, later,
the FastAPI layer — neither should open its own separate connection setup.

Loads DATABASE_URL from .env rather than hardcoding a connection string
in source, same reasoning as AIRNOW_API_KEY in fetch_airnow.py.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
