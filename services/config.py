"""
=============================================================================
 Configuration — MLB Data Pipeline
 Centralised settings loaded from environment variables / .env file.
=============================================================================
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
#  PostgreSQL connection
# ──────────────────────────────────────────────────────────────────────────────
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mlb_sabermetrics")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)

# ──────────────────────────────────────────────────────────────────────────────
#  Pipeline defaults
# ──────────────────────────────────────────────────────────────────────────────
# Minimum plate appearances / innings pitched to include a player
MIN_PA = int(os.getenv("MIN_PA", "50"))
MIN_IP = float(os.getenv("MIN_IP", "20"))

# Default season to ingest (0 = current calendar year)
DEFAULT_SEASON = int(os.getenv("DEFAULT_SEASON", "0"))

# Chunk size for bulk inserts (rows per batch)
BULK_INSERT_CHUNK = int(os.getenv("BULK_INSERT_CHUNK", "500"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
