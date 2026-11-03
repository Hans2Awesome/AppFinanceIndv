"""Test-suite guards shared by the bot/core and backend suites.

The repository `.env` may point ``DATABASE_URL`` at a real PostgreSQL or
Supabase database. ``finance_core.config`` calls ``dotenv.load_dotenv()``, which
only fills variables that are not already set. Defining ``DATABASE_URL`` as an
empty string here keeps every test on a temporary SQLite file, even on a
machine that is configured for production.

Tests that genuinely need PostgreSQL (``tests/test_postgres_portability.py``)
set ``DATABASE_URL`` themselves through ``monkeypatch``, and the variable is
read per call, so those still work.
"""

from __future__ import annotations

import os

# Must happen at import time, before the first ``get_common_settings()`` call.
# ``load_dotenv`` does not override an existing key, so "" wins over the .env
# value and the suite stays on SQLite.
os.environ["DATABASE_URL"] = ""
