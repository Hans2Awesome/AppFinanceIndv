"""Tests for recurring transaction API endpoints."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from finance_core.timezones import today_in


@pytest.fixture
def recurring_client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_recurring_api.sqlite3")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-1234567890123456789012")
    monkeypatch.setenv("RECURRING_SCHEDULER_ENABLED", "0")

    from backend.app.main import app
    from finance_core.db.connection import connect
    from finance_core.db.migrations import init_db

    conn = connect(db_file)
    init_db(conn)
    conn.close()

    with TestClient(app) as client:
        reg = client.post(
            "/api/auth/register",
            json={
                "email": "recurring_user@example.com",
                "password": "password123",
                "first_name": "Recurring",
            },
        )
        token = reg.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client


def test_create_weekly_schedule_starts_today_when_day_matches(recurring_client):
    today = today_in("Asia/Jakarta")

    res = recurring_client.post(
        "/api/recurring",
        json={
            "type": "expense",
            "category_name": "Transportasi",
            "amount": 25000,
            "note": "Parkir mingguan",
            "frequency": "weekly",
            "day_of_week": today.weekday(),
            "start_date": today.isoformat(),
        },
    )

    assert res.status_code == 201, res.text
    data = res.json()
    assert data["frequency"] == "weekly"
    assert data["day_of_week"] == today.weekday()
    assert data["day_of_month"] is None
    assert data["next_run_date"] == today.isoformat()
    assert data["is_active"] is True
    assert data["category_name"] == "Transportasi"


def test_create_monthly_schedule_computes_next_run(recurring_client):
    res = recurring_client.post(
        "/api/recurring",
        json={
            "type": "income",
            "category_name": "Gaji",
            "amount": 5000000,
            "frequency": "monthly",
            "day_of_month": 31,
            "start_date": "2030-01-31",
        },
    )

    assert res.status_code == 201, res.text
    data = res.json()
    assert data["day_of_week"] is None
    assert data["day_of_month"] == 31
    assert data["next_run_date"] == "2030-01-31"


def test_create_schedule_rejects_invalid_day(recurring_client):
    res = recurring_client.post(
        "/api/recurring",
        json={
            "type": "expense",
            "amount": 25000,
            "frequency": "weekly",
            "start_date": "2026-01-01",
        },
    )

    assert res.status_code == 422


def test_update_schedule_recomputes_and_deactivates(recurring_client):
    created = recurring_client.post(
        "/api/recurring",
        json={
            "type": "expense",
            "category_name": "Langganan",
            "amount": 50000,
            "frequency": "monthly",
            "day_of_month": 10,
            "start_date": "2030-01-01",
        },
    ).json()

    res = recurring_client.put(
        f"/api/recurring/{created['id']}",
        json={"amount": 75000, "day_of_month": 20, "is_active": False},
    )

    assert res.status_code == 200, res.text
    updated = res.json()
    assert updated["amount"] == 75000
    assert updated["day_of_month"] == 20
    assert updated["next_run_date"].endswith("-20")
    assert updated["is_active"] is False

    listed = recurring_client.get("/api/recurring", params={"active_only": True})
    assert listed.status_code == 200
    assert listed.json() == []


def test_update_switches_frequency_and_clears_unused_day(recurring_client):
    created = recurring_client.post(
        "/api/recurring",
        json={
            "type": "expense",
            "category_name": "Langganan",
            "amount": 50000,
            "frequency": "monthly",
            "day_of_month": 10,
            "start_date": "2030-01-01",
        },
    ).json()

    res = recurring_client.put(
        f"/api/recurring/{created['id']}",
        json={"frequency": "weekly", "day_of_week": 2},
    )

    assert res.status_code == 200, res.text
    updated = res.json()
    assert updated["frequency"] == "weekly"
    assert updated["day_of_week"] == 2
    assert updated["day_of_month"] is None
    assert date.fromisoformat(updated["next_run_date"]).weekday() == 2


def test_delete_schedule(recurring_client):
    created = recurring_client.post(
        "/api/recurring",
        json={
            "type": "expense",
            "amount": 10000,
            "frequency": "weekly",
            "day_of_week": 0,
            "start_date": "2030-01-01",
        },
    ).json()

    deleted = recurring_client.delete(f"/api/recurring/{created['id']}")
    assert deleted.status_code == 204

    missing = recurring_client.delete(f"/api/recurring/{created['id']}")
    assert missing.status_code == 404