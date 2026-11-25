"""Offline shared-access safety checks; no gateway/model/network calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import sqlite3
import threading

import pytest

from apps.factory_lab.shared_access import (
    AccessConfig, AccessExpired, AccessStore, AuthenticationRequired,
    ConfigurationMismatch, QuotaExceeded, ReservationConflict,
)

PIN = "private-demo-7362"
BASE = datetime(2026, 11, 23, 14, 59, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = BASE

    def __call__(self):
        return self.now


@pytest.fixture
def access(tmp_path):
    clock = Clock()
    config = AccessConfig(deadline=BASE + timedelta(days=7))
    store = AccessStore(tmp_path / "access", config=config, pin=PIN, clock=clock)
    return store, clock, config


def reserve(store, token, key="request-1", **changes):
    args = dict(action="answer", workspace="workspace-1", request_key=key,
                revision="1", request_digest=hashlib.sha256(b"payload").hexdigest())
    args.update(changes)
    return store.reserve_paid_operation(token, **args)


def test_parallel_global_limit_and_restart(access):
    store, clock, config = access
    token = store.login(PIN)
    # Independent store/connection instances model multiple server workers.
    other = AccessStore(store.path.parent, config=config, pin=PIN, clock=clock)
    barrier = threading.Barrier(11)

    def attempt(index):
        barrier.wait(timeout=10)
        try:
            return reserve(store if index % 2 else other, token, str(index),
                           workspace=f"workspace-{index}")
        except QuotaExceeded:
            return None

    with ThreadPoolExecutor(max_workers=11) as pool:
        outcomes = list(pool.map(attempt, range(11)))
    assert sum(outcome is not None for outcome in outcomes) == 10
    assert sorted(outcome.count for outcome in outcomes if outcome) == list(range(1, 11))
    restarted = AccessStore(store.path.parent, config=config, pin=PIN, clock=clock)
    assert restarted.authenticate(token)
    assert restarted.quota_status().count == 10
    assert restarted.quota_status().remaining == 0
    with pytest.raises(QuotaExceeded):
        reserve(restarted, token, "next")


def test_replay_conflict_new_day_and_no_failure_refund(access):
    store, clock, _ = access
    token = store.login(PIN)
    first = reserve(store, token)
    # A caller's subsequent failed operation never invokes any refund API.
    assert store.quota_status().count == 1
    assert not first.replayed
    assert reserve(store, token).replayed
    with pytest.raises(ReservationConflict):
        reserve(store, token, request_digest=hashlib.sha256(b"changed").hexdigest())
    assert store.quota_status().count == 1
    clock.now += timedelta(minutes=2)  # Midnight in Asia/Seoul, not UTC.
    assert store.quota_status().day == "2026-11-24"
    assert store.quota_status().count == 0
    replay = reserve(store, token)
    assert replay.replayed and replay.day == "2026-11-23" and replay.count == 1
    assert store.quota_status().count == 0
    assert reserve(store, token, "new-day").count == 1
    # Each part of the composite key contributes to operation identity.
    assert not reserve(store, token, revision="2").replayed
    assert not reserve(store, token, action="semantic").replayed
    assert not reserve(store, token, workspace="other").replayed


def test_global_rolling_throttle_persists_and_logout(access):
    store, clock, config = access
    for _ in range(5):
        assert store.login("incorrect-pin") is None
    restarted = AccessStore(store.path.parent, config=config, pin=PIN, clock=clock)
    assert restarted.login(PIN) is None
    clock.now += timedelta(minutes=14, seconds=59)
    assert restarted.login(PIN) is None
    clock.now += timedelta(seconds=1)
    token = restarted.login(PIN)
    second_token = restarted.login(PIN)
    assert token != second_token
    assert restarted.authenticate(token)
    restarted.logout(token)
    assert not store.authenticate(token)
    assert store.authenticate(second_token)
    assert not store.authenticate("bad-token")
    with pytest.raises(AuthenticationRequired):
        reserve(store, token)


def test_session_eight_hours_and_absolute_deadline(access, tmp_path):
    store, clock, _ = access
    token = store.login(PIN)
    clock.now += timedelta(hours=8) - timedelta(microseconds=1)
    assert store.authenticate(token)
    clock.now += timedelta(microseconds=1)
    assert not store.authenticate(token)
    with pytest.raises(AuthenticationRequired):
        reserve(store, token)
    config = AccessConfig(deadline=clock.now + timedelta(minutes=1))
    short = AccessStore(tmp_path / "short", config=config, pin=PIN, clock=clock)
    token = short.login(PIN)
    clock.now += timedelta(minutes=1)
    for operation in (lambda: short.login(PIN), lambda: short.authenticate(token),
                      lambda: reserve(short, token)):
        with pytest.raises(AccessExpired):
            operation()


def test_configuration_and_credentials_are_bound_to_storage(access):
    store, clock, config = access
    with pytest.raises(ConfigurationMismatch):
        AccessStore(store.path.parent, config=config, pin="changed-private-pin", clock=clock)
    with pytest.raises(ConfigurationMismatch):
        AccessStore(store.path.parent,
                    config=AccessConfig(deadline=config.deadline + timedelta(days=1)),
                    pin=PIN, clock=clock)
    with pytest.raises(ConfigurationMismatch):
        AccessStore(store.path.parent,
                    config=AccessConfig(deadline=config.deadline, daily_limit=9),
                    pin=PIN, clock=clock)
    # Equivalent instants are an identical absolute deadline.
    same = AccessConfig(deadline=config.deadline.astimezone(timezone(timedelta(hours=9))))
    AccessStore(store.path.parent, config=same, pin=PIN, clock=clock)
    token = store.login(PIN)
    with sqlite3.connect(store.path) as db:
        salt, verifier = db.execute("SELECT salt,verifier FROM settings").fetchone()
        hashes = db.execute("SELECT token_hash FROM sessions").fetchall()
    assert len(salt) == 32 and len(verifier) == 32
    assert hashes == [(hashlib.sha256(token.encode()).hexdigest(),)]
    assert PIN.encode() not in store.path.read_bytes()
    assert token.encode() not in store.path.read_bytes()


def test_input_bounds_and_private_storage(access, tmp_path):
    store, _, _ = access
    token = store.login(PIN)
    for change in ({"action": "x" * 129}, {"request_key": "x" * 257},
                   {"workspace": "bad\nvalue"}, {"revision": ""},
                   {"request_digest": "a" * 63}):
        with pytest.raises(ValueError):
            reserve(store, token, **change)
    assert store.quota_status().count == 0
    with pytest.raises(ValueError):
        store.login("x" * 257)
    with pytest.raises(ValueError):
        AccessConfig(deadline=datetime(2026, 12, 1))
    with pytest.raises(ValueError):
        AccessConfig(deadline=BASE, daily_limit=11)
    with pytest.raises(ValueError):
        AccessStore("relative", config=store.config, pin=PIN)
    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    public.chmod(0o755)
    with pytest.raises(ValueError):
        AccessStore(public, config=store.config, pin=PIN)
    alias = tmp_path / "alias"
    alias.symlink_to(store.path.parent, target_is_directory=True)
    with pytest.raises(ValueError):
        AccessStore(alias, config=store.config, pin=PIN)


def test_operator_tests_preserve_reservations_without_consuming_human_quota(access):
    store, clock, config = access
    token = store.login(PIN)
    barrier = threading.Barrier(15)

    def attempt(index):
        barrier.wait(timeout=10)
        try:
            return reserve(store, token, str(index),
                           actor="operator_test" if index < 4 else "human")
        except QuotaExceeded:
            return None

    with ThreadPoolExecutor(max_workers=15) as pool:
        outcomes = list(pool.map(attempt, range(15)))
    assert all(outcomes[:4])
    assert sum(item is not None for item in outcomes[4:]) == 10
    assert store.quota_status().count == 10
    # Tests remain allowed at the human cap, with durable records for gateway costs.
    assert reserve(store, token, "after-cap", actor="operator_test").remaining == 0
    restarted = AccessStore(store.path.parent, config=config, pin=PIN, clock=clock)
    assert reserve(restarted, token, "0", actor="operator_test").replayed
    with pytest.raises(ReservationConflict):
        reserve(restarted, token, "0")
    with pytest.raises(QuotaExceeded):
        reserve(restarted, token, "new-human", workspace="different", action="semantic")
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT actor,COUNT(*) FROM reservations GROUP BY actor ORDER BY actor").fetchall() == [
            ("human", 10), ("operator_test", 5)]


def test_actor_replay_conflicts_authentication_and_deadline(access):
    store, clock, config = access
    token = store.login(PIN)
    reserve(store, token)
    with pytest.raises(ReservationConflict):
        reserve(store, token, actor="operator_test")
    with pytest.raises(AuthenticationRequired):
        reserve(store, "bad-token", "operator", actor="operator_test")
    with pytest.raises(ValueError):
        reserve(store, token, actor="agent")
    clock.now = config.deadline
    with pytest.raises(AccessExpired):
        reserve(store, token, "operator", actor="operator_test")


def test_legacy_migration_and_exact_audited_correction(access):
    store, clock, config = access
    token = store.login(PIN)
    reserve(store, token)
    with sqlite3.connect(store.path) as db:
        original = db.execute("SELECT action,workspace,request_key,revision,digest,day,created FROM reservations").fetchone()
        db.execute("ALTER TABLE reservations DROP COLUMN actor")
    restarted = AccessStore(store.path.parent, config=config, pin=PIN, clock=clock)
    assert restarted.quota_status().count == 1
    correction = dict(action=original[0], workspace=original[1], request_key=original[2],
                      revision=original[3], request_digest=original[4],
                      reason="Verified operator smoke operation; receipt example-001")
    for changed in ({"request_digest": "0" * 64}, {"revision": "wrong"}):
        with pytest.raises(ReservationConflict):
            restarted.reclassify_operator_test(**(correction | changed))
    assert restarted.quota_status().count == 1
    assert restarted.reclassify_operator_test(**correction)
    assert not restarted.reclassify_operator_test(**correction)
    with pytest.raises(ReservationConflict):
        restarted.reclassify_operator_test(**(correction | {"reason": "different reason"}))
    assert restarted.quota_status().count == 0
    assert reserve(restarted, token).replayed
    with pytest.raises(ReservationConflict):
        reserve(restarted, token, actor="operator_test")
    reserve(restarted, token, "actual-human")
    again = AccessStore(store.path.parent, config=config, pin=PIN, clock=clock)
    assert again.quota_status().count == 1
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT action,workspace,request_key,revision,digest,day,created FROM reservations WHERE request_key='request-1'").fetchone() == original
        assert db.execute("SELECT actor FROM reservations WHERE request_key='request-1'").fetchone() == ("human",)
        assert db.execute("SELECT digest,from_actor,to_actor,reason FROM reservation_actor_corrections").fetchall() == [
            (original[4], "human", "operator_test", correction["reason"])]


def test_original_and_correction_audit_rows_cannot_be_rewritten(access):
    store, clock, config = access
    token = store.login(PIN)
    reserve(store, token)
    with sqlite3.connect(store.path) as db:
        row = db.execute("SELECT action,workspace,request_key,revision,digest FROM reservations").fetchone()
    store.reclassify_operator_test(action=row[0], workspace=row[1], request_key=row[2],
        revision=row[3], request_digest=row[4], reason="Recorded operator verification")
    for sql in ("UPDATE reservations SET actor='operator_test'", "DELETE FROM reservations",
                "UPDATE reservation_actor_corrections SET reason='rewritten'",
                "DELETE FROM reservation_actor_corrections"):
        with sqlite3.connect(store.path) as db, pytest.raises(sqlite3.IntegrityError, match="immutable quota audit"):
            db.execute(sql)
    restarted = AccessStore(store.path.parent, config=config, pin=PIN, clock=clock)
    assert restarted.quota_status().count == 0
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT actor FROM reservations").fetchall() == [("human",)]
        assert db.execute("SELECT reason FROM reservation_actor_corrections").fetchall() == [("Recorded operator verification",)]
