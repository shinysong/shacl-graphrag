"""Offline-reviewable Auto-Ontology spending boundary; no credentials or pricing discovery.

Operator must verify provider rates AND full-context/output ceilings before config. Amounts
are integer nanodollars. Fixed mode never refunds; explicitly selected settled mode
releases unused holds only after successful cost-known responses. Unknown/failed costs
retain the full hold, including crashes. SQLite is append-only at application level, not tamper-proof against its owner.
Transport is injected and must make exactly one request, with no redirects or retries,
respect its timeout and cap response bytes. No real transport is supplied here.

Embedding adaptation removes NVIDIA input_type/truncate/modality only after checking
expected values; requests genuine dimensions=2048 and rejects mismatched vectors. It
never pads/truncates vectors. Child receives fakekey and a loopback HTTP endpoint only;
this adapter does not provide child network isolation.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import fcntl
import json
import math
import sqlite3
import time
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Callable


class Denied(ValueError):
    """Terminal local refusal; caller should stop its run, not retry."""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _positive(value):
    return type(value) is int and value > 0


def ledger_totals(db, mode='fixed'):
    """Never rewrite reservations; settle only successful, cost-known responses."""
    rows = db.execute('SELECT a.reserved,c.status,c.usage,c.error FROM attempts a LEFT JOIN completions c ON c.attempt=a.id').fetchall()
    raw = used = reported = held = 0
    for reservation, status, usage, error in rows:
        raw += reservation
        charge = None
        if status is not None and 200 <= status < 300 and not error:
            try:
                value = json.loads(usage) if usage else None
                cost = value.get('cost') if isinstance(value, dict) else None
                if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                    amount = Decimal(str(cost))
                    if amount.is_finite() and amount >= 0:
                        charge = int((amount * 1_000_000_000).to_integral_value(rounding=ROUND_CEILING))
            except (ValueError, TypeError, InvalidOperation):
                pass
        if charge is not None:
            reported += charge
        if mode == 'settled' and charge is not None:
            used += charge
        else:
            used += reservation
            held += reservation
    return {'attempts': len(rows), 'raw_reserved': raw, 'used': used,
            'reported': reported, 'held': held}


@dataclass(frozen=True)
class Model:
    alias: str
    actual_id: str
    kind: str  # chat or embedding
    provider: str
    input_nanodollars_per_token: int
    output_nanodollars_per_token: int
    max_input_tokens: int
    max_output_tokens: int  # includes reasoning tokens; embeddings require zero
    verification: str  # evidence for full provider context/output ceilings, not byte estimates
    reservation_nanodollars: int = 0  # zero uses the configured per-call ceiling
    billing_output_tokens: int = 0  # zero uses max_output_tokens; otherwise full provider ceiling


@dataclass(frozen=True)
class Config:
    models: tuple[Model, ...]
    call_cap: int
    per_call_nanodollars: int
    total_nanodollars: int
    deadline_epoch: float
    timeout_seconds: int
    max_request_bytes: int
    max_response_bytes: int
    inherited_attempts: int = 0
    inherited_reserved_nanodollars: int = 0
    prior_ledger_path: str = ""
    prior_ledger_sha256: str = ""
    campaign_lock_path: str = ""
    chat_attempt_cap: int = 0
    embedding_attempt_cap: int = 0
    reservation_accounting: str = 'fixed'

    def validate(self):
        if self.reservation_accounting not in ('fixed', 'settled'):
            raise Denied('unsupported reservation accounting')
        if not self.models or len({m.alias for m in self.models}) != len(self.models):
            raise Denied("missing or duplicate models")
        for n in (self.call_cap, self.per_call_nanodollars, self.total_nanodollars,
                  self.timeout_seconds, self.max_request_bytes, self.max_response_bytes):
            if not _positive(n):
                raise Denied("positive integer limits required")
        if self.total_nanodollars > 10_000_000_000 or self.per_call_nanodollars > self.total_nanodollars:
            raise Denied("budget exceeds $10 or per-call reservation exceeds budget")
        for number in (self.inherited_attempts, self.inherited_reserved_nanodollars,
                       self.chat_attempt_cap, self.embedding_attempt_cap):
            if type(number) is not int or number < 0:
                raise Denied("nonnegative inherited counters and role caps required")
        inherited = bool(self.inherited_attempts or self.inherited_reserved_nanodollars)
        if inherited != bool(self.prior_ledger_path and self.prior_ledger_sha256 and self.campaign_lock_path):
            raise Denied("carryforward requires bound predecessor and common campaign lock")
        if not inherited and any((self.prior_ledger_path,self.prior_ledger_sha256,self.campaign_lock_path)):
            raise Denied("incomplete carryforward configuration")
        if self.inherited_attempts > self.call_cap or self.inherited_reserved_nanodollars > self.total_nanodollars:
            raise Denied("inherited campaign already exceeds ceiling")
        if not math.isfinite(self.deadline_epoch):
            raise Denied("finite deadline required")
        for m in self.models:
            if (not m.alias.startswith("openai/auto-ontology-") or not m.actual_id
                    or "/" not in m.actual_id or not m.provider or not m.verification.strip()
                    or m.kind not in {"chat", "embedding"}):
                raise Denied("explicit alias, actual model, provider and verification required")
            if not all(_positive(n) for n in (m.input_nanodollars_per_token,
                    m.max_input_tokens)):
                raise Denied("verified nonzero input prices and token upper bounds required")
            if m.kind == "chat" and not all(_positive(n) for n in (
                    m.output_nanodollars_per_token, m.max_output_tokens)):
                raise Denied("verified output price and limit required")
            if m.kind == "embedding" and (m.max_output_tokens != 0 or m.output_nanodollars_per_token != 0):
                raise Denied("embeddings have no output-token allowance")
            if (type(m.reservation_nanodollars) is not int or m.reservation_nanodollars < 0
                    or type(m.billing_output_tokens) is not int or m.billing_output_tokens < 0
                    or (m.billing_output_tokens and m.billing_output_tokens < m.max_output_tokens)
                    or (m.kind == "embedding" and m.billing_output_tokens)):
                raise Denied("invalid full-output ceiling or reservation")
            reservation = m.reservation_nanodollars or self.per_call_nanodollars
            cost = (m.max_input_tokens * m.input_nanodollars_per_token
                    + (m.billing_output_tokens or m.max_output_tokens) * m.output_nanodollars_per_token)
            if reservation > self.per_call_nanodollars or cost > reservation:
                raise Denied("full provider context/output charge exceeds reservation")


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes


# route, request bytes, bearer secret, timeout seconds, max response bytes -> Response
Transport = Callable[[str, bytes, str, float, int], Response]


class Gateway:
    def __init__(self, ledger: Path, config: Config, secret: str, transport: Transport,
                 clock: Callable[[], float] = time.time):
        config.validate()
        if not secret or secret == "fakekey":
            raise Denied("operator credential required")
        self.ledger, self.config, self._secret = Path(ledger), config, secret
        self.transport, self.clock = transport, clock
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self._campaign_lock = None
        if config.prior_ledger_path:
            if self.ledger.resolve() == Path(config.prior_ledger_path).resolve():
                raise Denied("continuation must not overwrite predecessor ledger")
            self._campaign_lock = open(config.campaign_lock_path, "a")
            try:
                fcntl.flock(self._campaign_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._verify_prior()
            except BaseException:
                self.close()
                raise
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS configuration (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (
                  id INTEGER PRIMARY KEY, started REAL NOT NULL, route TEXT NOT NULL,
                  alias TEXT NOT NULL, model TEXT NOT NULL, original TEXT NOT NULL,
                  request TEXT NOT NULL, sha256 TEXT NOT NULL, reserved INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS completions (
                  attempt INTEGER PRIMARY KEY REFERENCES attempts(id), finished REAL NOT NULL,
                  status INTEGER, response BLOB, usage TEXT, error TEXT);
            ''')
            for table in ("configuration", "attempts", "completions"):
                for action in ("UPDATE", "DELETE"):
                    db.execute(f"CREATE TRIGGER IF NOT EXISTS no_{action}_{table} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable ledger'); END")
            db.execute("BEGIN IMMEDIATE")
            frozen = _json(asdict(config))
            existing = db.execute("SELECT value FROM configuration WHERE id=1").fetchone()
            previous = json.loads(existing[0]) if existing else None
            if previous is not None:
                previous.setdefault('reservation_accounting', 'fixed')
            if existing and _json(previous) != frozen:
                raise Denied("ledger configuration is frozen")
            db.execute("INSERT OR IGNORE INTO configuration VALUES (1, ?)", (frozen,))
        self.ledger.chmod(0o600)

    def close(self):
        """Release lifetime campaign lock after the server/forwarding work has stopped."""
        if self._campaign_lock is not None:
            self._campaign_lock.close()
            self._campaign_lock = None

    def _verify_prior(self):
        cfg = self.config
        if not cfg.prior_ledger_path:
            return
        if self._campaign_lock is None:
            raise Denied("continuation campaign lock is closed")
        prior = Path(cfg.prior_ledger_path).resolve()
        if hashlib.sha256(prior.read_bytes()).hexdigest() != cfg.prior_ledger_sha256:
            raise Denied("predecessor ledger changed")
        db = sqlite3.connect(prior.as_uri() + "?mode=ro", uri=True)
        try:
            totals = ledger_totals(db, cfg.reservation_accounting)
            unresolved = db.execute("SELECT COUNT(*) FROM attempts a LEFT JOIN completions c ON a.id=c.attempt WHERE c.attempt IS NULL").fetchone()[0]
            original = json.loads(db.execute("SELECT value FROM configuration WHERE id=1").fetchone()[0])
            count = totals['attempts'] + original.get('inherited_attempts', 0)
            total = totals['used'] + original.get('inherited_reserved_nanodollars', 0)
            if ((count,total) != (cfg.inherited_attempts,cfg.inherited_reserved_nanodollars)
                    or unresolved or original["deadline_epoch"] != cfg.deadline_epoch):
                raise Denied("predecessor counters, unresolved status or deadline differ")
        finally:
            db.close()

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.ledger, timeout=30)
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _prepare(self, route, payload):
        if route not in {"/v1/chat/completions", "/v1/embeddings"} or type(payload) is not dict:
            raise Denied("route or request denied")
        try:
            original = _json(payload)
        except (TypeError, ValueError):
            raise Denied("JSON request required") from None
        if self._secret in original or len(original.encode()) > self.config.max_request_bytes:
            raise Denied("oversized or credential-bearing request")
        matches = [m for m in self.config.models if m.alias == payload.get("model")]
        if not matches:
            raise Denied("unknown model alias")
        m = matches[0]
        embedding = route.endswith("embeddings")
        if embedding != (m.kind == "embedding"):
            raise Denied("model route mismatch")
        body = json.loads(original)
        if embedding:
            allowed = {"model", "input", "dimensions", "encoding_format", "input_type", "truncate", "modality"}
            inputs = body.get("input")
            if isinstance(inputs, str):
                inputs = [inputs]
            if not isinstance(inputs, list) or len(inputs) != 1 or not all(isinstance(x, str) and x for x in inputs):
                raise Denied("embedding requires exactly one nonempty text")
            for key, expected in (("input_type", "passage"), ("truncate", "END"), ("modality", "text")):
                if key in body and body[key] != expected:
                    raise Denied("unsupported NVIDIA embedding setting")
                body.pop(key, None)
            if body.get("dimensions", 2048) != 2048 or body.get("encoding_format", "float") != "float":
                raise Denied("2048 float embeddings required")
            body.update(dimensions=2048, encoding_format="float")
            output = 0
        else:
            allowed = {"model", "messages", "max_tokens", "max_completion_tokens", "temperature",
                       "top_p", "stream", "tools", "tool_choice", "response_format", "parallel_tool_calls"}
            messages = body.get("messages")
            if not isinstance(messages, list) or not messages:
                raise Denied("messages required")
            for message in messages:
                if (not isinstance(message, dict) or set(message) - {"role", "content", "name", "tool_calls", "tool_call_id"}
                        or message.get("role") not in {"system", "user", "assistant", "tool", "developer"}
                        or not isinstance(message.get("content", ""), (str, type(None)))):
                    raise Denied("text-only chat messages required")
            if body.get("stream", False) is not False or ("max_tokens" in body and "max_completion_tokens" in body):
                raise Denied("streaming or ambiguous output limit denied")
            output = body.get("max_completion_tokens", body.get("max_tokens"))
            if not _positive(output) or output > m.max_output_tokens:
                raise Denied("bounded output including reasoning required")
            # Native SDK sends max_completion_tokens; preserve original but normalize
            # the forwarded parameter advertised by the pinned Google endpoint.
            body.pop("max_completion_tokens", None)
            body["max_tokens"] = output
            if "tools" in body and (not isinstance(body["tools"], list) or any(
                    not isinstance(tool, dict) or set(tool) != {"type", "function"}
                    or tool.get("type") != "function" or not isinstance(tool.get("function"), dict)
                    for tool in body["tools"])):
                raise Denied("only client-executed function declarations allowed")
            # No server tools, plugins, cache-control blocks or account presets.
            if "response_format" in body and (not isinstance(body["response_format"], dict)
                    or body["response_format"].get("type") not in {"text", "json_object", "json_schema"}
                    or set(body["response_format"]) - {"type", "json_schema"}):
                raise Denied("unsupported response format")
            for key, low, high in (("temperature", 0, 2), ("top_p", 0, 1)):
                if key in body and (type(body[key]) not in (int, float) or not low <= body[key] <= high):
                    raise Denied("sampling setting denied")
        if set(payload) - allowed:
            raise Denied("unsupported request settings")
        body["model"] = m.actual_id
        body["provider"] = {"order": [m.provider], "only": [m.provider],
                            "allow_fallbacks": False, "require_parameters": True,
                            # OpenRouter max_price units are USD per million tokens.
                            "max_price": {"prompt": m.input_nanodollars_per_token / 1000,
                                          "completion": m.output_nanodollars_per_token / 1000,
                                          "request": 0}}
        wire = _json(body).encode()
        if len(wire) > self.config.max_request_bytes:
            raise Denied("adapted request oversized")
        # Reserve the entire documented provider input/output ceilings, independent
        # of JSON size, schema transformation, actual usage and requested output.
        return m, original, wire

    def handle(self, route: str, payload: dict) -> Response:
        m, original, wire = self._prepare(route, payload)
        reservation = m.reservation_nanodollars or self.config.per_call_nanodollars
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self._verify_prior()
            now = self.clock()
            if now + self.config.timeout_seconds > self.config.deadline_epoch:
                raise Denied("campaign deadline reached")
            totals = ledger_totals(db, self.config.reservation_accounting)
            count, total = totals['attempts'], totals['used']
            role_cap = self.config.embedding_attempt_cap if m.kind == "embedding" else self.config.chat_attempt_cap
            role_count = db.execute("SELECT COUNT(*) FROM attempts WHERE route=?", (route,)).fetchone()[0]
            if role_cap and role_count >= role_cap:
                raise Denied("campaign reservation limit reached")
            if (count + self.config.inherited_attempts >= self.config.call_cap
                    or total + self.config.inherited_reserved_nanodollars + reservation > self.config.total_nanodollars):
                raise Denied("campaign reservation limit reached")
            cursor = db.execute("INSERT INTO attempts(started,route,alias,model,original,request,sha256,reserved) VALUES(?,?,?,?,?,?,?,?)",
                (now, route, m.alias, m.actual_id, original, wire.decode(), hashlib.sha256(wire).hexdigest(), reservation))
            attempt = cursor.lastrowid
        # Reservation committed with FULL synchronous before any transport invocation.
        response = None
        usage = None
        error = None
        try:
            response = self.transport(route, wire, self._secret, self.config.timeout_seconds,
                                      self.config.max_response_bytes)
            if not isinstance(response, Response) or type(response.body) is not bytes:
                response = None
                raise Denied("transport contract violation")
            if len(response.body) > self.config.max_response_bytes:
                raise Denied("response exceeds transport limit")
            parsed = json.loads(response.body)
            if not isinstance(parsed, dict) or parsed.get('error') is not None:
                raise Denied('provider returned an error payload')
            usage = _json(parsed.get("usage"))
            if not 200 <= response.status < 300:
                raise Denied("provider returned error")
            if m.kind == "embedding":
                expected = payload["input"]
                count = 1 if isinstance(expected, str) else len(expected)
                data = parsed.get("data", [])
                if (len(data) != count or sorted(x.get("index", -1) for x in data) != list(range(count))
                    or any(len(x.get("embedding", [])) != 2048 or any(type(v) not in (int, float) or not math.isfinite(v)
                        for v in x["embedding"]) for x in data)):
                    raise Denied("provider did not return genuine 2048-dimensional vectors")
        except BaseException as exc:
            # Exception messages may contain headers/credentials. Preserve category only.
            error = type(exc).__name__
            if not isinstance(exc, Exception):
                raise
        finally:
            raw = response.body if response else None
            if raw is not None:
                raw = raw.replace(self._secret.encode(), b"[REDACTED]")
            if usage is not None:
                usage = usage.replace(self._secret, "[REDACTED]")
            with self._db() as db:
                db.execute("INSERT INTO completions VALUES(?,?,?,?,?,?)",
                    (attempt, self.clock(), response.status if response else None, raw, usage, error))
        if error:
            raise Denied(f"attempt {attempt} failed ({error}); reservation retained")
        if self.config.reservation_accounting == 'settled':
            # A missing/invalid cost is not refunded and must stop native retries.
            reported = parsed.get('usage')
            cost = reported.get('cost') if isinstance(reported, dict) else None
            if (not isinstance(cost, (int, float)) or isinstance(cost, bool)
                    or not math.isfinite(cost) or cost < 0
                    or Decimal(str(cost)) * 1_000_000_000 > reservation):
                raise Denied('unconfirmed cost or campaign overage; reservation retained')
        return response
