"""Repository-level tests for reset-request consumption.

``consume_reset_request`` must be safely serializable: two callers that race
for the same challenge produce exactly one success, never two password
rotations. The failed caller must not clear the guess budget either.
"""

from __future__ import annotations

import threading

from finance_core.db.account_security import consume_reset_request, create_reset_request
from finance_core.db.connection import connect, transaction
from finance_core.db.migrations import run_migrations
from finance_core.db.users import create_mobile_user, get_user_by_id

REQUEST_ID = "race-request"
CODE_HASH = "digest"
FUTURE = 10**12


def _prepare(tmp_path) -> tuple[str, int]:
    path = str(tmp_path / "consume.sqlite3")
    connection = connect(path)
    try:
        run_migrations(connection)
        user = create_mobile_user(
            connection, email="race@example.com", password_hash="old-hash"
        )
        create_reset_request(connection, user, REQUEST_ID, CODE_HASH, FUTURE)
        connection.commit()
        return path, user.id
    finally:
        connection.close()


def _consume_in_thread(path, code_hash, password_hash, barrier, results):
    connection = connect(path)
    try:
        barrier.wait(timeout=5)
        with transaction(connection):
            outcome = consume_reset_request(
                connection, REQUEST_ID, code_hash, password_hash, 0
            )
        results.append(outcome)
    except Exception as error:  # surfaced through the assertion below
        results.append(error)
    finally:
        connection.close()


def _run_pair(path, *, code_hash_a, password_hash_a, code_hash_b, password_hash_b):
    barrier = threading.Barrier(2)
    results: list[object] = []
    threads = [
        threading.Thread(
            target=_consume_in_thread,
            args=(path, code_hash_a, password_hash_a, barrier, results),
        ),
        threading.Thread(
            target=_consume_in_thread,
            args=(path, code_hash_b, password_hash_b, barrier, results),
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert not any(thread.is_alive() for thread in threads), "thread did not finish"
    return results


def test_concurrent_consume_allows_exactly_one_success(tmp_path):
    path, user_id = _prepare(tmp_path)

    results = _run_pair(
        path,
        code_hash_a=CODE_HASH,
        password_hash_a="new-hash-a",
        code_hash_b=CODE_HASH,
        password_hash_b="new-hash-b",
    )

    assert all(isinstance(result, bool) for result in results), results
    assert sorted(results) == [False, True]

    connection = connect(path)
    try:
        user = get_user_by_id(connection, user_id)
        # Exactly one password rotation: the loser never replaced the hash.
        assert user.password_hash in {"new-hash-a", "new-hash-b"}
        assert user.token_version == 1
        remaining = connection.execute(
            "SELECT COUNT(*) FROM password_reset_requests WHERE request_id = ?",
            (REQUEST_ID,),
        ).fetchone()[0]
    finally:
        connection.close()
    assert remaining == 0


def test_concurrent_wrong_guesses_persist_budget_without_rotation(tmp_path):
    path, user_id = _prepare(tmp_path)

    results = _run_pair(
        path,
        code_hash_a="wrong-a",
        password_hash_a="unused-a",
        code_hash_b="wrong-b",
        password_hash_b="unused-b",
    )

    assert results == [False, False], results

    connection = connect(path)
    try:
        user = get_user_by_id(connection, user_id)
        assert user.password_hash == "old-hash"
        assert user.token_version == 0
        row = connection.execute(
            "SELECT attempts FROM password_reset_requests WHERE request_id = ?",
            (REQUEST_ID,),
        ).fetchone()
    finally:
        connection.close()

    # Both failed guesses were committed; the budget was consumed, not reset.
    assert row is not None
    assert row[0] == 2
