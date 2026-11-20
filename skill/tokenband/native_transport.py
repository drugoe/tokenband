"""Bounded owned-stdio and local Unix-WebSocket native protocol transports."""
from __future__ import annotations
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import socket
import stat
import struct
import subprocess
import sys
import threading
import time
import uuid
import worker as w

LIMIT = 1024 * 1024
METHODS = {"initialize", "config/read", "permissionProfile/list", "model/list", "windowsSandbox/readiness",
           "thread/start", "thread/name/set", "thread/list", "thread/read", "thread/turns/list",
           "thread/items/list", "thread/resume", "turn/start", "turn/steer", "turn/interrupt", "command/exec"}
OBSERVER_METHODS = {"config/read", "permissionProfile/list", "model/list", "windowsSandbox/readiness",
                    "thread/list", "thread/read", "thread/turns/list", "thread/items/list", "turn/interrupt"}


class NativeRPCError(w.WorkflowError):
    """Only a matched reviewed request identity; never native message/data."""
    def __init__(self, method, request_id, rpc_code):
        self.method, self.request_id, self.rpc_code = method, request_id, rpc_code
        self.category = "unsupported_method" if rpc_code == -32601 else "matched_rejection"
        super().__init__("native_rpc_rejected", "Matched native RPC rejection (" + self.category + ").")


def encode(value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > LIMIT:
        w.fail("oversize_protocol", "Native protocol message too large.")
    return raw


def decode(raw):
    try:
        if len(raw) > LIMIT:
            raise ValueError()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=w.json_pairs,
                           parse_constant=lambda _: w.fail("invalid_protocol", "Nonfinite protocol value."))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeError):
        w.fail("invalid_protocol", "Malformed native message; contents suppressed.")


class OwnedStdio:
    shared = False
    _startup_failed = False

    def __init__(self, argv, cwd, control, *, environment_binding=None, environment_presence=None, environment_names=None):
        environment = os.environ.copy()
        if environment_names is not None and (not isinstance(environment_names, (list, tuple))
                or len(environment_names) > 1024 or any(not isinstance(name, str) for name in environment_names)
                or set(environment_names) != set(environment)):
            w.fail("native_environment_changed", "Native environment source inventory changed before launch.")
        binding = environment_binding or {}
        if not isinstance(binding, dict) or len(binding) > 128:
            w.fail("invalid_native_environment", "Native environment binding must be bounded.")
        for name, value in binding.items():
            if (not isinstance(name, str) or not name.replace("_", "").isalnum()
                    or any(part in name.upper() for part in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
                    or (value is not None and (not isinstance(value, str) or len(value) > 32768))):
                w.fail("invalid_native_environment", "Only qualified nonsecret environment identities may be bound.")
            if environment.get(name) != value:
                w.fail("native_environment_changed", "Effective native environment changed before launch; values suppressed.")
        presence = environment_presence or {}
        if not isinstance(presence, dict) or len(presence) > 128:
            w.fail("invalid_native_environment", "Native auth-source presence must be bounded.")
        for name, expected in presence.items():
            if not isinstance(name, str) or not name.replace("_", "").isalnum() or type(expected) is not bool:
                w.fail("invalid_native_environment", "Auth-source presence requires names and booleans only.")
            if (name in environment) != expected:
                w.fail("native_environment_changed", "Native auth-source presence changed; credential contents are not inspected.")
        self.control = Path(control)
        self.control.mkdir(parents=True, exist_ok=False)
        self.nonce = uuid.uuid4().hex
        self.spec, self.receipt = self.control / "launch.json", self.control / "cleanup.json"
        w.atomic_json(self.spec, {"argv": argv, "cwd": str(cwd), "receipt": str(self.receipt), "nonce": self.nonce})
        self.closed, self.reader = False, None
        self.process = subprocess.Popen([sys.executable, "-I", str(Path(__file__).with_name("native_owned.py")), str(self.spec)],
                                        cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, shell=False,
                                        env=environment,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            self.messages = queue.Queue(maxsize=256)
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
        except BaseException:
            self._startup_failed = True
            try:
                # This owner was never returned. Perform cleanup only; there
                # is no complete pipe observation or usable connection.
                self._close_after_failed_start()
            except BaseException:
                pass  # Keep the original constructor failure; do not retry.
            raise

    def _read(self):
        try:
            while True:
                raw = self.process.stdout.readline(LIMIT + 2)
                if not raw:
                    self.messages.put(None, timeout=1)
                    return
                if len(raw) > LIMIT + 1:
                    self.messages.put({"_protocol_error": "oversize"}, timeout=1)
                    return
                if not raw.endswith(b"\n"):
                    raise ValueError()
                self.messages.put(decode(raw), timeout=1)
        except Exception:
            try:
                self.messages.put({"_protocol_error": True}, timeout=1)
            except queue.Full:
                pass

    def send(self, value):
        try:
            self.process.stdin.write(encode(value) + b"\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            w.fail("native_write_unknown", "Native write failed; operation may have been accepted.")

    def receive(self, timeout=60):
        try:
            value = self.messages.get(timeout=timeout)
        except queue.Empty:
            w.fail("native_inactivity", "No native event within the bounded observation interval.")
        if isinstance(value, dict) and value.get("_protocol_error") == "oversize":
            w.fail("oversize_protocol", "Native frame exceeds the fixed 1 MiB bound; no complete response can be established.")
        if value is None or "_protocol_error" in value:
            w.fail("native_eof", "Native channel ended without a confirmed result.")
        return value

    def close(self):
        if self.closed:
            return self.proof
        try:
            self.process.stdin.close()
            self.process.wait(timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            self.process.terminate()  # Only the separately owned launcher.
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                w.fail("cleanup_unknown", "Owned launcher cleanup not proven; retain assignment.")
        self.reader.join(timeout=2)
        if self.process.stdout:
            self.process.stdout.close()
        return self._close_proof(self.receipt)

    def _close_proof(self, receipt):
        value = w.read_json(receipt)
        if value.get("nonce") != self.nonce or value.get("owner_pid") != self.process.pid or value.get("proof", {}).get("empty") is not True:
            w.fail("cleanup_unknown", "Kernel cleanup proof missing or bound to a different owner.")
        self.closed, self.proof = True, value["proof"]
        return self.proof

    def _close_after_failed_start(self):
        # A partially started reader gives no pipe observation. Verify the independently
        # bound owned launcher receipt without racing stdout handle closure.
        if self.closed:
            return self.proof
        try:
            self.process.stdin.close()
            self.process.wait(timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            try:
                self.process.terminate()  # Only the separately owned launcher.
            except OSError:
                pass  # It may have exited between wait and terminate.
            try:
                self.process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                w.fail("cleanup_unknown", "Owned launcher cleanup not proven; retain assignment.")
        joined = self.reader is None
        if not joined:
            try:
                if self.reader.ident is not None or self.reader.is_alive():
                    self.reader.join(timeout=2)
                    joined = not self.reader.is_alive()
            except RuntimeError:
                pass  # ident can be published before join becomes legal.
        if joined and self.process.stdout:
            self.process.stdout.close()
        return self._close_proof(w.plain_control_path(self.receipt))


class UnixWebSocket:
    shared = True
    def __init__(self, path, *, expected_hash=None):
        if os.name == "nt":
            w.fail("unsupported_shared_transport", "Unix shared transport is Linux-only.")
        path = Path(path)
        info = path.stat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            w.fail("untrusted_socket", "Native socket identity is not the current user.")
        for parent in path.parents:
            metadata = parent.stat()
            if parent.is_symlink() or metadata.st_mode & 0o022:
                w.fail("untrusted_socket", "Native socket has an externally writable ancestor.")
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(60)
        self.socket.connect(str(path))
        pid, uid, _ = struct.unpack("3i", self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != os.getuid() or expected_hash is None or w.file_hash(w.native_executable(os.readlink(f"/proc/{pid}/exe"))) != expected_hash.lower():
            self.socket.close()
            w.fail("daemon_identity_unknown", "Connected daemon peer is not the pinned native runtime/current user.")
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        self.socket.sendall(("GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + key + "\r\n\r\n").encode("ascii"))
        self.buffer = bytearray()
        while b"\r\n\r\n" not in self.buffer:
            part = self.socket.recv(4096)
            if not part:
                w.fail("native_eof", "Native channel closed during upgrade.")
            self.buffer.extend(part)
            if len(self.buffer) > 16384:
                w.fail("invalid_websocket", "Oversize WebSocket handshake.")
        raw, remaining = bytes(self.buffer).split(b"\r\n\r\n", 1)
        self.buffer = bytearray(remaining)
        lines = raw.decode("ascii").split("\r\n")
        headers = {}
        for line in lines[1:]:
            name, value = line.split(":", 1)
            name = name.lower()
            if name in headers:
                w.fail("invalid_websocket", "Duplicate WebSocket handshake header.")
            headers[name] = value.strip()
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()).decode("ascii")
        if (not lines[0].startswith("HTTP/1.1 101 ") or headers.get("upgrade", "").lower() != "websocket"
                or "upgrade" not in [x.strip().lower() for x in headers.get("connection", "").split(",")]
                or headers.get("sec-websocket-accept") != expected or "sec-websocket-extensions" in headers):
            w.fail("invalid_websocket", "Native WebSocket upgrade could not be verified.")

    def _bytes(self, count, until=None):
        while len(self.buffer) < count:
            if until is not None:
                remaining = until - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                self.socket.settimeout(remaining)
            raw = self.socket.recv(min(65536, count - len(self.buffer)))
            if not raw:
                w.fail("native_eof", "Shared native channel closed.")
            self.buffer.extend(raw)
        value = bytes(self.buffer[:count])
        del self.buffer[:count]
        return value

    def _send_frame(self, opcode, raw):
        size = len(raw)
        header = bytes([0x80 | opcode, 0x80 | (size if size < 126 else 126 if size < 65536 else 127)])
        if size >= 126:
            header += struct.pack("!H" if size < 65536 else "!Q", size)
        mask = os.urandom(4)
        self.socket.sendall(header + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(raw)))

    def send(self, value):
        self._send_frame(1, encode(value))

    def receive(self, timeout=60):
        self.socket.settimeout(timeout)
        raw, started = bytearray(), False
        until = time.monotonic() + timeout
        partial = False
        try:
            while True:
                first, second = self._bytes(2, until)
                partial = True
                fin, opcode = bool(first & 0x80), first & 15
                if first & 0x70 or second & 0x80:
                    w.fail("invalid_websocket", "Unsupported WebSocket flags.")
                size = second & 127
                if size in (126, 127):
                    size = struct.unpack("!H" if size == 126 else "!Q", self._bytes(2 if size == 126 else 8, until))[0]
                if size > LIMIT or len(raw) + size > LIMIT or (opcode >= 8 and (not fin or size > 125)):
                    w.fail("invalid_websocket", "Invalid WebSocket frame size/control.")
                part = self._bytes(size, until)
                partial = False
                if opcode == 9:
                    self._send_frame(10, part)
                    continue
                if opcode == 10:
                    continue
                if opcode == 8:
                    w.fail("native_eof", "Native WebSocket closed.")
                if (opcode == 1 and started) or (opcode == 0 and not started) or opcode not in (0, 1):
                    w.fail("invalid_websocket", "Invalid WebSocket continuation.")
                started = True
                raw.extend(part)
                if fin:
                    return decode(bytes(raw))
        except TimeoutError:
            if partial or started or self.buffer:
                w.fail("incomplete_native_frame", "Incomplete bounded native frame; outcome unknown, do not replay.")
            w.fail("native_inactivity", "Native WebSocket observation timed out; connection remains owned.")

    def close(self):
        try:
            self._send_frame(8, b"")
        except OSError:
            pass
        self.socket.close()
        return {"kind": "shared_connection_only", "daemon_signaled": False}


REASONING_PROGRESS = {"item/reasoning/summaryTextDelta", "item/reasoning/summaryPartAdded", "item/reasoning/textDelta"}
PUBLIC_PROGRESS = {"item/agentMessage/delta", "item/commandExecution/outputDelta", "item/fileChange/outputDelta",
                   "item/fileChange/patchUpdated", "item/plan/delta", "turn/plan/updated", "turn/diff/updated",
                   "item/autoApprovalReview/started", "item/autoApprovalReview/completed"}
TOOL_PROGRESS = {"item/commandExecution/outputDelta", "item/fileChange/outputDelta", "item/fileChange/patchUpdated"}


class RPC:
    def __init__(self, transport):
        self.transport, self.sequence, self.events = transport, 0, []
        self.call("initialize", {"clientInfo": {"name": "tokenband", "title": "TokenBand", "version": "1"},
                                 "capabilities": {"experimentalApi": True}})
        self.transport.send({"method": "initialized", "params": {}})

    def event(self, timeout=60):
        value = self.transport.receive(timeout)
        if "id" in value and "method" in value:
            self.transport.send({"id": value["id"], "error": {"code": -32601, "message": "Unsupported client action"}})
            w.fail("unsupported_client_action", "Native approval/client request requires its supported host bridge; no answer fabricated.")
        return value

    def call(self, method, params, *, deadline=None):
        if method not in METHODS:
            w.fail("unsupported_rpc", "Native RPC method is outside the reviewed lifecycle.")
        # Только observer metadata/control; не общий deadline модельной задачи.
        if deadline is not None:
            if (method not in OBSERVER_METHODS or type(deadline) not in (int, float)
                    or not math.isfinite(deadline)):
                w.fail("invalid_observer_deadline", "Deadline допустим только для конечного metadata/control наблюдения.")
            if time.monotonic() >= deadline:
                w.fail("native_inactivity", "Бюджет наблюдения исчерпан до отправки RPC.")
        self.sequence += 1
        if self.sequence > 2 ** 53 - 1:
            w.fail("native_rpc_error", "Native request identity bound exhausted.")
        request_id = self.sequence
        self.transport.send({"id": request_id, "method": method, "params": params})
        # A lost turn acceptance can already represent inference; do not kill it
        # at the metadata observation interval. Never resend the pending request.
        pending_turn = method == "turn/start"
        last_progress = time.monotonic()
        until = last_progress + (600 if pending_turn else 60)
        if deadline is not None:
            until = min(until, deadline)
        warned, diagnosed, pending_turn_id = False, False, None
        def check_silence():
            nonlocal warned, diagnosed
            age = time.monotonic() - last_progress
            observe = getattr(self, "observe", lambda value: None)
            if age >= 120 and not warned:
                observe({"stage": "warning", "pending_acceptance": True, "silence_seconds": int(age)})
                warned = True
            if age >= 300 and not diagnosed:
                process = getattr(self.transport, "process", None)
                observe({"stage": "diagnostics", "pending_acceptance": True,
                         "owner_alive": process is not None and process.poll() is None, "silence_seconds": int(age)})
                diagnosed = True
            if age >= 600:
                process = getattr(self.transport, "process", None)
                observe({"stage": "unknown_acceptance", "pending_acceptance": True,
                         "owner_alive": process is not None and process.poll() is None, "silence_seconds": int(age)})
                w.fail("native_acceptance_unknown", "Pending turn acknowledgement silent after ownership/state diagnostics; preserve unknown, never replay.")
        while True:
            # Housekeeping may keep the transport busy forever. Observe actual
            # substantive silence before every read, not only receive timeouts.
            if pending_turn:
                check_silence()
            elif time.monotonic() >= until:
                w.fail("native_inactivity", "Native RPC acknowledgement timed out.")
            try:
                remaining = until - time.monotonic()
                if deadline is not None and remaining <= 0:
                    w.fail("native_inactivity", "Бюджет наблюдения RPC исчерпан; исход отправленного запроса неизвестен.")
                value = self.event(min(60, remaining if deadline is not None else max(.01, remaining)))
            except w.WorkflowError as error:
                if error.code == "native_inactivity" and pending_turn:
                    check_silence()
                    continue
                raise
            if "id" not in value:
                if "error" in value or "result" in value:
                    w.fail("native_rpc_error", "Unmatched native response; payload suppressed.")
                event_name, payload = value.get("method", ""), value.get("params", {})
                matching = pending_turn and isinstance(payload, dict) and payload.get("threadId") == params.get("threadId")
                turn_record = payload.get("turn") if isinstance(payload, dict) else None
                event_turn = (payload.get("turnId") or (turn_record.get("id") if isinstance(turn_record, dict) else None)) if isinstance(payload, dict) else None
                if matching and isinstance(event_turn, str) and event_name in PUBLIC_PROGRESS | REASONING_PROGRESS | {"turn/started", "turn/completed", "item/started", "item/completed"}:
                    if pending_turn_id is None:
                        pending_turn_id = event_turn
                    matching = event_turn == pending_turn_id
                else:
                    matching = False
                if matching:
                    last_progress = time.monotonic()
                    until, warned, diagnosed = last_progress + 600, False, False
                if event_name in REASONING_PROGRESS:
                    continue
                if event_name in PUBLIC_PROGRESS and isinstance(payload, dict):
                    # Only identity/progress survives the acknowledgement queue;
                    # native tool output and incremental content are unnecessary.
                    value = {"method": event_name, "params": {key: payload[key] for key in ("threadId", "turnId", "itemId") if key in payload}}
                    self.events = [old for old in self.events if not (old.get("method") == event_name and old.get("params", {}).get("threadId") == payload.get("threadId") and old.get("params", {}).get("turnId") == event_turn)]
                if len(self.events) >= 256:
                    w.fail("event_overflow", "Too many pending native events.")
                self.events.append(value)
                continue
            if type(value["id"]) is not int or value["id"] != request_id:
                w.fail("native_rpc_error", "Unexpected native response identity; payload suppressed.")
            if "error" in value:
                error = value["error"]
                if ("result" in value or not isinstance(error, dict) or not {"code", "message"} <= error.keys()
                        or set(error) - {"code", "message", "data"} or type(error["code"]) is not int
                        or not -(2 ** 31) <= error["code"] < 2 ** 31 or not isinstance(error["message"], str)):
                    w.fail("native_rpc_error", "Malformed native rejection; payload suppressed.")
                raise NativeRPCError(method, request_id, error["code"])
            if not isinstance(value.get("result"), dict):
                w.fail("native_rpc_error", "Unexpected native response; payload suppressed.")
            if pending_turn and pending_turn_id is not None and value["result"].get("turn", {}).get("id") != pending_turn_id:
                w.fail("foreign_native_event", "Pending progress and acknowledged turn IDs differ; preserve unknown, never replay.")
            return value["result"]
        w.fail("native_inactivity", "Native RPC acknowledgement timed out.")

    def next_event(self, timeout=60):
        """Сначала сохранённая очередь; timeout ограничивает только новое чтение."""
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout < 0:
            w.fail("invalid_observer_timeout", "Timeout наблюдения должен быть конечным неотрицательным числом.")
        if self.events:
            return self.events.pop(0)
        if timeout == 0:
            w.fail("native_inactivity", "Нет накопленного события; бюджет нового чтения исчерпан.")
        return self.event(timeout)

    def close(self):
        return self.transport.close()
