"""Test-suite guards shared by the bot/core and backend suites.

The repository `.env` may point ``DATABASE_URL`` at a real PostgreSQL or
Supabase database. ``finance_core.config`` calls ``dotenv.load_dotenv()``, which
only fills variables that are not already set. Defining ``DATABASE_URL`` as an
empty string here keeps every test on a temporary SQLite file, even on a
machine that is configured for production.

That alone is one import away from being bypassed (a future
``load_dotenv(override=True)``, or a module imported before this file runs), so
the guard has three layers:

1. ``DATABASE_URL`` is blanked here, before the first ``get_common_settings()``.
2. ``dotenv.load_dotenv`` is wrapped so the variable cannot be filled back in
   from ``.env``, whatever override flag the caller passes.
3. ``finance_core.db.connection.connect_url`` refuses a hosted production
   database while ``pytest`` is loaded.

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

# A deployment ``.env`` with ``ENVIRONMENT=production`` must not turn a local
# test run into a failed production-configuration check. Tests that need
# production behaviour set the variable themselves.
os.environ["ENVIRONMENT"] = "development"

import dotenv

_real_load_dotenv = dotenv.load_dotenv


def _load_dotenv_without_database_url(*args, **kwargs):
    """Load the .env file, then clear ``DATABASE_URL`` again.

    A ``DATABASE_URL`` that was already set by a test (``monkeypatch.setenv``)
    is kept: only a value that came from the file is discarded.
    """

    before = os.environ.get("DATABASE_URL", "")
    loaded = _real_load_dotenv(*args, **kwargs)
    if not before:
        os.environ["DATABASE_URL"] = ""
    return loaded


# ``finance_core.config`` binds ``load_dotenv`` with ``from dotenv import ...``
# at import time, so both names are replaced before anything imports it.
dotenv.load_dotenv = _load_dotenv_without_database_url

import finance_core.config as _finance_config  # noqa: E402

_finance_config.load_dotenv = _load_dotenv_without_database_url
