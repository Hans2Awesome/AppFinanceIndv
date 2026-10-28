"""In-memory pending confirmation store for quick input previews."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from finance_core.services.quick_input_parser import QuickInputResult


@dataclass(frozen=True)
class _PendingEntry:
    preview: QuickInputResult
    created_at: datetime


class PendingConfirmationStore:
    """Store parsed previews temporarily per Telegram user."""

    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(minutes=10),
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._ttl = ttl
        self._now_provider = now_provider or _utc_now
        self._entries: dict[int, _PendingEntry] = {}

    def set(self, *, telegram_user_id: int, preview: QuickInputResult) -> None:
        """Set or replace a pending preview for one Telegram user."""

        self._entries[telegram_user_id] = _PendingEntry(
            preview=preview,
            created_at=self._now(),
        )

    def get(self, *, telegram_user_id: int) -> QuickInputResult | None:
        """Return a pending preview if it exists and has not expired."""

        entry = self._entries.get(telegram_user_id)
        if entry is None:
            return None
        if self._is_expired(entry):
            self.clear(telegram_user_id=telegram_user_id)
            return None
        return entry.preview

    def clear(self, *, telegram_user_id: int) -> None:
        """Clear a pending preview for one Telegram user."""

        self._entries.pop(telegram_user_id, None)

    def _is_expired(self, entry: _PendingEntry) -> bool:
        return self._now() - entry.created_at > self._ttl

    def _now(self) -> datetime:
        return self._now_provider()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
