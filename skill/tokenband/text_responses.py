#!/usr/bin/env python3
"""Portable packaged Responses transport (TokenBand TB-P1-TEXT).

Implements accepted architecture §2.2-§2.5 for the ``protocol: "responses"``
connection, reusing reviewed companion semantics (step_text_api/step_slot/
app_transport) as a bounded, host-independent stdlib module. It imports nothing
from the private host/runtime tree and exposes no second driver, framework,
service, daemon or queue.

Guarantees honoured here (the worker supplies the frozen-snapshot callback,
credential, composed endpoint and no-proxy/no-redirect opener):
  * one POST per attempt; a caller ``before_request`` callback runs before each
    physical POST; the request body carries only model/input/stream/reasoning.
  * strict SSE parsing: each raw line and the aggregate raw event are bounded to
    2 MiB BEFORE any append/join/decode; strict UTF-8; reasoning is counted and
    discarded; the visible buffer is bounded at 1,000,000 characters.
  * closed-set terminals: completed | incomplete | failed | cancelled | unknown;
    tools/refusal/reasoning-marker reject without publishing unsafe content.
  * finite, shared 180-second recovery: only an unaccepted transient 429 is
    retried, at most 3 times, delay max(15/30/60, valid Retry-After); accepted or
    ambiguously accepted work is never replayed.
"""
from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
import http.client
import json
import re
import time
import urllib.error
import urllib.request

# --- bounded constants (reviewed companion semantics) ----------------------
MAX_BUFFER_CHARS = 1_000_000            # visible answer character bound
MAX_SSE_LINE_BYTES = 2 * 1024 * 1024    # per raw SSE line
MAX_SSE_EVENT_BYTES = 2 * 1024 * 1024   # aggregate raw event since delimiter
RECOVERY_BUDGET_SECONDS = 180           # shared unaccepted-429 recovery budget
MAX_RETRIES = 3                         # retries after the initial failure
ERROR_BODY_LIMIT = 4096                 # bounded error body read for classing
SOCKET_TIMEOUT = 300.0                  # inactivity timeout; no job deadline
DEFAULT_READ_SIZE = 65536
OVERFLOW_PROBE = 1                   # one byte detects a real overflow

REASONING_MARKER = re.compile(
    r"(?:<|&lt;)\s*/?\s*(?:think|analysis)\b[^>]*?(?:>|&gt;)", re.IGNORECASE
)

_TEXT_DELTA_EVENTS = {"response.output_text.delta"}
_REASONING_DELTA_EVENTS = {
    "response.reasoning_text.delta",
    "response.reasoning_summary_text.delta",
    "response.reasoning.delta",
}
_ITEM_EVENTS = {"response.output_item.added", "response.output_item.done"}
_TOOL_ITEM_TYPES = {"function_call", "custom_tool_call", "tool_call", "local_shell_call"}
_TOOL_EVENT_SUBSTRINGS = ("function_call", "tool_call", "local_shell_call")
_REFUSAL_EVENTS = {"response.refusal.delta", "response.refusal.done"}
_TERMINAL_FAILED = {"failed", "cancelled"}

RetryDecision = namedtuple("RetryDecision", ["decision", "delay_seconds", "reason"])


@dataclass
class ResponsesResult:
    """A known accepted terminal (completed | incomplete | failed)."""

    acceptance: str
    terminal: str
    completeness: str
    content: str
    reported: dict
    failure_class: str | None = None
    terminal_metadata: dict | None = None


class ResponsesError(Exception):
    """Sanitized transport failure. Never carries a raw body/header/reasoning."""

    def __init__(self, code, message, *, acceptance="unaccepted", terminal=None,
                 failure_class=None, retry_after=None, http_status=None):
        super().__init__(message)
        self.code = code
        self.acceptance = acceptance
        self.terminal = terminal
        self.failure_class = failure_class
        self.retry_after = retry_after
        self.http_status = http_status


# --- request / classification helpers --------------------------------------
def build_request_body(model, input_text, reasoning_effort):
    """Exactly model/input/stream/reasoning; never tools/tool_choice/max_output_tokens."""
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string")
    if not isinstance(input_text, str) or not input_text.strip():
        raise ValueError("input text must be a non-empty string")
    body = {"model": model, "input": input_text, "stream": True}
    if reasoning_effort:
        body["reasoning"] = {"effort": reasoning_effort}
    return body


def classify_failure(http_status, body_class):
    """transient_429 | access | quota | other (quota body class takes precedence)."""
    if body_class in {"quota", "insufficient_quota", "insufficient_balance"}:
        return "quota"
    if http_status == 429:
        return "transient_429"
    if http_status in (401, 403):
        return "access"
    if http_status == 402:
        return "quota"
    return "other"


def retry_plan(retry_after, attempt, budget_start, *, now,
               max_retries=MAX_RETRIES, recovery_budget_seconds=RECOVERY_BUDGET_SECONDS):
    """Plan one retry of an unaccepted transient 429.

    ``attempt`` is the 1-based retry being considered; delay is
    max(15/30/60, valid Retry-After) preserving the lower bounds; the shared
    180-second recovery budget clamps the whole series across client layers.
    """
    now_value = float(now())
    if attempt < 1:
        return RetryDecision("fail", 0.0, "attempt numbering starts at 1")
    if attempt > max_retries:
        return RetryDecision("exhausted", 0.0, "retry series exhausted after %d retries" % max_retries)
    hint = 0.0
    if retry_after is not None:
        if retry_after < 0:
            return RetryDecision("fail", 0.0, "negative Retry-After is invalid")
        hint = float(retry_after)
    schedule = min(15.0 * (2 ** (attempt - 1)), 60.0)
    delay = max(schedule, hint)
    if now_value + delay - budget_start > recovery_budget_seconds:
        return RetryDecision("exhausted", 0.0, "shared recovery budget exhausted")
    return RetryDecision("retry", delay, "within retry count and recovery budget")


def parse_retry_after(headers, *, now):
    """Return a non-negative hint (seconds) or None; invalid present value blocks."""
    value = None
    if headers is not None:
        try:
            value = headers.get("Retry-After")
        except AttributeError:
            value = None
    if value is None:
        return None
    text = value.strip() if isinstance(value, str) else value
    if isinstance(text, str) and re.fullmatch(r"[0-9]{1,10}", text):
        return float(int(text))
    try:
        parsed = parsedate_to_datetime(str(text))
    except (ValueError, TypeError):
        parsed = None
    if parsed is None:
        raise ResponsesError("invalid_retry_after", "Invalid retry timing; no early replay is sent.",
                             acceptance="unaccepted", failure_class="transient_429", http_status=429)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, parsed.timestamp() - float(now()))


def quota_body_class(raw):
    """Classify a bounded error body for quota detection, then discard it."""
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    for key in ("code", "type"):
        value = error.get(key)
        if isinstance(value, str) and value.strip().lower() in {
                "quota", "insufficient_quota", "insufficient_balance"}:
            return value.strip().lower()
    return None


def numeric_usage(usage):
    """Strict-integer usage only; untrusted strings are deferred (never returned)."""
    if not isinstance(usage, dict):
        return {}
    counts = {}
    for path, name in ((("input_tokens",), "input_tokens"),
                       (("output_tokens",), "output_tokens"),
                       (("total_tokens",), "total_tokens"),
                       (("input_tokens_details", "cached_tokens"), "cached_input_tokens"),
                       (("output_tokens_details", "reasoning_tokens"), "reasoning_tokens")):
        value = usage
        for component in path:
            value = value.get(component) if isinstance(value, dict) else None
        if type(value) is int and 0 <= value <= 2 ** 63 - 1:
            counts[name] = value
    return counts


def reported_usage(usage):
    counts = numeric_usage(usage)
    return {"usage": counts, "usage_scope": "response", "model": None,
            "request_id": None, "response_id": None, "string_fields_reason": "deferred"}


def incomplete_metadata(payload):
    """Allowlisted incomplete reason observation + strict-integer usage."""
    response = payload.get("response") if isinstance(payload, dict) else None
    value = None
    observation = "missing"
    if response is not None:
        if not isinstance(response, dict):
            observation = "invalid"
        else:
            details = response.get("incomplete_details")
            if details is not None:
                if not isinstance(details, dict):
                    observation = "invalid"
                else:
                    reason = details.get("reason")
                    if reason is not None:
                        if not isinstance(reason, str):
                            observation = "invalid"
                        elif reason == "max_output_tokens":
                            value, observation = "max_output_tokens", "reported"
                        elif reason == "content_filter":
                            value, observation = "content_filter", "reported"
                        else:
                            observation = "unknown"
    metadata = {"incomplete_reason": {"value": value, "observation": observation}}
    usage = response.get("usage") if isinstance(response, dict) else None
    counts = numeric_usage(usage)
    if counts:
        metadata["usage"] = counts
    return metadata


def _incomplete_reason(response_obj):
    """The declared incomplete reason, or None when the payload declares none."""
    if not isinstance(response_obj, dict):
        return None
    details = response_obj.get("incomplete_details")
    if not isinstance(details, dict):
        return None
    reason = details.get("reason")
    return reason if isinstance(reason, str) and reason else None


def _is_tool_event(event_type):
    return isinstance(event_type, str) and any(s in event_type for s in _TOOL_EVENT_SUBSTRINGS)


class _DeadlineGuard:
    """A read-source proxy that keeps the shared recovery deadline enforced
    between the individual receives a composite stdlib read performs.

    The stdlib chunked parser reads the chunk-size line (with its extension), the
    inter-chunk CRLF and the trailer through several buffered
    ``readline``/``read`` calls on the response's file, and each of those may
    perform several raw receives. A single socket timeout bounds one receive,
    not that series, so the guard re-implements the buffered calls as loops over
    ``read1`` -- which performs at most one raw read -- and checks the shared
    deadline and re-times the socket before every one of them. The stdlib framing
    itself is untouched: no second transport, thread, daemon or watchdog.
    """

    __slots__ = ("_source", "_expire", "_retime")

    def __init__(self, source, expire, retime):
        object.__setattr__(self, "_source", source)
        object.__setattr__(self, "_expire", expire)
        object.__setattr__(self, "_retime", retime)

    def _step(self, produce):
        """One low-level receive under the shared recovery deadline.

        The deadline and the remaining socket timeout are (re)applied before the
        receive, and if the receive raises because the socket timeout fired
        exactly as the shared budget ran out, the deadline check is run once more
        so the context's classification is raised -- accepted/unknown for a body
        or a guarded status/header read, exhausted for an unaccepted error body --
        instead of a bare OSError escaping the guard. A genuine inactivity timeout
        that is still inside the budget is left to propagate unchanged.
        """
        object.__getattribute__(self, "_expire")()
        object.__getattribute__(self, "_retime")()
        try:
            return produce()
        except OSError:
            object.__getattribute__(self, "_expire")()
            raise

    def _set_expire(self, expire):
        object.__setattr__(self, "_expire", expire)

    def read1(self, *args):
        return self._step(lambda: object.__getattribute__(self, "_source").read1(*args))

    def peek(self, *args):
        return self._step(lambda: object.__getattribute__(self, "_source").peek(*args))

    def readinto(self, b):
        return self._step(lambda: object.__getattribute__(self, "_source").readinto(b))

    def read(self, size=-1):
        source = object.__getattribute__(self, "_source")
        if size is None or size < 0:
            parts = []
            while True:
                chunk = self._step(lambda: source.read1(-1))
                if not chunk:
                    break
                parts.append(chunk)
            return b"".join(parts)
        parts = []
        total = 0
        while total < size:
            chunk = self._step(lambda: source.read1(size - total))
            if not chunk:
                break
            parts.append(chunk)
            total += len(chunk)
        return b"".join(parts)

    def readline(self, limit=-1):
        source = object.__getattribute__(self, "_source")
        if limit is None or limit < 0:
            limit = -1
        peek = getattr(source, "peek", None)
        parts = []
        total = 0
        while True:
            if callable(peek):
                # Look ahead without advancing; peek performs at most one raw
                # read, and everything it returned is already buffered.
                ahead = self._step(lambda: peek(1))
                if not ahead:
                    break
                cut = ahead.find(b"\n")
                if cut >= 0:
                    take = cut + 1
                    if limit >= 0 and total + take > limit:
                        take = limit - total
                    if take <= 0:
                        break
                    parts.append(self._step(lambda: source.read(take)))
                    total += take
                    break
                take = len(ahead)
                if limit >= 0 and total + take > limit:
                    take = limit - total
                if take <= 0:
                    break
                parts.append(self._step(lambda: source.read(take)))
                total += take
                if limit >= 0 and total >= limit:
                    break
            else:
                # No look-ahead primitive: step one byte at a time so the
                # delimiter is never overshot and no byte is lost.
                chunk = self._step(lambda: source.read1(1))
                if not chunk:
                    break
                parts.append(chunk)
                total += 1
                if chunk.endswith(b"\n"):
                    break
                if limit >= 0 and total >= limit:
                    break
        return b"".join(parts)

    def close(self):
        source = object.__getattribute__(self, "_source")
        close = getattr(source, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_source"), name)


class _GuardedSocket:
    """A socket proxy that deadline-guards the file the stdlib parser reads the
    HTTP status line and ordinary headers from -- INSIDE the opener call.

    urllib reads the status line and the response headers while the opener is
    still running (``do_open`` -> ``getresponse`` -> ``begin``), which is before
    the transport can install a guard on the returned response, so those receives
    used to escape the one shared recovery deadline entirely. Wrapping the
    connection's socket here makes ``makefile`` hand the parser a guarded file, so
    the status line and headers are bounded by the shared deadline exactly like
    the body reads are. No second transport, thread, daemon or watchdog is used;
    the real stdlib framing and parsing are untouched.
    """

    __slots__ = ("_sock", "_client")

    def __init__(self, sock, client):
        object.__setattr__(self, "_sock", sock)
        object.__setattr__(self, "_client", client)

    def makefile(self, *args, **kwargs):
        fp = object.__getattribute__(self, "_sock").makefile(*args, **kwargs)
        if isinstance(fp, _DeadlineGuard):
            return fp
        client = object.__getattribute__(self, "_client")
        return _DeadlineGuard(fp, client._accepted_deadline_exceeded, self._retime)

    def _retime(self):
        sock = object.__getattribute__(self, "_sock")
        settimeout = getattr(sock, "settimeout", None)
        if callable(settimeout):
            settimeout(object.__getattribute__(self, "_client")._io_timeout())

    def settimeout(self, value):
        object.__getattribute__(self, "_sock").settimeout(value)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_sock"), name)


def _guarded_connection_class(base_conn, client):
    """A connection subclass whose ``getresponse`` guards the socket so the
    status line and headers it reads are bounded by the shared deadline."""
    class GuardedConnection(base_conn):
        def getresponse(self):
            real = getattr(self, "sock", None)
            if real is not None and not isinstance(real, _GuardedSocket):
                self.sock = _GuardedSocket(real, client)
            try:
                return base_conn.getresponse(self)
            finally:
                if real is not None:
                    self.sock = real
    return GuardedConnection


# --- transport -------------------------------------------------------------
class ResponsesTextClient:
    def __init__(self, *, key, endpoint, payload, opener, before_request=None,
                 clock=time.monotonic, sleeper=time.sleep, now=time.time,
                 inactivity_timeout=SOCKET_TIMEOUT, read_size=DEFAULT_READ_SIZE):
        self._key = key
        self._endpoint = endpoint
        self._payload = payload
        self._opener = opener
        self._before_request = before_request
        self._clock = clock
        self._sleeper = sleeper
        self._now = now
        self._inactivity_timeout = inactivity_timeout
        self._read_size = read_size
        self._recovery_deadline = None
        self._guarded_cache = None

    # -- recovery budget ---------------------------------------------------
    def _remaining_recovery(self):
        if self._recovery_deadline is None:
            return None
        remaining = self._recovery_deadline - self._clock()
        if remaining <= 0:
            raise ResponsesError("text_429_exhausted", "the shared recovery deadline is exhausted",
                                 acceptance="unaccepted", failure_class="transient_429", http_status=429)
        return remaining

    def _io_timeout(self):
        """Inactivity timeout clamped by the remaining shared recovery budget (never raises)."""
        if self._recovery_deadline is None:
            return self._inactivity_timeout
        remaining = self._recovery_deadline - self._clock()
        if remaining <= 0:
            return 0.0
        return min(self._inactivity_timeout, remaining)

    def _accepted_deadline_exceeded(self):
        """Accepted body I/O that outlives the shared deadline is ambiguous, never unaccepted."""
        if self._recovery_deadline is not None and self._clock() >= self._recovery_deadline:
            raise ResponsesError("text_response_unknown",
                                 "the shared recovery deadline expired during accepted body I/O",
                                 acceptance="accepted", terminal="unknown")

    def _begin_recovery(self, status):
        if status == 429 and self._recovery_deadline is None:
            self._recovery_deadline = self._clock() + RECOVERY_BUDGET_SECONDS

    def _budget_start(self):
        if self._recovery_deadline is None:
            return self._clock()
        return self._recovery_deadline - RECOVERY_BUDGET_SECONDS

    # -- submission --------------------------------------------------------
    def submit(self):
        self._recovery_deadline = None
        attempt = 0
        while True:
            if self._before_request is not None:
                self._before_request()
            try:
                return self._attempt()
            except ResponsesError as exc:
                if exc.code != "transient_429" or exc.acceptance != "unaccepted":
                    raise
                attempt += 1
                decision = retry_plan(exc.retry_after, attempt, self._budget_start(), now=self._clock)
                if decision.decision != "retry":
                    raise ResponsesError(
                        "text_429_exhausted",
                        "the transient 429 retry series or shared recovery budget is exhausted (%s)" % decision.reason,
                        acceptance="unaccepted", failure_class="transient_429",
                        retry_after=exc.retry_after, http_status=429) from exc
                self._sleeper(decision.delay_seconds)

    def _attempt(self):
        response = self._request()
        try:
            return self._consume(response)
        finally:
            self._close(response)

    def _request(self):
        request = urllib.request.Request(self._endpoint, data=self._payload, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "text/event-stream")
        request.add_header("Authorization", "Bearer " + self._key)
        request.add_header("User-Agent", "tokenband/1")
        remaining = self._remaining_recovery()
        timeout = self._inactivity_timeout if remaining is None else min(self._inactivity_timeout, remaining)
        try:
            opener = self._opener
            director = getattr(opener, "__self__", None)
            if self._recovery_deadline is not None and isinstance(director, urllib.request.OpenerDirector):
                # The stdlib opener reads the status line and the ordinary
                # response headers INSIDE this call, before it returns, so the one
                # shared recovery deadline has to bound those receives too -- not
                # only the body that is read after it returns. A cached guarded
                # copy of the director wraps the connection's socket for exactly
                # that; a scripted test opener (not a bound director method) is
                # used unchanged so the existing retry scenarios are untouched.
                opener = self._guarded_open(director)
            response = opener(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            try:
                status = int(exc.code or 0)
                self._begin_recovery(status)
                self._install_deadline_guard(exc, expire=self._remaining_recovery)
                if 300 <= status < 400:
                    raise ResponsesError("text_redirect_rejected", "the endpoint returned a redirect",
                                         acceptance="unaccepted", http_status=status) from exc
                retry_after = parse_retry_after(getattr(exc, "headers", None), now=self._now) if status == 429 else None
                body_class = None
                try:
                    body_class = quota_body_class(self._read_error_body(exc))
                except ResponsesError:
                    raise
                except Exception:
                    body_class = None
                raise self._classified(status, body_class, retry_after) from exc
            finally:
                exc.close()
        except urllib.error.URLError as exc:
            self._remaining_recovery()
            raise ResponsesError("text_dispatch_unknown", "connection failed before the POST boundary",
                                 acceptance="unknown") from exc
        except OSError as exc:
            raise ResponsesError("text_dispatch_unknown", "the POST outcome is unknown",
                                 acceptance="unknown") from exc
        status = int(getattr(response, "status", 200) or 200)
        if 300 <= status < 400:
            self._close(response)
            raise ResponsesError("text_redirect_rejected", "the endpoint returned a redirect",
                                 acceptance="unaccepted", http_status=status)
        final_url = getattr(response, "geturl", lambda: self._endpoint)()
        if final_url != self._endpoint:
            self._close(response)
            raise ResponsesError("text_destination_override",
                                 "the response came from a destination other than the composed endpoint",
                                 acceptance="unaccepted")
        if status != 200:
            self._close(response)
            raise self._classified(status, None,
                                   parse_retry_after(getattr(response, "headers", None), now=self._now))
        self._install_deadline_guard(response)
        self._set_response_timeout(response, timeout)
        return response

    @staticmethod
    def _classified(status, body_class, retry_after):
        kind = classify_failure(status, body_class)
        if kind == "transient_429":
            return ResponsesError("transient_429", "the endpoint returned a transient 429",
                                  acceptance="unaccepted", failure_class="transient_429",
                                  retry_after=retry_after, http_status=status)
        if kind == "access":
            return ResponsesError("text_access_denied", "the endpoint denied access",
                                  acceptance="unaccepted", failure_class="access", http_status=status)
        if kind == "quota":
            return ResponsesError("text_quota", "the endpoint reported a quota-class failure",
                                  acceptance="unaccepted", failure_class="quota", http_status=status)
        return ResponsesError("text_http_failure", "the endpoint returned a non-success status",
                              acceptance="unaccepted", failure_class="other", http_status=status)

    def _read_error_body(self, response):
        """Bounded classification read: one low-level step at a time, deadline-checked.

        A buffered ``read`` can perform an unbounded number of internal receives
        under a single socket timeout, so the shared deadline is re-checked between
        real receives instead of only after the composite call returns.
        """
        reader = getattr(response, "read1", None)
        if not callable(reader):
            # No single-shot low-level read is exposed, so the deadline cannot be
            # enforced between receives; read nothing rather than exceed it.
            return b""
        parts = []
        budget = ERROR_BODY_LIMIT
        while budget > 0:
            self._remaining_recovery()
            self._set_response_timeout(response, self._io_timeout())
            chunk = reader(budget)
            self._remaining_recovery()
            if not chunk:
                break
            parts.append(chunk)
            budget -= len(chunk)
        return b"".join(parts)

    def _guarded_open(self, director):
        """A cached copy of a real OpenerDirector whose HTTP handlers wrap the
        connection so the status line and headers are deadline-guarded too.

        The original director and its handlers are never mutated: every handler is
        copied (its instance state preserved) and only the HTTP/HTTPS handlers get
        a wrapped ``do_open``. A non-OpenerDirector opener is never routed here.
        """
        cached = self._guarded_cache
        if cached is not None and cached[0] is director:
            return cached[1]
        guarded = urllib.request.OpenerDirector()
        guarded.addheaders = list(getattr(director, "addheaders", []))
        for handler in list(getattr(director, "handlers", [])):
            guarded.add_handler(self._guarded_handler(handler))
        self._guarded_cache = (director, guarded.open)
        return guarded.open

    def _guarded_handler(self, handler):
        try:
            cls = type(handler)
            inst = cls.__new__(cls)
            inst.__dict__.update(handler.__dict__)
        except Exception:
            return handler
        if isinstance(handler, urllib.request.AbstractHTTPHandler):
            guarded_cls = type("Guarded" + cls.__name__, (cls,), {"do_open": self._make_guarded_do_open()})
            wrapped = guarded_cls.__new__(guarded_cls)
            wrapped.__dict__.update(inst.__dict__)
            return wrapped
        return inst

    def _make_guarded_do_open(self):
        client = self

        def do_open(handler_self, http_class, req, **http_conn_args):
            guarded_conn = _guarded_connection_class(http_class, client)
            return urllib.request.AbstractHTTPHandler.do_open(handler_self, guarded_conn, req, **http_conn_args)

        return do_open

    def _install_deadline_guard(self, response, expire=None):
        """Guard the response's buffered read source with the shared deadline.

        Only installed while a recovery deadline is actually active: without a
        prior 429 the inactivity timeout alone bounds the body, exactly as
        before. The guard wraps the file the stdlib parser reads from, so the
        chunk-size line, the inter-chunk CRLF and the trailer are covered too.

        ``expire`` selects the classification of an expiry: an accepted body that
        outlives the budget is ambiguous, while an unaccepted error body stays
        an exhausted retry series.
        """
        if self._recovery_deadline is None:
            return
        holder = None
        source = None
        current = response
        for _ in range(4):
            nxt = getattr(current, "fp", None)
            if nxt is None or nxt is current:
                break
            holder, source = current, nxt
            current = nxt
        if holder is None or source is None:
            return
        if isinstance(source, _DeadlineGuard):
            # A guarded opener already wrapped this source while it read the
            # status line and headers; keep that guard but honour the
            # classification this call wants, so a real-opener unaccepted error
            # body still expires as an exhausted retry series, not accepted.
            if expire is not None:
                source._set_expire(expire)
            return
        if not (hasattr(source, "read1") or hasattr(source, "readline")):
            return
        try:
            holder.fp = _DeadlineGuard(source, expire or self._accepted_deadline_exceeded,
                                       lambda: self._retime_source(source))
        except Exception:
            return

    def _retime_source(self, source):
        """Re-time the socket behind a read source to what is actually left."""
        raw = getattr(source, "raw", None)
        sock = getattr(raw, "_sock", None)
        if sock is not None and callable(getattr(sock, "settimeout", None)):
            sock.settimeout(self._io_timeout())

    @staticmethod
    def _set_response_timeout(response, seconds):
        current = response
        for _ in range(3):
            raw = getattr(current, "raw", None)
            sock = getattr(raw, "_sock", None)
            if sock is not None and callable(getattr(sock, "settimeout", None)):
                sock.settimeout(seconds)
                return
            current = getattr(current, "fp", None)
            if current is None:
                return

    @staticmethod
    def _close(response):
        close = getattr(response, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    # -- strict SSE --------------------------------------------------------
    def _iter_sse(self, response):
        event_name = None
        data_lines = []
        pending = b""
        event_size = 0

        def bound(msg):
            return ResponsesError("text_response_unknown", msg, acceptance="accepted", terminal="unknown")

        def dispatch_line(raw_line):
            nonlocal event_name, data_lines
            try:
                line = raw_line.decode("utf-8").rstrip("\r\n")
            except UnicodeDecodeError as exc:
                raise bound("the SSE stream is not valid UTF-8") from exc
            if line == "":
                if data_lines:
                    dispatched = (event_name, "\n".join(data_lines))
                    event_name, data_lines = None, []
                    return dispatched
                # A real delimiter always resets the event state, even with no data:
                # an empty event never leaks its name into the following event.
                event_name, data_lines = None, []
                return None
            if line.startswith(":"):
                return None
            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
            if field == "event":
                event_name = value
            elif field == "data":
                data_lines.append(value)
            return None

        while True:
            # Charge the aggregate event bound to the bytes that already belong to
            # the open event: the completed lines counted in ``event_size`` plus the
            # partial line in ``pending``. A delimiter that arrives inside the same
            # read step resets the counter, so bytes owned by the NEXT event are
            # never charged to the one that is closing and a valid event sitting
            # exactly at the bound is accepted whatever the read/HTTP/chunk split.
            # The read still pulls one probe byte past the tighter budget so the
            # explicit bound check rejects an event that is one byte over instead of
            # the read being mistaken for the end of the stream. All of this happens
            # BEFORE any concatenation, join or decode.
            charged = event_size + len(pending)
            line_room = MAX_SSE_LINE_BYTES - len(pending)
            event_room = MAX_SSE_EVENT_BYTES - charged
            allowance = line_room if line_room < event_room else event_room
            size = self._read_size if allowance + OVERFLOW_PROBE >= self._read_size else allowance + OVERFLOW_PROBE
            if size < 1:
                # A budget that is already exhausted must still take one probe
                # step so the explicit bound check below rejects instead of the
                # read being mistaken for the end of the stream.
                size = 1
            # The one shared recovery deadline also bounds accepted body I/O; expiry
            # there stays accepted/unknown and is never turned into a retry.
            self._accepted_deadline_exceeded()
            self._set_response_timeout(response, self._io_timeout())
            # One low-level I/O step per iteration. read1 performs at most one receive
            # on the underlying raw stream, so the deadline is re-checked between real
            # receives instead of inside a single buffered call.
            reader = getattr(response, "read1", None)
            if callable(reader):
                chunk = reader(size)
            elif self._recovery_deadline is None:
                # No shared recovery budget governs this body; the inactivity timeout
                # alone bounds it, exactly as before.
                chunk = response.readline(size)
            else:
                # A buffered readline/read can perform an unbounded number of internal
                # receives inside one call, so the deadline cannot be enforced between
                # them; fail closed rather than silently exceed the accepted budget.
                raise bound("the body exposes no bounded low-level read, so the shared recovery deadline cannot be enforced")
            self._accepted_deadline_exceeded()
            if chunk == b"":
                if pending:
                    if len(pending) > MAX_SSE_LINE_BYTES:
                        raise bound("an SSE line exceeded the bounded length")
                    if event_size + len(pending) > MAX_SSE_EVENT_BYTES:
                        raise bound("an SSE event exceeded the bounded size")
                    dispatched = dispatch_line(pending + b"\n")
                    if dispatched is not None:
                        yield dispatched
                if data_lines:
                    yield (event_name, "\n".join(data_lines))
                return
            pending += chunk
            if len(pending) > MAX_SSE_LINE_BYTES + OVERFLOW_PROBE:
                raise bound("an SSE line exceeded the bounded length")
            # A single low-level step can carry several complete lines and several
            # delimiters; each completed line is charged to the event that is open
            # right now, and a blank delimiter line closes that event and restarts
            # the counter at zero so only the bytes that follow it are counted for
            # the next event. Counting the whole read step up front would charge
            # the next event's bytes to the closing one and falsely overflow a
            # valid near-bound event.
            while b"\n" in pending:
                raw_line, pending = pending.split(b"\n", 1)
                if len(raw_line) + 1 > MAX_SSE_LINE_BYTES:
                    raise bound("an SSE line exceeded the bounded length")
                event_size += len(raw_line) + 1
                # The completed raw-line bytes -- including this line's framing,
                # and on a blank delimiter the whole event plus its delimiter --
                # belong to the event that is open right now. Enforce the aggregate
                # event bound HERE, before any decode/dispatch/yield and before a
                # delimiter resets the counter, so a completed MAX+1 event is
                # rejected even when its trailing blank-delimiter byte closes it and
                # even when that delimiter carries the terminal. A valid event that
                # sits exactly at the bound reaches at most MAX here and is
                # unaffected, so the R4 valid-boundary false overflow is not
                # reintroduced and the next event's tail in ``pending`` is never
                # charged to the closing event.
                if event_size > MAX_SSE_EVENT_BYTES:
                    raise bound("an SSE event exceeded the bounded size")
                dispatched = dispatch_line(raw_line + b"\n")
                if dispatched is not None:
                    yield dispatched
                if raw_line.rstrip(b"\r") == b"":
                    # A real delimiter closes the event; the bytes that follow it
                    # inside this same step are charged to the next event, so the
                    # counter restarts from zero and only ``pending`` is counted.
                    event_size = 0
            # The aggregate event bound must also hold for the bytes still charged
            # to the open event once this step's delimiters have been processed: a
            # long unfinished event keeps one event open across many single-byte
            # probe reads, so checking only inside the split loop would pull the
            # whole oversize event before the bound is noticed. ``event_size +
            # len(pending)`` is the true size of the event that is still open, so a
            # delimiter that fell mid-step can never overflow a valid event and a
            # genuinely oversized one is rejected before any decode or join.
            if event_size + len(pending) > MAX_SSE_EVENT_BYTES:
                raise bound("an SSE event exceeded the bounded size")

    def _consume(self, response):
        text_parts = []
        visible_chars = 0
        usage = None
        incomplete_meta = None
        terminal_seen = False
        observed_terminal = "unknown"
        refusal = False
        failed_class = None

        def known_failure(visible):
            """Known-failure evidence that is sufficient on any exit path.

            The visible text is joined exactly once per exit, so a late OSError,
            parser error, deadline expiry or malformed event can never downgrade
            already observed evidence into an ambiguous unknown, and no quadratic
            re-join is performed.
            """
            if failed_class is not None:
                return ResponsesResult(acceptance="accepted", terminal="failed", completeness="unknown",
                                       content="", reported=reported_usage(None),
                                       failure_class=failed_class, terminal_metadata=None)
            if REASONING_MARKER.search(visible):
                return ResponsesResult(acceptance="accepted", terminal="failed", completeness="unknown",
                                       content="", reported=reported_usage(None),
                                       failure_class="reasoning_marker", terminal_metadata=None)
            if refusal:
                return ResponsesResult(acceptance="accepted", terminal="failed", completeness="unknown",
                                       content="", reported=reported_usage(None),
                                       failure_class="refusal", terminal_metadata=None)
            return None

        try:
            for event_name, data in self._iter_sse(response):
                if data == "[DONE]":
                    continue
                try:
                    payload = json.loads(data)
                except ValueError as exc:
                    raise ResponsesError("text_response_unknown", "an SSE event carried invalid JSON",
                                         acceptance="accepted", terminal="unknown") from exc
                payload_type = payload.get("type") if isinstance(payload, dict) else None
                if not isinstance(payload_type, str):
                    payload_type = None
                # A tool marker rejects the event whichever field carries it, and the
                # two fields must not disagree: an unchecked conflict would let a
                # renamed event slip its real type past the reader.
                if _is_tool_event(event_name) or _is_tool_event(payload_type):
                    failed_class = "tools_rejected"
                    break
                if event_name and payload_type and event_name != payload_type:
                    failed_class = "tools_rejected"
                    break
                event_type = payload_type if payload_type is not None else event_name
                if event_type in _REFUSAL_EVENTS:
                    # A refusal is complete known-failure evidence on its own, so no
                    # further read is taken and no later error can discard it.
                    refusal = True
                    break
                if event_type in _TEXT_DELTA_EVENTS:
                    delta = payload.get("delta") if isinstance(payload, dict) else None
                    if isinstance(delta, str) and delta:
                        if "\0" in delta:
                            raise ResponsesError("text_response_unknown", "visible output carried a control character",
                                                 acceptance="accepted", terminal="unknown")
                        visible_chars += len(delta)
                        if visible_chars > MAX_BUFFER_CHARS:
                            raise ResponsesError("text_response_unknown", "visible output exceeded the bounded buffer",
                                                 acceptance="accepted", terminal="unknown")
                        text_parts.append(delta)
                elif event_type in _REASONING_DELTA_EVENTS:
                    continue  # counted and discarded; never persisted or published
                elif event_type in _ITEM_EVENTS:
                    item = payload.get("item") if isinstance(payload, dict) else None
                    item_type = item.get("type") if isinstance(item, dict) else None
                    if isinstance(item_type, str) and item_type in _TOOL_ITEM_TYPES:
                        failed_class = "tools_rejected"
                        break
                elif event_type == "response.completed":
                    terminal_seen = True
                    response_obj = payload.get("response") if isinstance(payload, dict) else None
                    status = response_obj.get("status") if isinstance(response_obj, dict) else None
                    if not isinstance(status, str):
                        raise ResponsesError("text_response_unknown", "unknown terminal status",
                                             acceptance="accepted", terminal="unknown")
                    if status in _TERMINAL_FAILED:
                        observed_terminal = "failed"
                        failed_class = "failed"
                        break
                    if status not in ("completed", "incomplete"):
                        raise ResponsesError("text_response_unknown", "unknown terminal status",
                                             acceptance="accepted", terminal="unknown")
                    # A declared incomplete reason keeps the result incomplete no
                    # matter which wrapper carried it; both wrappers classify alike.
                    incomplete_reason = _incomplete_reason(response_obj)
                    if status == "incomplete" or incomplete_reason is not None:
                        observed_terminal = "incomplete"
                        incomplete_meta = incomplete_metadata(payload)
                    else:
                        observed_terminal = status
                    if isinstance(response_obj, dict):
                        usage = response_obj.get("usage")
                    break
                elif event_type == "response.incomplete":
                    terminal_seen = True
                    observed_terminal = "incomplete"
                    incomplete_meta = incomplete_metadata(payload)
                    break
                elif event_type in ("response.failed", "error"):
                    terminal_seen = True
                    observed_terminal = "failed"
                    failed_class = "failed"
                    break
        except ResponsesError:
            # A transport, deadline, bound or parser error must not discard evidence
            # that was already reliably observed; only an unevidenced abort is unknown.
            failure = known_failure("".join(text_parts))
            if failure is not None:
                return failure
            raise
        except (OSError, ValueError, RecursionError, http.client.HTTPException) as exc:
            # A real transport failure includes the http.client family
            # (IncompleteRead on a truncated chunked body, BadStatusLine,
            # RemoteDisconnected, ...). They are not OSError/ValueError, so they
            # have to be classified here or already observed known-failure
            # evidence would be dropped and the worker would record an ambiguous
            # unknown instead of the known failed terminal. RecursionError is the
            # same story for a bounded but pathologically nested JSON event: the
            # stdlib parser raises it (it is a RuntimeError, not a ValueError), and
            # an already observed reasoning marker must survive it. BaseException
            # is still never caught: a system-level abort stays an abort.
            failure = known_failure("".join(text_parts))
            if failure is not None:
                return failure
            raise ResponsesError("text_response_unknown",
                                 "an accepted stream aborted before a terminal event; it is never automatically replayed",
                                 acceptance="accepted", terminal="unknown") from exc

        # Observed unsafe evidence is a known-failed terminal on its own: a stream that
        # ends at EOF, aborts or never declares a terminal must not downgrade that
        # evidence into an ambiguous unknown, and it is never automatically replayed.
        visible = "".join(text_parts)
        failure = known_failure(visible)
        if failure is not None:
            return failure
        if not terminal_seen:
            raise ResponsesError("text_response_unknown",
                                 "the stream ended without a terminal event; it is never automatically replayed",
                                 acceptance="accepted", terminal="unknown")
        completeness = "incomplete" if observed_terminal == "incomplete" else "complete"
        return ResponsesResult(acceptance="accepted", terminal=observed_terminal, completeness=completeness,
                               content=visible, reported=reported_usage(usage),
                               failure_class=None, terminal_metadata=incomplete_meta)
