"""
Standalone script to initialize the database tables.
Can be run via: python scripts/init_db.py
"""

import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db.init_db import init_db
from app.core.config import settings

if __name__ == "__main__":
    print(f"Connecting to database: {settings.DATABASE_URL}")
    init_db()
    print("Database initialization completed successfully.")
