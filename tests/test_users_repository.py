"""Tests for Bot04 user repository."""

from __future__ import annotations

import sqlite3

import pytest

from finance_core.db.connection import connect
from finance_core.db.migrations import init_db
from finance_core.db.users import (
    consume_telegram_link_code,
    create_mobile_user,
    create_telegram_link_code,
    get_or_create_user,
    link_telegram_account,
    peek_telegram_link_code,
    unlink_telegram_account,
)


def setup_connection() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    return connection


def test_get_or_create_user_inserts_new_user() -> None:
    connection = setup_connection()

    user = get_or_create_user(
        connection,
        telegram_user_id=796529359,
        first_name="Hans",
        username="hans2awesome",
        timezone="Asia/Jakarta",
        currency="IDR",
    )

    assert user.id == 1
    assert user.telegram_user_id == 796529359
    assert user.first_name == "Hans"
    assert user.username == "hans2awesome"
    assert user.timezone == "Asia/Jakarta"
    assert user.currency == "IDR"
    assert user.email is None

    row_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert row_count == 1


def test_get_or_create_user_returns_existing_user_without_duplicate_insert() -> None:
    connection = setup_connection()

    first_user = get_or_create_user(
        connection,
        telegram_user_id=796529359,
        first_name="Hans",
        username="hans2awesome",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    second_user = get_or_create_user(
        connection,
        telegram_user_id=796529359,
        first_name="Changed Name",
        username="changed_username",
        timezone="UTC",
        currency="USD",
    )

    assert second_user == first_user
    row_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert row_count == 1


def test_telegram_link_code_create_consume_and_expire() -> None:
    connection = setup_connection()
    user = get_or_create_user(
        connection,
        telegram_user_id=796529359,
        first_name="Hans",
        timezone="Asia/Jakarta",
        currency="IDR",
    )

    code = create_telegram_link_code(connection, user_id=user.id, code="ABCDEF")
    assert code == "ABCDEF"

    owner_id = consume_telegram_link_code(connection, code="ABCDEF")
    assert owner_id == user.id

    # Kode sudah dikonsumsi (used = 1), tidak bisa digunakan lagi.
    assert consume_telegram_link_code(connection, code="ABCDEF") is None


def test_telegram_link_account_transfers_bot_data_to_mobile_owner() -> None:
    connection = setup_connection()

    # Akun Mobile (email) adalah pemilik utama.
    mobile = create_mobile_user(
        connection,
        email="budi@example.com",
        password_hash="dummy",
        first_name="Budi",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    mobile_category = connection.execute(
        "INSERT INTO categories (user_id, type, name, aliases, is_default) VALUES (?, 'expense', 'Makan', '', 0)",
        (mobile.id,),
    ).lastrowid

    # Baris bot dibuat lewat /start dengan telegram_user_id yang sama.
    bot_user = get_or_create_user(
        connection,
        telegram_user_id=555123,
        first_name="Bot Budi",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    # Bot punya kategori dengan nama yang sama; ini harus dipetakan, bukan bentrok.
    bot_category = connection.execute(
        "INSERT INTO categories (user_id, type, name, aliases, is_default) VALUES (?, 'expense', 'Makan', '', 0)",
        (bot_user.id,),
    ).lastrowid
    connection.execute(
        "INSERT INTO transactions (user_id, type, category_id, amount, transaction_date) "
        "VALUES (?, 'expense', ?, 10000, '2026-01-01')",
        (bot_user.id, bot_category),
    )

    linked = link_telegram_account(
        connection, user_id=mobile.id, telegram_user_id=555123
    )
    assert linked.id == mobile.id
    assert linked.telegram_user_id == 555123

    # Baris bot dihapus.
    assert connection.execute("SELECT COUNT(*) FROM users WHERE id = ?", (bot_user.id,)).fetchone()[0] == 0

    # Transaksi bot dipindahkan ke pemilik mobile dan kategori dipetakan ke kategori owner.
    moved = connection.execute(
        "SELECT user_id, category_id FROM transactions WHERE user_id = ?", (mobile.id,)
    ).fetchone()
    assert moved["user_id"] == mobile.id
    assert moved["category_id"] == mobile_category

    # Tidak ada kategori duplikat untuk owner.
    duplicate_count = connection.execute(
        "SELECT COUNT(*) FROM categories WHERE user_id = ? AND type = 'expense' AND name = 'Makan'",
        (mobile.id,),
    ).fetchone()[0]
    assert duplicate_count == 1


def test_link_telegram_cannot_hijack_mobile_account_with_credentials() -> None:
    connection = setup_connection()

    victim = create_mobile_user(
        connection,
        email="victim@example.com",
        password_hash="hash",
        first_name="Victim",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    link_telegram_account(connection, user_id=victim.id, telegram_user_id=777)

    attacker = create_mobile_user(
        connection,
        email="attacker@example.com",
        password_hash="hash",
        first_name="Attacker",
        timezone="Asia/Jakarta",
        currency="IDR",
    )

    with pytest.raises(ValueError):
        link_telegram_account(
            connection, user_id=attacker.id, telegram_user_id=777
        )

    # Akun korban tidak berubah.
    victim_row = connection.execute(
        "SELECT id, email, telegram_user_id FROM users WHERE id = ?", (victim.id,)
    ).fetchone()
    assert victim_row["email"] == "victim@example.com"
    assert victim_row["telegram_user_id"] == 777


def test_link_telegram_rebases_transaction_source_keys_to_new_owner() -> None:
    connection = setup_connection()

    mobile = create_mobile_user(
        connection,
        email="owner@example.com",
        password_hash="hash",
        first_name="Owner",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    bot_user = get_or_create_user(
        connection,
        telegram_user_id=555999,
        first_name="Bot",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    connection.execute(
        "INSERT INTO transactions (user_id, type, amount, transaction_date, source_key) "
        "VALUES (?, 'income', 10000, '2026-01-01', ?)",
        (bot_user.id, f"debt:{bot_user.id}:42"),
    )

    link_telegram_account(connection, user_id=mobile.id, telegram_user_id=555999)

    source_keys = [
        row[0]
        for row in connection.execute(
            "SELECT source_key FROM transactions WHERE user_id = ?", (mobile.id,)
        ).fetchall()
    ]
    assert source_keys == [f"debt:{mobile.id}:42"]


def test_new_link_code_invalidates_previous_code() -> None:
    connection = setup_connection()
    user = create_mobile_user(
        connection,
        email="codes@example.com",
        password_hash="hash",
        first_name="Codes",
        timezone="Asia/Jakarta",
        currency="IDR",
    )

    create_telegram_link_code(connection, user_id=user.id, code="111111")
    create_telegram_link_code(connection, user_id=user.id, code="222222")

    assert consume_telegram_link_code(connection, code="111111") is None
    assert consume_telegram_link_code(connection, code="222222") == user.id


def test_peek_telegram_link_code_does_not_burn_code() -> None:
    connection = setup_connection()
    user = create_mobile_user(
        connection,
        email="peek@example.com",
        password_hash="hash",
        first_name="Peek",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    create_telegram_link_code(connection, user_id=user.id, code="654321")

    # Percobaan tautan yang ditolak tidak boleh menghanguskan kode.
    assert peek_telegram_link_code(connection, code="654321") == user.id
    assert peek_telegram_link_code(connection, code="654321") == user.id
    assert consume_telegram_link_code(connection, code="654321") == user.id
    assert peek_telegram_link_code(connection, code="654321") is None


def test_link_rebases_each_prefix_without_touching_schedule_ids() -> None:
    connection = setup_connection()
    mobile = create_mobile_user(
        connection,
        email="prefix@example.com",
        password_hash="hash",
        first_name="Prefix",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    bot_user = get_or_create_user(
        connection,
        telegram_user_id=555777,
        first_name="Bot",
        timezone="Asia/Jakarta",
        currency="IDR",
    )

    # schedule_id sama dengan bot id: pola lama ":<bot>:" akan merusak id ini.
    bot_id = bot_user.id
    keys = [
        f"recurring:{bot_id}:{bot_id}:2026-11-02",
        f"recurring:{bot_id}:22:2026-11-02",
        f"debt:{bot_id}:{bot_id}",
        f"debt_payment:{bot_id}:{bot_id}",
    ]
    for key in keys:
        connection.execute(
            "INSERT INTO transactions (user_id, type, amount, transaction_date, source_key) "
            "VALUES (?, 'income', 1000, '2026-11-02', ?)",
            (bot_id, key),
        )

    link_telegram_account(connection, user_id=mobile.id, telegram_user_id=555777)

    rebased = [
        row[0]
        for row in connection.execute(
            "SELECT source_key FROM transactions WHERE user_id = ? ORDER BY id",
            (mobile.id,),
        ).fetchall()
    ]
    assert rebased == [
        f"recurring:{mobile.id}:{bot_id}:2026-11-02",
        f"recurring:{mobile.id}:22:2026-11-02",
        f"debt:{mobile.id}:{bot_id}",
        f"debt_payment:{mobile.id}:{bot_id}",
    ]


def test_link_drops_bot_cash_row_that_collides_with_owner_key() -> None:
    connection = setup_connection()
    mobile = create_mobile_user(
        connection,
        email="dupe@example.com",
        password_hash="hash",
        first_name="Dupe",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    bot_user = get_or_create_user(
        connection,
        telegram_user_id=555888,
        first_name="Bot",
        timezone="Asia/Jakarta",
        currency="IDR",
    )

    # Pemilik sudah punya baris kas untuk utang yang sama; baris bot duplikat.
    for user_id in (mobile.id, bot_user.id):
        connection.execute(
            "INSERT INTO transactions (user_id, type, amount, transaction_date, source_key) "
            "VALUES (?, 'income', 1000, '2026-11-02', ?)",
            (user_id, f"debt:{user_id}:5"),
        )

    # Tidak boleh gagal karena indeks unik source_key.
    link_telegram_account(connection, user_id=mobile.id, telegram_user_id=555888)

    source_keys = [
        row[0]
        for row in connection.execute(
            "SELECT source_key FROM transactions WHERE user_id = ?", (mobile.id,)
        ).fetchall()
    ]
    assert source_keys == [f"debt:{mobile.id}:5"]


def test_expired_link_codes_are_pruned_when_a_new_code_is_requested() -> None:
    connection = setup_connection()
    user = create_mobile_user(
        connection,
        email="prune@example.com",
        password_hash="hash",
        first_name="Prune",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    other = create_mobile_user(
        connection,
        email="other@example.com",
        password_hash="hash",
        first_name="Other",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    # Kode kedaluwarsa milik pengguna lain.
    connection.execute(
        "INSERT INTO telegram_link_codes (user_id, code, expires_at, used) "
        "VALUES (?, '000001', '2000-01-01 00:00:00', 0)",
        (other.id,),
    )

    create_telegram_link_code(connection, user_id=user.id, code="123456")

    remaining = connection.execute(
        "SELECT code FROM telegram_link_codes"
    ).fetchall()
    assert [row[0] for row in remaining] == ["123456"]


def test_unlink_telegram_keeps_data_and_clears_telegram_id() -> None:
    connection = setup_connection()
    mobile = create_mobile_user(
        connection,
        email="unlink@example.com",
        password_hash="hash",
        first_name="Unlink",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    link_telegram_account(connection, user_id=mobile.id, telegram_user_id=424242)
    connection.execute(
        "INSERT INTO transactions (user_id, type, amount, transaction_date) "
        "VALUES (?, 'expense', 5000, '2026-11-02')",
        (mobile.id,),
    )

    unlinked = unlink_telegram_account(connection, user_id=mobile.id)

    assert unlinked is not None
    assert unlinked.telegram_user_id is None
    assert unlinked.telegram_linked is False
    assert (
        connection.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = ?", (mobile.id,)
        ).fetchone()[0]
        == 1
    )

    # Akun Telegram baru bisa ditautkan setelah dilepas.
    relinked = link_telegram_account(
        connection, user_id=mobile.id, telegram_user_id=999999
    )
    assert relinked.telegram_user_id == 999999
