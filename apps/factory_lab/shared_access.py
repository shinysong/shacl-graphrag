"""Bounded shared-user access and daily paid-operation reservations.

This is one trusted group's workspace, not multi-tenant isolation. Authentication
never supplies evaluation gold, expert approval, or permission to exceed the
separate gateway's total budget. Reservations precede work and are never refunded,
including failures. The operator must preserve this private directory across
restarts; removing it destroys sessions, throttling, and quota history.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo


class AccessError(Exception):
    """Base error with no credential or request payload in its message."""


class ConfigurationMismatch(AccessError):
    pass


class AccessExpired(AccessError):
    pass


class AuthenticationRequired(AccessError):
    pass


class QuotaExceeded(AccessError):
    pass


class ReservationConflict(AccessError):
    pass


@dataclass(frozen=True)
class AccessConfig:
    deadline: datetime
    daily_limit: int = 10

    def __post_init__(self) -> None:
        _aware(self.deadline)
        if type(self.daily_limit) is not int or not 1 <= self.daily_limit <= 10:
            raise ValueError("daily_limit must be an integer between 1 and 10")


@dataclass(frozen=True)
class QuotaStatus:
    day: str
    count: int
    remaining: int


@dataclass(frozen=True)
class Reservation(QuotaStatus):
    replayed: bool


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("an absolute timezone-aware datetime is required")
    return value.astimezone(timezone.utc)


def _field(value: str, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise ValueError(f"invalid {name}")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"invalid {name}")
    return value


def _derive(pin: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 310_000)


class AccessStore:
    """SQLite-backed global policy; a fresh connection/transaction per operation.

    Directory and database must be owned by this process's user, private, and not
    symlinks. Keep all ancestors operator-controlled. The PIN is constructor-only
    secret input; only its salted PBKDF2 verifier is written. Token hashes, rather
    than bearer tokens, are persisted. Do not log login bodies or cookie headers.
    """

    def __init__(self, directory: Path | str, *, config: AccessConfig, pin: str,
                 clock: Callable[[], datetime] | None = None) -> None:
        _field(pin, "PIN", 256)
        if len(pin) < 5:
            raise ValueError("PIN must contain at least five characters")
        self.config = config
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        directory = Path(directory)
        if not directory.is_absolute():
            raise ValueError("access directory must be absolute")
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._private(directory, is_directory=True)
        self.path = directory / "access.sqlite3"
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        self._private(self.path, is_directory=False)
        identity = json.dumps({"version": 1, "deadline": _aware(config.deadline).isoformat(),
                               "daily_limit": config.daily_limit, "timezone": "Asia/Seoul",
                               "session_seconds": 28800, "failures": 5,
                               "failure_window_seconds": 900, "pbkdf2_iterations": 310000},
                              sort_keys=True, separators=(",", ":"))
        with self._transaction() as db:
            for sql in (
                "CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL, salt BLOB NOT NULL, verifier BLOB NOT NULL)",
                "CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, expires REAL NOT NULL)",
                "CREATE TABLE IF NOT EXISTS failures (at REAL NOT NULL)",
                "CREATE TABLE IF NOT EXISTS reservations (action TEXT NOT NULL, workspace TEXT NOT NULL, request_key TEXT NOT NULL, revision TEXT NOT NULL, digest TEXT NOT NULL, day TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(action,workspace,request_key,revision))",
                "CREATE INDEX IF NOT EXISTS reservation_day ON reservations(day)",
                "CREATE TABLE IF NOT EXISTS reservation_actor_corrections (action TEXT NOT NULL, workspace TEXT NOT NULL, request_key TEXT NOT NULL, revision TEXT NOT NULL, digest TEXT NOT NULL, from_actor TEXT NOT NULL CHECK(from_actor='human'), to_actor TEXT NOT NULL CHECK(to_actor='operator_test'), reason TEXT NOT NULL, recorded REAL NOT NULL, PRIMARY KEY(action,workspace,request_key,revision))",
            ):
                db.execute(sql)
            # Preserve every legacy reservation, conservatively attributed to a human.
            if "actor" not in {column[1] for column in db.execute("PRAGMA table_info(reservations)")}:
                db.execute("ALTER TABLE reservations ADD COLUMN actor TEXT NOT NULL DEFAULT 'human' CHECK(actor IN ('human','operator_test'))")
            # Historical attribution changes use a separate correction record.
            # Neither the original reservation nor a correction may be rewritten.
            for table in ("reservations", "reservation_actor_corrections"):
                for action in ("UPDATE", "DELETE"):
                    db.execute(f"CREATE TRIGGER IF NOT EXISTS no_{action}_{table} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable quota audit'); END")
            row = db.execute("SELECT identity,salt,verifier FROM settings WHERE id=1").fetchone()
            if row is None:
                salt = secrets.token_bytes(32)
                verifier = _derive(pin, salt)
                db.execute("INSERT INTO settings VALUES(1,?,?,?)", (identity, salt, verifier))
            else:
                if row[0] != identity or not hmac.compare_digest(_derive(pin, row[1]), row[2]):
                    raise ConfigurationMismatch("persistent access configuration does not match")
                salt, verifier = row[1], row[2]
        self._salt, self._verifier = salt, verifier

    @staticmethod
    def _private(path: Path, *, is_directory: bool) -> None:
        info = path.lstat()
        expected = stat.S_ISDIR if is_directory else stat.S_ISREG
        if not expected(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError("access storage must be private and operator-owned")

    def _transaction(self):
        # Avoid sqlite Connection's context-manager leak: it commits but does not close.
        from contextlib import contextmanager

        @contextmanager
        def transaction():
            db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
            try:
                db.execute("BEGIN IMMEDIATE")
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()
        return transaction()

    def _now(self) -> datetime:
        return _aware(self._clock())

    def _active(self, now: datetime) -> None:
        if now >= _aware(self.config.deadline):
            raise AccessExpired("shared access deadline reached")

    @staticmethod
    def _token_hash(token: str) -> str | None:
        if not isinstance(token, str) or len(token) != 43 or any(
                char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
                for char in token):
            return None
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    def login(self, pin: str) -> str | None:
        _field(pin, "PIN", 256)
        with self._transaction() as db:
            now = self._now()
            self._active(now)
            db.execute("DELETE FROM failures WHERE at<=?", (now.timestamp() - 900,))
            if db.execute("SELECT COUNT(*) FROM failures").fetchone()[0] >= 5:
                return None
            if not hmac.compare_digest(_derive(pin, self._salt), self._verifier):
                db.execute("INSERT INTO failures VALUES(?)", (now.timestamp(),))
                return None
            token = secrets.token_urlsafe(32)
            expiry = min(now + timedelta(hours=8), _aware(self.config.deadline))
            db.execute("INSERT INTO sessions VALUES(?,?)", (self._token_hash(token), expiry.timestamp()))
            return token

    def authenticate(self, token: str) -> bool:
        with self._transaction() as db:
            now = self._now()
            self._active(now)
            return self._authenticated(db, token, now)

    def _authenticated(self, db: sqlite3.Connection, token: str, now: datetime) -> bool:
        hashed = self._token_hash(token)
        if hashed is None:
            return False
        row = db.execute("SELECT token_hash,expires FROM sessions WHERE token_hash=?", (hashed,)).fetchone()
        return bool(row and hmac.compare_digest(hashed, row[0]) and row[1] > now.timestamp())

    def logout(self, token: str) -> None:
        with self._transaction() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (self._token_hash(token),))

    def quota_status(self) -> QuotaStatus:
        with self._transaction() as db:
            now = self._now()
            day = now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
            count = self._human_count(db, day)
            return QuotaStatus(day, count, max(0, self.config.daily_limit - count))

    @staticmethod
    def _human_count(db: sqlite3.Connection, day: str) -> int:
        return db.execute(
            "SELECT COUNT(*) FROM reservations r WHERE r.day=? AND r.actor='human' "
            "AND NOT EXISTS (SELECT 1 FROM reservation_actor_corrections c "
            "WHERE c.action=r.action AND c.workspace=r.workspace AND c.request_key=r.request_key "
            "AND c.revision=r.revision AND c.digest=r.digest)", (day,)
        ).fetchone()[0]

    def reclassify_operator_test(self, *, action: str, workspace: str, request_key: str,
                                 revision: str, request_digest: str, reason: str) -> bool:
        """Operator-only audit correction for a precisely identified historical test.

        Never expose this method through an HTTP route or user-supplied switch.
        The original reservation and its replay binding remain immutable. Costs
        are unaffected. Returns False for an identical previously recorded correction.
        """
        key = (_field(action, "action", 128), _field(workspace, "workspace", 256),
               _field(request_key, "request_key", 256), _field(revision, "revision", 256))
        _field(reason, "reason", 2048)
        with self._transaction() as db:
            row = db.execute("SELECT digest,actor FROM reservations WHERE action=? AND workspace=? AND request_key=? AND revision=?", key).fetchone()
            if row is None or not isinstance(request_digest, str) or not hmac.compare_digest(row[0], request_digest) or row[1] != "human":
                raise ReservationConflict("correction requires an exact original human reservation")
            previous = db.execute("SELECT digest,reason FROM reservation_actor_corrections WHERE action=? AND workspace=? AND request_key=? AND revision=?", key).fetchone()
            if previous:
                if previous != (request_digest, reason):
                    raise ReservationConflict("a different correction is already recorded")
                return False
            db.execute("INSERT INTO reservation_actor_corrections VALUES(?,?,?,?,?,'human','operator_test',?,?)",
                       (*key, request_digest, reason, self._now().timestamp()))
            return True

    def reserve_paid_operation(self, token: str, *, action: str, workspace: str,
                               request_key: str, revision: str, request_digest: str,
                               actor: str = "human") -> Reservation:
        """Reserve once before work. A replay reports its original day's quota.

        Caller computes SHA-256 from a canonical complete request including every
        cost-relevant field. A changed payload under the same key is rejected.
        Authentication, deadline and the gateway's independent total cap still
        apply to replays; this method never invokes a model or executes work.
        Actor is selected by trusted server code, never from browser request data.
        Operator tests retain reservations and costs but consume no human quota.
        """
        if actor not in ("human", "operator_test"):
            raise ValueError("invalid reservation actor")
        key = (_field(action, "action", 128), _field(workspace, "workspace", 256),
               _field(request_key, "request_key", 256), _field(revision, "revision", 256))
        if (not isinstance(request_digest, str) or len(request_digest) != 64
                or any(char not in "0123456789abcdef" for char in request_digest)):
            raise ValueError("request_digest must be lowercase SHA-256 hex")
        with self._transaction() as db:
            now = self._now()
            self._active(now)
            if not self._authenticated(db, token, now):
                raise AuthenticationRequired("a current shared session is required")
            previous = db.execute("SELECT digest,day,actor FROM reservations WHERE action=? AND workspace=? AND request_key=? AND revision=?", key).fetchone()
            day = now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
            if previous:
                if not hmac.compare_digest(previous[0], request_digest) or previous[2] != actor:
                    raise ReservationConflict("reservation key already binds a different request")
                day = previous[1]
            count = self._human_count(db, day)
            if not previous:
                if actor == "human" and count >= self.config.daily_limit:
                    raise QuotaExceeded("shared daily paid-operation limit reached")
                db.execute("INSERT INTO reservations(action,workspace,request_key,revision,digest,day,created,actor) VALUES(?,?,?,?,?,?,?,?)", (*key, request_digest, day, now.timestamp(), actor))
                count += int(actor == "human")
            return Reservation(day, count, max(0, self.config.daily_limit - count), bool(previous))
