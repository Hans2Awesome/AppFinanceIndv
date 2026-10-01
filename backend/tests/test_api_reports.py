"""Tests for report API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def populated_client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_report_api.sqlite3")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123456789")

    from backend.app.main import app
    from backend.app.database.connection import connect
    from backend.app.database.schema import init_db

    conn = connect(db_file)
    init_db(conn)
    conn.close()

    with TestClient(app) as client:
        # Register user
        reg = client.post(
            "/api/auth/register",
            json={"email": "report_user@example.com", "password": "password123", "first_name": "ReportUser"},
        )
        token = reg.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})

        # Insert some transactions for 2026-05-30
        client.post(
            "/api/transactions",
            json={"type": "income", "category_name": "Gaji", "amount": 5000000, "transaction_date": "2026-05-30"},
        )
        client.post(
            "/api/transactions",
            json={"type": "expense", "category_name": "Makan & Minum", "amount": 100000, "transaction_date": "2026-05-30"},
        )
        client.post(
            "/api/transactions",
            json={"type": "investment", "category_name": "Crypto", "asset_name": "BTC", "amount": 500000, "transaction_date": "2026-05-30"},
        )

        yield client


def test_daily_report(populated_client):
    res = populated_client.get("/api/reports/daily?target_date=2026-05-30")
    assert res.status_code == 200
    data = res.json()
    assert data["total_income"] == 5000000
    assert data["total_expense"] == 100000
    assert data["total_investment"] == 500000
    assert data["net"] == 4400000
    assert len(data["top_expense_categories"]) >= 1


def test_monthly_report(populated_client):
    res = populated_client.get("/api/reports/monthly?year=2026&month=5")
    assert res.status_code == 200
    data = res.json()
    assert data["total_income"] == 5000000
    assert data["net"] == 4400000


def test_category_breakdown(populated_client):
    res = populated_client.get(
        "/api/reports/category-breakdown?type=expense&start_date=2026-05-01&end_date=2026-05-31"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_amount"] == 100000
    assert data["categories"][0]["name"] == "Makan & Minum"


def test_investment_report(populated_client):
    res = populated_client.get(
        "/api/reports/investment?start_date=2026-05-01&end_date=2026-05-31"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_investment"] == 500000
    assert data["investment_percentage"] == 10.0
