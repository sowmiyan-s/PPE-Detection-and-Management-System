"""
EdgeVision SQL Database Initialization and Seeding Script
Initializes SQLite database schema with default tables and seed records.
"""

import sys
import os
import logging

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core import sqlite_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_sql")

def seed():
    log.info("Initializing SQL database tables...")
    sqlite_db.init_sqlite_db()
    log.info("Successfully seeded SQL database tables at %s!", sqlite_db.SQLITE_DB_PATH)

if __name__ == "__main__":
    seed()
