"""Settings, read once at import.

This module is what makes a local `.env` work: `load_dotenv()` has to run
before any other module reads `os.environ`, so every module that needs a
setting imports it from here rather than calling `os.environ.get` itself.

On Railway there is no .env file -- the variables come from the service
config and `load_dotenv()` quietly does nothing.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# .strip() because these get pasted into Railway's variable boxes and into
# .env by hand, and "KEY= value" is an easy way to smuggle in a leading space
# that then never matches. The detector strips its copies for the same reason.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./vigiwatch.db").strip()
API_KEY = os.environ.get("API_KEY", "").strip()

DRIVER_USERNAME = os.environ.get("DRIVER_USERNAME", "driver").strip()
DRIVER_PASSWORD = os.environ.get("DRIVER_PASSWORD", "").strip()
DRIVER_NAME = os.environ.get("DRIVER_NAME", "Driver").strip()
