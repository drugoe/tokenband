"""Owned, tool-free Claude print sessions. No automatic replay or raw event logs.

Qualification is protected host evidence, not evidence created by this module.
Native initialization and persistence are additionally checked on every connection.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
import uuid
import worker as w

LIMIT = 512 * 1024
REQUIRED_CHECKS = ("claude_print_stream_json", "claude_restricted", "claude_exact_resume_fails_missing",
    "claude_multi_turn_stream", "claude_interrupted_replay_disabled", "claude_customizations_disabled",
    "claude_native_retries_disabled")
ENVIRONMENT_NAMES = ("CLAUDE_CONFIG_DIR", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL", "CLAUDE_CODE_EFFORT_LEVEL",
    "CLAUDE_CODE_MAX_RETRIES", "CLAUDE_CODE_RETRY_WATCHDOG", "CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK",
    "CLAUDE_CODE_RESUME_INTERRUPTED_TURN", "CLAUDE_CODE_SKIP_PROMPT_HISTORY", "CLAUDE_CODE_PROCESS_WRAPPER",
    "CLAUDE_CODE_SHELL_PREFIX", "CLAUDE_CODE_PROJECT_DIR_NAME", "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_SAFE_MODE", "CLAUDE_CODE_SIMPLE",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "NODE_OPTIONS", "NODE_PATH", "LD_PRELOAD",
    "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "PATH")
AUTH_ENVIRONMENT_NAMES = {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"}
HOME_ENVIRONMENT_NAMES = {"HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "PATH"}
FORBIDDEN_ENVIRONMENT_NAMES = set(ENVIRONMENT_NAMES) - HOME_ENVIRONMENT_NAMES - {
    "CLAUDE_CONFIG_DIR", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_EFFORT_LEVEL", "CLAUDE_CODE_MAX_RETRIES",
    "CLAUDE_CODE_RETRY_WATCHDOG", "CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK",
    "CLAUDE_CODE_RESUME_INTERRUPTED_TURN", "CLAUDE_CODE_SKIP_PROMPT_HISTORY"}


def controlled_environment_name(name):
    return (name.upper() in ENVIRONMENT_NAMES or name.upper().startswith(("CLAUDE_", "ANTHROPIC_", "OTEL_",
        "AWS_", "AZURE_", "GOOGLE_", "GCLOUD_", "BEDROCK_", "VERTEX_", "FOUNDRY_", "CLOUD_ML_",
        "DYLD_", "LD_", "NODE_", "API_", "ENABLE_", "DISABLE_", "MAX_THINKING_"))
        or name.upper() in {"SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "TRACEPARENT", "TRACESTATE"})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, default=str, separators=(",", ":")).encode("utf-8")).hexdigest()


def bounded_text(value):
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > LIMIT or "\x00" in value:
        w.fail("invalid_native_text", "Native public text must be bounded UTF-8.")
    return value


def exact_uuid(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        w.fail("invalid_native_identity", "Native identity must be a full canonical UUID.")
    return value


class ClaudeDriver:
    capabilities = {"persistent_chat": True, "same_chat_resume": True, "send": True,
                    "native_tools": False, "live_steer": False, "execution_lifetime": "foreground"}

    def __init__(self, spec, expected, context, qualification, transport_factory=None):
        self.spec, self.expected, self.context, self.qualification = spec, expected, context, qualification
        if transport_factory is None:
            from native_transport import OwnedStdio
            transport_factory = OwnedStdio
        self.factory = transport_factory

    def _validate(self):
        q = self.qualification.get("claude", {})
        if (not isinstance(q, dict) or any(q.get(key) is not True for key in REQUIRED_CHECKS)
                or type(q.get("claude_init_before_input")) is not bool):
            w.fail("native_qualification_required", "Claude restricted stream lifecycle needs protected version qualification.")
        roots = self.context.get("_protection_roots", [])
        if not roots:
            w.fail("missing_parent_permissions", "Claude requires the trusted neutral protection context.")
        environment = self._environment(q, roots)
        for field, pin, expected in (("_settings", self.spec.get("settings_sha256"), {}),
                ("_mcp", q.get("claude_mcp_sha256"), {"mcpServers": {}})):
            path = w.protect_path(self.spec.get(field), roots)
            try:
                if path.stat().st_size > 131072 or not path.is_file():
                    raise ValueError()
                raw = path.read_bytes()
                value = json.loads(raw.decode("utf-8"), object_pairs_hook=w.json_pairs)
                if hashlib.sha256(raw).hexdigest() != pin or value != expected:
                    raise ValueError()
            except (OSError, ValueError, UnicodeError):
                w.fail("native_settings_changed", "Claude fixed empty settings or MCP configuration is unqualified or changed.")
        if any(not isinstance(self.expected.get(key), str) or not self.expected[key]
                or len(self.expected[key]) > 4096 for key in ("model", "effort", "native_provider", "cwd")):
            w.fail("invalid_native_config", "Claude requires a qualified exact model, effort, provider and working directory.")
        runtime = w.protect_path(self.spec.get("_runtime"), roots)
        if w.file_hash(runtime) != self.qualification.get("runtime_sha256"):
            w.fail("native_runtime_changed", "Claude runtime differs from protected qualification.")
        return digest({"spec": self.spec, "expected": self.expected, "context": self.context,
                       "qualification": self.qualification, "effective_environment": environment})

    def _environment(self, q, roots):
        qualified = q.get("claude_environment")
        if (not isinstance(qualified, dict) or set(qualified) != set(ENVIRONMENT_NAMES)
                or any(value is not None and (not isinstance(value, str) or len(value) > 65536 or "\x00" in value)
                       for value in qualified.values())):
            w.fail("native_qualification_required", "Claude needs a closed qualified nonsecret environment binding.")
        # Only inspect names of credential variables; their values belong to native auth.
        actual = {}
        names = tuple(os.environ)
        auth_names = sorted(name for name in names if name.upper() in AUTH_ENVIRONMENT_NAMES)
        qualified_auth = q.get("claude_auth_environment_names")
        if (not isinstance(qualified_auth, list)
                or any(not isinstance(name, str) or name not in AUTH_ENVIRONMENT_NAMES for name in qualified_auth)
                or qualified_auth != sorted(set(qualified_auth)) or auth_names != qualified_auth):
            w.fail("unsafe_native_environment", "Native credential source names differ from protected qualification; values were not inspected.")
        for name in names:
            upper = name.upper()
            if upper in AUTH_ENVIRONMENT_NAMES:
                continue
            if controlled_environment_name(name):
                if upper not in ENVIRONMENT_NAMES or (os.name != "nt" and name != upper) or upper in actual:
                    w.fail("unsafe_native_environment", "Unqualified Claude routing, customization, proxy or telemetry environment.")
                actual[upper] = os.environ[name]
        binding = {name: actual.get(name) for name in ENVIRONMENT_NAMES}
        if binding != qualified or any(binding[name] is not None for name in FORBIDDEN_ENVIRONMENT_NAMES):
            w.fail("unsafe_native_environment", "Effective Claude environment differs from its protected qualification.")
        if (binding["CLAUDE_CODE_MAX_RETRIES"] != "0" or binding["CLAUDE_CODE_RETRY_WATCHDOG"] not in (None, "0")
                or binding["CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK"] != "1"
                or binding["CLAUDE_CODE_RESUME_INTERRUPTED_TURN"] not in (None, "0")
                or binding["CLAUDE_CODE_SKIP_PROMPT_HISTORY"] not in (None, "0")
                or binding["CLAUDE_CODE_EFFORT_LEVEL"] not in (None, self.expected.get("effort"))
                or q.get("claude_effective_effort") != self.expected.get("effort")
                or q.get("claude_effective_native_provider") != self.expected.get("native_provider")):
            w.fail("unsafe_native_environment", "Claude effective effort, retry or persistence controls are unqualified.")
        endpoint = binding["ANTHROPIC_BASE_URL"]
        if endpoint is not None:
            try:
                parsed = urlsplit(endpoint)
                valid = (parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None
                    and parsed.password is None and not parsed.query and not parsed.fragment)
            except ValueError:
                valid = False
            if not valid:
                w.fail("unsafe_native_environment", "Claude qualified endpoint must be a credential-free HTTPS URL.")
        raw_home = w.lexical_path(binding["CLAUDE_CONFIG_DIR"] or Path.home() / ".claude", "Claude native home")
        home = w.protect_path(raw_home, roots)
        configured = w.protect_path(self.spec.get("_native_home", raw_home), roots)
        if home != configured or q.get("claude_effective_native_home") != str(home):
            w.fail("unsafe_native_environment", "Actual Claude auth/history home differs from protected qualification.")
        self._environment_names = names
        return binding

    def _launch(self, journal, resume):
        self._frozen(journal)
        binding = self._environment(self.qualification["claude"], self.context["_protection_roots"])
        return self.factory(self._argv(journal, resume), self.expected["cwd"], journal.connection_dir(),
                            environment_binding=binding, environment_names=self._environment_names)

    def _frozen(self, journal):
        current = self._validate()
        if journal.state.get("claude_snapshot") != current:
            w.fail("native_snapshot_changed", "Claude connection configuration differs from its frozen sprint.")
        exact_uuid(journal.state.get("thread_id"))

    def _argv(self, journal, resume):
        return [self.spec["_runtime"], "--restricted", "-p", "--input-format", "stream-json",
            "--output-format", "stream-json", "--verbose", "--resume" if resume else "--session-id",
            journal.state["thread_id"], "--model", self.expected["model"], "--effort", self.expected["effort"],
            "--name", journal.state["claude_title"], "--tools", "", "--disallowedTools", "mcp__*",
            "--strict-mcp-config", "--mcp-config", self.spec["_mcp"], "--setting-sources", "",
            "--settings", self.spec["_settings"], "--disable-slash-commands", "--permission-mode", "default",
            "--permission-prompts", "none"]

    def _identity(self, event, journal):
        from native_sprint import claude_identity
        claude_identity(event, journal.state["thread_id"], self.expected["model"])
        if (event.get("type") != "system" or event.get("subtype") != "init"
                or event.get("session_id") != journal.state["thread_id"] or event.get("model") != self.expected["model"]
                or event.get("tools") != [] or event.get("mcp_servers") != []
                or any(event.get(key, []) != [] for key in ("plugins", "skills", "agents"))
                or event.get("permissionMode") != "default"
                or not isinstance(event.get("cwd"), str)
                or Path(event["cwd"]).resolve() != Path(self.expected["cwd"]).resolve()):
            w.fail("native_identity_mismatch", "Claude initialization differs from exact tool-free session requirements.")
        journal.update(observed_model=event["model"], qualified_native_provider=self.expected["native_provider"],
                       configured_effort=self.expected["effort"], actual_serving_model="unknown")

    @staticmethod
    def _owner_state(process):
        try:
            return "running" if process.process.poll() is None else "exited"
        except (AttributeError, OSError):
            return "unconfirmed"

    def _receive(self, process, journal):
        started, warned, diagnosed = time.monotonic(), False, False
        while True:
            try:
                return process.receive(timeout=60)
            except w.WorkflowError as error:
                if error.code != "native_inactivity":
                    raise
            elapsed = time.monotonic() - started
            if elapsed >= 120 and not warned:
                journal.update(claude_observation={"stage": "warning", "silence_seconds": int(elapsed), "progress": "unconfirmed"})
                warned = True
            if elapsed >= 300 and not diagnosed:
                journal.update(claude_observation={"stage": "diagnostics", "silence_seconds": int(elapsed),
                    "owner": self._owner_state(process), "progress": "unconfirmed"})
                diagnosed = True
            if elapsed >= 600:
                # Drain an event that raced the timeout before checking this exact owned handle.
                try:
                    return process.receive(timeout=0)
                except w.WorkflowError as error:
                    if error.code != "native_inactivity":
                        raise
                state = self._owner_state(process)
                journal.update(claude_observation={"stage": "state_unconfirmed" if state == "unconfirmed" else "cancel_checked",
                    "silence_seconds": int(elapsed), "owner": state, "progress": "unconfirmed"})
                if state != "unconfirmed":
                    w.fail("native_silence_unknown", "Claude progress unconfirmed after state-checked silence threshold; operation remains unknown.")
                # A missing diagnostic is not authority to terminate an accepted owned turn.

    def _terminal(self, process, journal):
        while True:
            event = self._receive(process, journal)
            if not isinstance(event, dict) or event.get("session_id") != journal.state["thread_id"]:
                w.fail("native_identity_mismatch", "Claude event identity changed; event contents suppressed.")
            if event.get("type") == "system" and event.get("subtype") == "permission_denied":
                journal.update(last_turn_status="blocked")
                w.fail("native_turn_blocked", "Claude native permission denial blocks the turn; details suppressed.")
            if event.get("type") == "result":
                if (event.get("subtype") != "success" or event.get("is_error") is not False
                        or event.get("permission_denials") != []):
                    journal.update(last_turn_status="blocked")
                    w.fail("native_turn_blocked", "Claude turn did not produce a successful permission-free terminal result.")
                return {"session_id": journal.state["thread_id"], "turn_id": exact_uuid(event.get("uuid")),
                        "text": bounded_text(event.get("result")), "status": "completed"}
            if event.get("type") == "assistant":
                message = event.get("message", {})
                blocks = message.get("content") if isinstance(message, dict) else None
                if (event.get("parent_tool_use_id") is not None or not isinstance(blocks, list)
                        or any(not isinstance(b, dict) or b.get("type") not in ("text", "thinking", "redacted_thinking") for b in blocks)):
                    w.fail("native_tools_forbidden", "Claude emitted a tool or unsupported assistant event.")
                continue  # Never persist assistant reasoning, signatures or raw events.
            w.fail("unsupported_native_event", "Claude emitted an unsupported event; contents suppressed.")

    @staticmethod
    def _input(process, journal, text):
        process.send({"type": "user", "session_id": journal.state["thread_id"],
            "message": {"role": "user", "content": bounded_text(text)}, "parent_tool_use_id": None})

    def _first_turn(self, process, journal, text):
        before = self.qualification["claude"]["claude_init_before_input"]
        if before:
            self._identity(self._receive(process, journal), journal)
        self._input(process, journal, text)
        if not before:
            self._identity(self._receive(process, journal), journal)
        return self._terminal(process, journal)

    @staticmethod
    def _close(process, journal):
        try:
            proof = process.close()
            if not isinstance(proof, dict) or proof.get("empty") is not True:
                w.fail("cleanup_unknown", "Claude owned process cleanup is unconfirmed.")
            journal.update(owner_cleanup="confirmed")
        except Exception:
            journal.update(owner_cleanup="unknown", operation_status="unknown")
            raise

    def create(self, journal, brief):
        bounded_text(brief)
        snapshot = self._validate()
        if journal.state.get("thread_id") or journal.state.get("operation_status") in ("sending", "unknown"):
            w.fail("existing_native_assignment", "Claude sprint already has an identity or unresolved operation.")
        challenge = uuid.uuid4().hex + uuid.uuid4().hex
        readiness = "Readiness challenge: " + challenge + "\nRemember this challenge. Reply with exactly the challenge. Use no tools."
        persistence = "Persistence check: reply with exactly the readiness challenge from the previous turn. Use no tools."
        journal.update(thread_id=str(uuid.uuid4()), claude_snapshot=snapshot, claude_title=str(self.spec.get("title", "Sprint"))[:128],
            claude_challenge=challenge, claude_readiness=readiness, claude_persistence=persistence,
            claude_brief_sha256=digest(brief), backend_persistence="unconfirmed", client_visibility="pending",
            actual_serving_model="unknown", last_turn_status="pending", owner_cleanup="pending")
        process = None
        def ready():
            nonlocal process
            process = self._launch(journal, False)
            result = self._first_turn(process, journal, readiness)
            if result["text"] != challenge:
                w.fail("native_readiness_failed", "Claude did not confirm the frozen readiness challenge.")
            journal.record_ack(journal.state["active_operation"], {"initialization_turn_id": result["turn_id"]})
            journal.update(last_turn_status="completed")
            return result
        try:
            journal.perform("claude-readiness", {"text_sha256": digest(readiness)}, ready)
        finally:
            if process is not None:
                self._close(process, journal)
        return self._resume(journal, brief, "claude-assignment", initial=True)

    def _resume(self, journal, text, operation_id, initial=False):
        self._frozen(journal)
        if (journal.state.get("operation_status") != "complete" or journal.state.get("last_turn_status") != "completed"
                or journal.state.get("owner_cleanup") != "confirmed"):
            w.fail("native_operation_unresolved", "Claude resume requires a terminal turn and confirmed owned cleanup.")
        if not isinstance(operation_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", operation_id):
            w.fail("invalid_operation_id", "Claude operation identifier is invalid.")
        journal.reserve_logical(operation_id, digest(text))
        journal.update(owner_cleanup="pending")
        process = None
        def persistence():
            nonlocal process
            process = self._launch(journal, True)
            result = self._first_turn(process, journal, journal.state["claude_persistence"])
            if result["text"] != journal.state["claude_challenge"]:
                w.fail("native_persistence_unconfirmed", "Claude exact resumed context could not be verified.")
            journal.update(backend_persistence="confirmed", last_turn_status="completed")
            return result
        def assignment():
            self._input(process, journal, text)
            result = self._terminal(process, journal)
            journal.record_ack(journal.state["active_operation"], {"assignment_turn_id": result["turn_id"]})
            journal.update(last_turn_status="completed")
            return result
        try:
            journal.perform(operation_id + "-persistence", {"text_sha256": digest(journal.state["claude_persistence"])}, persistence)
            return journal.perform(operation_id, {"text_sha256": digest(text)}, assignment)
        finally:
            if process is not None:
                self._close(process, journal)

    def send(self, journal, text, operation_id):
        bounded_text(text)
        return self._resume(journal, text, operation_id)

    def status(self, journal):
        self._frozen(journal)
        return {key: journal.state.get(key, "unknown") for key in ("thread_id", "operation_status", "last_turn_status",
            "backend_persistence", "client_visibility", "actual_serving_model", "owner_cleanup")}

    def steer(self, *args, **kwargs):
        w.fail("unsupported_native_operation", "Claude restricted print sessions do not support live steering.")

    def interrupt(self, *args, **kwargs):
        w.fail("unsupported_native_operation", "Claude restricted print sessions do not expose live interruption.")
