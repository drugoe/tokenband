"""Reviewed-shape Codex 0.160 native persistent lifecycle, stdlib only."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import worker as w
from native_sprint import check_identity, digest, require_legacy_unit
from native_transport import OwnedStdio, RPC, UnixWebSocket, NativeRPCError, PUBLIC_PROGRESS, REASONING_PROGRESS, TOOL_PROGRESS

DISABLED = {"hooks", "plugins", "apps", "browser_use", "browser_use_external", "browser_use_full_cdp_access",
            "computer_use", "image_generation", "remote_plugin", "skill_mcp_dependency_install", "js_repl",
            "code_mode_host", "api_key_model_discovery", "auth_elicitation", "multi_agent", "tool_suggest", "view_image",
            "multi_agent_v2", "request_permissions_tool", "code_mode"}
TOOL_ENV = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "USERPROFILE", "HOMEDRIVE",
            "HOMEPATH", "COMSPEC", "PSMODULEPATH", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "HOME", "LANG", "LC_ALL"}
# Bounded closed vocabulary of pre-allocation reasons recorded for an auto -> owned choice.
SHARED_BLOCK_REASONS = frozenset({
    "shared_daemon_discovery_unavailable", "shared_daemon_unqualified", "shared_daemon_version_mismatch",
    "shared_daemon_not_running", "shared_daemon_advertisement_incomplete", "shared_daemon_runtime_missing"})
NETWORK_NULL_DEFAULTS = {"proxy_url", "enable_socks5", "socks_url", "enable_socks5_udp", "allow_upstream_proxy",
                        "dangerously_allow_non_loopback_proxy", "dangerously_allow_all_unix_sockets", "mode",
                        "domains", "unix_sockets", "allow_local_binding", "mitm"}


def shared_unix_host():
    """Exactly a Linux host may address a Unix shared socket; os.name alone is not Linux."""
    return os.name == "posix" and sys.platform.startswith("linux")


def normalized_profile(value):
    """Only documented 0.160 null defaults may be absent in generated TOML."""
    if not isinstance(value, dict):
        return value
    result = dict(value)
    for key in ("description", "workspace_roots"):
        if result.get(key, False) is None:
            del result[key]
    for field, allowed in (("filesystem", {"glob_scan_max_depth"}), ("network", NETWORK_NULL_DEFAULTS)):
        if isinstance(result.get(field), dict):
            result[field] = {key: item for key, item in result[field].items() if key not in allowed or item is not None}
    return result


def toml(value):
    """Closed value encoder; no key/argv content is supplied by the task model."""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if isinstance(value, list):
        return "[" + ",".join(toml(x) for x in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(toml(str(k)) + "=" + toml(v) for k, v in value.items()) + "}"
    w.fail("invalid_native_value", "Unsupported generated native configuration value.")


def error_observation(value):
    """Closed v2 error metadata only; never extract free-form error contents."""
    message = "Native error notification is malformed; contents suppressed."
    error, retry = value.get("error"), value.get("willRetry")
    if not isinstance(error, dict) or type(retry) is not bool:
        w.fail("invalid_native_event", message)
    info = error.get("codexErrorInfo")
    if info is None:
        variant = "UNKNOWN"
    elif isinstance(info, str):
        if info not in {"contextWindowExceeded", "sessionBudgetExceeded", "usageLimitExceeded", "rateLimitExceeded",
                        "flexUnavailable", "serverOverloaded", "cyberPolicy", "misalignmentPolicyViolation",
                        "tooManyDenials", "internalServerError", "unauthorized", "badRequest", "threadRollbackFailed",
                        "sandboxError", "other"}:
            w.fail("invalid_native_event", message)
        variant = info
    elif isinstance(info, dict) and len(info) == 1:
        variant, fields = next(iter(info.items()))
        if not isinstance(fields, dict):
            w.fail("invalid_native_event", message)
        if variant in {"httpConnectionFailed", "responseStreamConnectionFailed", "responseStreamDisconnected",
                       "responseTooManyFailedAttempts"}:
            if set(fields) - {"httpStatusCode"}:
                w.fail("invalid_native_event", message)
            status = fields.get("httpStatusCode")
            if status is not None and (type(status) is not int or not 0 <= status <= 65535):
                w.fail("invalid_native_event", message)
        elif variant == "activeTurnNotSteerable":
            if (set(fields) != {"turnKind"} or not isinstance(fields["turnKind"], str)
                    or fields["turnKind"] not in {"review", "compact"}):
                w.fail("invalid_native_event", message)
        else:
            w.fail("invalid_native_event", message)
    else:
        w.fail("invalid_native_event", message)
    return {"stage": "native_error", "willRetry": retry, "codexErrorInfo": variant}


def tool_temp_context_matches(context):
    actual = {str(Path(os.environ[k]).resolve()) for k in ("TMP", "TEMP", "TMPDIR") if os.environ.get(k)}
    if os.name != "nt" and Path("/tmp").exists():
        actual.add(str(Path("/tmp").resolve()))
    roots = context["temp_roots"] + (context["writable_roots"] if context.get("schema") == 2 else [])
    return all(any(w.is_within(Path(path), Path(root)) for root in roots) for path in actual)


def profiles(context, private, native_home):
    if context.get("schema") == 2:
        actual = w.actual_permissions(context["task_permissions"], context["network"])
        if not actual["network"]["enabled"]:
            w.fail("unsupported_permission_contract", "The direct full-access builtin bridge does not implement network-disabled grants.")
        return {stage: ":danger-full-access" for stage in ("init", "task")}
    denied = {str(Path(x).resolve()) for x in context["deny_read_paths"]}
    denied.update(str(Path(x).resolve()) for x in private)
    denied.add(str(Path(native_home).resolve()))
    definitions = {}
    for stage, extends in (("init", ":read-only"), ("task", ":workspace")):
        fs = {":root": "deny", ":minimal": "read", ":tmpdir": "deny", ":slash_tmp": "deny"}
        for path in context["read_roots"]:
            fs[path] = "read"
        if stage == "task":
            for path in context["writable_roots"] + context["temp_roots"]:
                fs[path] = "write"
                for name in context["protected_names"]:
                    fs[str(Path(path) / name)] = "read"
        for path in denied:
            # No parent read/write carve-out may reopen an auth/control subtree.
            for grant in list(fs):
                if grant.startswith(":"):
                    continue
                if w.is_within(Path(grant), Path(path)):
                    del fs[grant]
            fs[path] = "deny"
        definitions[stage] = {"extends": extends, "filesystem": fs, "network": {"enabled": False}}
    return definitions


def profile_names(context, spec, definitions):
    """Builtin references are native IDs; schema1 retains its alias grammar."""
    if context.get("schema") == 2:
        for field in ("initialization_profile", "execution_profile"):
            if field in spec and spec[field] != ":danger-full-access":
                w.fail("unsupported_permission_contract", "Schema2 direct builtin selection cannot use custom profile aliases.")
        return dict(definitions)
    names = {stage: spec.get("initialization_profile" if stage == "init" else "execution_profile",
                            "workflow_" + stage + "_" + digest(definitions[stage])[:16]) for stage in ("init", "task")}
    for name in names.values():
        w.identifier(name, "permission profile")
    return names


def terminal_observation(event, *, thread_id, turn_id):
    """Безопасное свидетельство exact terminal; не cleanup и не приёмка ответа."""
    w.identifier(thread_id, "expected native thread")
    w.identifier(turn_id, "expected native turn")
    if not isinstance(event, dict):
        w.fail("native_rpc_error", "Некорректная форма native события; payload скрыт.")
    if event.get("method") != "turn/completed":
        return None
    value = event.get("params")
    if not isinstance(value, dict):
        w.fail("native_rpc_error", "Некорректная форма terminal; payload скрыт.")
    turn = value.get("turn")
    if (value.get("threadId") != thread_id or not isinstance(turn, dict)
            or turn.get("id") != turn_id or ("turnId" in value and value["turnId"] != turn_id)):
        w.fail("foreign_native_event", "Terminal не подтверждает исходный exact thread/turn.")
    status = turn.get("status")
    if status not in ("completed", "failed", "interrupted"):
        w.fail("native_rpc_error", "Terminal содержит неподдерживаемый status; payload скрыт.")
    return {"thread_id": thread_id, "turn_id": turn_id, "status": status}


class CodexDriver:
    def __init__(self, spec, expected, context, qualification, transport_factory=None):
        self.spec, self.expected, self.context, self.qualification = spec, expected, context, qualification
        self.factory = transport_factory
        if context.get("schema") == 2:
            w.actual_approval(context.get("approval"))
            w.actual_permissions(context.get("task_permissions"), context.get("network"))
        elif context.get("approval") != {"system": "codex", "policy": "on-request", "reviewer": "auto_review"}:
            w.fail("unsupported_permission_contract", "Actual parent Codex approval route must be preserved.")
        self.native_home = spec.get("_native_home", os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        actual_home = w.lexical_path(os.environ.get("CODEX_HOME", Path.home() / ".codex"), "Effective native home")
        configured_home = w.lexical_path(spec.get("_raw_native_home", self.native_home), "Configured native home")
        if actual_home != configured_home or actual_home.resolve() != configured_home.resolve():
            w.fail("native_home_mismatch", "Configured native home differs from actual inherited native home.")
        self.environment_binding = {name: os.environ.get(name) for name in TOOL_ENV | {"CODEX_HOME", "OPENAI_BASE_URL", "CODEX_OSS_BASE_URL", "CODEX_OSS_PORT"}}
        if any(self.environment_binding[name] for name in ("OPENAI_BASE_URL", "CODEX_OSS_BASE_URL", "CODEX_OSS_PORT")):
            w.fail("unqualified_native_environment", "Ambient native provider routing overrides are not qualified.")
        self.shared_socket = None
        self.shared_block_reason = None
        self.chosen = None

    def _prepare(self, journal):
        if any(os.environ.get(name) != value for name, value in self.environment_binding.items()):
            w.fail("native_environment_changed", "Native home/routing/tool environment changed; values suppressed.")
        self.definitions = profiles(self.context, [journal.directory.parent.parent], self.native_home)
        self.names = profile_names(self.context, self.spec, self.definitions)
        self.overrides = {"model": self.expected["model"], "model_provider": self.expected["native_provider"],
                          "model_reasoning_effort": self.expected["effort"], "approval_policy": self.context["approval"]["policy"],
                          "web_search": "disabled", "shell_environment_policy.inherit": "core",
                          "shell_environment_policy.ignore_default_excludes": False, "notify": [], "analytics.enabled": False}
        if "native_model_catalog" in self.spec:
            catalog = self.spec.get("_native_model_catalog")
            if not isinstance(catalog, dict) or not isinstance(catalog.get("canonical"), str):
                w.fail("invalid_model_catalog", "Native model catalog requires its protected preflight pin.")
            self.overrides["model_catalog_json"] = catalog["canonical"]
        if self.context["approval"]["reviewer"] is not None:
            self.overrides["approvals_reviewer"] = self.context["approval"]["reviewer"]
        self.overrides["shell_environment_policy.filters"] = {name: "include" for name in sorted(TOOL_ENV)}
        # Exact tool temp environment must be retained and qualified, never cwd-only.
        if not tool_temp_context_matches(self.context):
            w.fail("temp_context_mismatch", "Context omits actual native tool temporary roots.")
        if self.context.get("schema") == 2:
            self.overrides["permission_profile"] = self.names["init"]
        else:
            self.overrides["default_permissions"] = self.names["init"]
            for stage in ("init", "task"):
                self.overrides["permissions." + self.names[stage]] = self.definitions[stage]
        provider = self.expected["native_provider"]
        self.overrides["model_providers." + provider + ".request_max_retries"] = 0
        self.overrides["model_providers." + provider + ".stream_max_retries"] = 0
        for server in self.spec.get("disabled_mcp_servers", []):
            self.overrides["mcp_servers." + server + ".enabled"] = False
        for feature in DISABLED:
            self.overrides["features." + feature] = False
        if os.name == "nt" and self.context.get("schema") != 2:
            self.overrides["windows.sandbox"] = "elevated"
        # Integrations/settings are discovered through config/read before turns.
        if self.chosen is None:
            requested = self.spec["connection"]
            if requested == "shared-unix" and not shared_unix_host():
                w.fail("unsupported_shared_transport", "Explicit shared Unix socket transport is unavailable on this host.")
            if self._unresolved_operation(journal):
                # Selection is a pre-allocation decision, so it applies to every route
                # branch: explicit owned, the factory seam and auto/shared alike. A
                # retained accepted, unknown or live operation is never re-routed as
                # recovery and never receives a new owner: a fresh OwnedStdio would be a
                # new owning process even when the route name is unchanged. Only the
                # exactly known original shared owner is preserved, and only while its
                # daemon is still qualified; an owned, cached-without-handle or unbound
                # original fails closed before any transport constructor.
                retained = None
                if (requested in {"auto", "shared-unix"} and shared_unix_host()
                        and self._retained_route(journal) == "shared-unix"):
                    self._discover_shared()
                    retained = "shared-unix" if self.shared_socket else None
                if retained is None:
                    w.fail("native_reconciliation_required",
                           "Existing accepted/unknown/live operation keeps its original route or lacks an exact original binding; reconcile before any new route.")
                self.chosen = retained
            elif self.factory:
                self.chosen = "owned-stdio"
            elif requested in {"auto", "shared-unix"} and shared_unix_host():
                self._discover_shared()
                if self.shared_socket:
                    self.chosen = "shared-unix"
                elif requested == "shared-unix":
                    w.fail("shared_unavailable", "No qualified local shared daemon; owned stdio can be selected before creation.")
                else:
                    self.chosen = "owned-stdio"
                    if self.shared_block_reason is not None:
                        journal.update(native_route={"route": "owned-stdio", "reason": self.shared_block_reason})
            else:
                self.chosen = "owned-stdio"

    def _unresolved_operation(self, journal):
        """True when this journal already holds an in-flight, accepted or unknown operation."""
        state = getattr(journal, "state", None)
        if not isinstance(state, dict):
            return False
        return (state.get("active_operation") is not None
                or state.get("operation_status") == "unknown"
                or state.get("migration_status") is not None)

    def _retained_route(self, journal):
        """Exact original route recorded for existing accepted/unknown work, else None."""
        state = getattr(journal, "state", None)
        lifetime = state.get("execution_lifetime") if isinstance(state, dict) else None
        return {"daemon": "shared-unix", "foreground": "owned-stdio"}.get(lifetime)

    def _retained_shared_live(self, journal):
        """True only for an exactly known shared-unix original whose daemon is still
        qualified; a cached owned route name is never treated as a live owner."""
        if self.chosen != "shared-unix" or not shared_unix_host():
            return False
        if self._retained_route(journal) != "shared-unix":
            return False
        self._discover_shared()
        return self.shared_socket is not None and self.shared_block_reason is None

    @staticmethod
    def _bounded_absolute_path(value, limit):
        return (isinstance(value, str) and bool(value) and len(value) <= limit
                and not any(ord(char) < 32 or ord(char) == 127 for char in value)
                and Path(value).is_absolute())

    def _discover_shared(self):
        self.shared_block_reason = None
        result = subprocess.run([self.spec["_runtime"], "app-server", "daemon", "version"],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=15, shell=False)
        if result.returncode != 0:
            self.shared_block_reason = "shared_daemon_discovery_unavailable"
            return
        if len(result.stdout) > 16384:
            w.fail("daemon_identity_unknown", "Oversize daemon discovery output.")
        try:
            value = json.loads(result.stdout)
        except ValueError:
            w.fail("daemon_identity_unknown", "Daemon metadata invalid; no transport fallback after ambiguity.")
        if not isinstance(value, dict):
            w.fail("daemon_identity_unknown", "Daemon metadata is not an object; no transport fallback after ambiguity.")
        for field in ("cliVersion", "appServerVersion", "status"):
            if field in value and not isinstance(value[field], str):
                w.fail("daemon_identity_unknown", "Daemon metadata field is not a bounded string.")
        advertised, socket_path = value.get("managedCodexPath"), value.get("socketPath")
        # Every present path field is shape-checked before any known-unqualified or
        # known-missing return, so malformed discovery can never become a permitted
        # alternative. A missing or empty advertised runtime stays a known incompatibility.
        if advertised is not None and advertised != "" and not self._bounded_absolute_path(advertised, 32768):
            w.fail("daemon_identity_unknown", "Advertised native runtime path is malformed; no transport fallback after ambiguity.")
        # A present socketPath is validated even when its value is null: only
        # managedCodexPath has the documented nullable/empty form, and an absent
        # socketPath is a different fact from a present one.
        if "socketPath" in value and not self._bounded_absolute_path(socket_path, 4096):
            w.fail("daemon_identity_unknown", "Daemon socket path is malformed; no transport fallback after ambiguity.")
        # Qualified versioned discovery shape is part of the pinned protocol evidence.
        expected = self.qualification.get("checks", {}).get("shared_daemon")
        if self.context.get("schema") != 2 and not expected:
            self.shared_block_reason = "shared_daemon_unqualified"
            return
        if value.get("cliVersion") != self.spec["version"] or value.get("appServerVersion") != self.spec["version"]:
            self.shared_block_reason = "shared_daemon_version_mismatch"
            return
        if value.get("status") != "running":
            self.shared_block_reason = "shared_daemon_not_running"
            return
        if advertised is None or advertised == "":
            # Known pre-allocation incompatibility: the shared route is simply unselectable.
            self.shared_block_reason = "shared_daemon_advertisement_incomplete"
            return
        try:
            # Only a specifically proven missing file is a known incompatibility; the
            # broad worker missing_path also wraps permission/loop errors and must not
            # be treated as proof of absence.
            resolved = Path(advertised).resolve(strict=True)
        except FileNotFoundError:
            self.shared_block_reason = "shared_daemon_runtime_missing"
            return
        except (OSError, RuntimeError):
            w.fail("daemon_identity_unknown", "Advertised native runtime path could not be resolved.")
        try:
            image = w.native_executable(resolved)
            digest = w.file_hash(image)
        except w.WorkflowError:
            w.fail("daemon_identity_unknown", "Shared daemon runtime bytes not independently established.")
        if digest != self.spec["sha256"].lower():
            w.fail("daemon_identity_unknown", "Shared daemon runtime bytes not independently established.")
        self.shared_socket = socket_path
        if not isinstance(self.shared_socket, str) or not Path(self.shared_socket).is_absolute():
            w.fail("daemon_identity_unknown", "Daemon socket path unavailable.")

    def _open(self, journal):
        self._prepare(journal)
        if journal.guard:
            journal.guard()
        if self._unresolved_operation(journal) and not self._retained_shared_live(journal):
            # self.chosen is a cached route name, not a live owned/RPC handle, and _open
            # always builds a NEW transport (new connection_dir + new OwnedStdio/factory).
            # A retained accepted/unknown/live operation never receives a new owner: only
            # the exactly known shared owner may be reconnected while still qualified;
            # owned/unbound/cached-without-handle fails closed before any constructor.
            w.fail("native_reconciliation_required",
                   "Retained accepted/unknown/live operation lacks an exact live owner; reconcile before opening any new transport.")
        if self.chosen == "shared-unix":
            transport = UnixWebSocket(self.shared_socket, expected_hash=self.spec["sha256"])
        else:
            argv = [self.spec["_runtime"], "app-server", "--stdio", "--strict-config"]
            for key, value in self.overrides.items():
                # Native -c parses simple dotted keys, not quoted segments.
                # MCP names were restricted to simple identifiers at setup.
                argv.extend(["-c", key + "=" + toml(value)])
            factory = self.factory or OwnedStdio
            transport = factory(argv, self.expected["cwd"], journal.connection_dir(), environment_binding=self.environment_binding)
        rpc = None
        try:
            rpc = RPC(transport)
            rpc.observe = lambda value: journal.update(observation=value)
            self._check_config(rpc)
            return rpc
        except BaseException:
            if rpc is None:
                # initialize itself can fail after a child exists. It has the
                # same cleanup obligation as every later protocol failure.
                try:
                    journal.update(cleanup=transport.close(), execution_lifetime="daemon" if transport.shared else "foreground")
                except BaseException:
                    journal.update(owner_cleanup="unknown")
                    raise
            else:
                self._close(rpc, journal)
            raise

    def _check_config(self, rpc):
        response = rpc.call("config/read", {"cwd": self.expected["cwd"], "includeLayers": False})
        config = response.get("config")
        if not isinstance(config, dict):
            w.fail("native_config_mismatch", "Native effective configuration unavailable.")
        if "native_model_catalog" in self.spec:
            reference = config.get("model_catalog_json")
            if reference is not None and reference != self.overrides["model_catalog_json"]:
                w.fail("native_catalog_mismatch", "Native visible model catalog reference conflicts with the protected pin.")
            # Reference visibility does not prove a loaded catalog or file-tool use.
            self.model_catalog_reference = "NOT_EXPOSED_UNKNOWN" if reference is None else "MATCH_VISIBLE_REFERENCE"
        for key in ("model", "model_provider", "model_reasoning_effort", "approval_policy", "web_search", *(["approvals_reviewer"] if self.context["approval"]["policy"] != "never" or self.context.get("schema") != 2 else [])):
            if config.get(key) != self.overrides[key]:
                w.fail("native_config_mismatch", "Native effective role/approval restrictions changed.")
        if config.get("sandbox_mode") is not None or config.get("sandbox_workspace_write") is not None:
            w.fail("legacy_sandbox_conflict", "Legacy sandbox would discard named deny-read profiles.")
        if self.context.get("schema") == 2:
            # 0.160 accepts this explicit selector while serializing it as null.
            # A catalog entry alone is not effective tool-grant qualification.
            if (self.names != {"init": ":danger-full-access", "task": ":danger-full-access"}
                    or self.definitions != self.names
                    or self.overrides.get("permission_profile") != ":danger-full-access"
                    or any(key == "default_permissions" or key.startswith("permissions.") for key in self.overrides)
                    or any(config.get(key) is not None and config[key] != ":danger-full-access"
                           for key in ("permission_profile", "default_permissions"))):
                w.fail("native_permission_mismatch", "Explicit native builtin selection or returned effective selector differs.")
            permissions = config.get("permissions")
            if permissions is not None and (not isinstance(permissions, dict) or ":danger-full-access" in permissions):
                w.fail("native_permission_mismatch", "Native builtin selection cannot be replaced by a custom definition.")
        else:
            for stage, name in self.names.items():
                if normalized_profile(config.get("permissions", {}).get(name)) != self.definitions[stage]:
                    w.fail("native_permission_mismatch", "Native named initialization/task roots and secret denies do not match.")
        provider = config.get("model_providers", {}).get(self.expected["native_provider"], {})
        if (provider.get("base_url") != self.spec.get("native_base_url")
                or provider.get("wire_api") != self.spec.get("native_wire_api")):
            w.fail("native_provider_mismatch", "Native effective provider endpoint/wire differs from the exact protected pins.")
        if provider.get("request_max_retries") != 0 or provider.get("stream_max_retries") != 0:
            w.fail("native_retry_mismatch", "Opaque native request/stream retries must be disabled.")
        if config.get("notify") or any(row.get("enabled", True) for row in config.get("mcp_servers", {}).values()):
            w.fail("native_integration_mismatch", "Unqualified native notification/MCP integration enabled.")
        if any(config.get("features", {}).get(feature) is not False for feature in DISABLED):
            w.fail("native_integration_mismatch", "Unqualified native tools/integrations are enabled.")
        shell = config.get("shell_environment_policy", {})
        shell_set = shell.get("set")
        if shell_set is None:
            shell_set = {}
        if (shell.get("inherit") != "core" or shell.get("ignore_default_excludes") is not False
                or not isinstance(shell_set, dict) or any(shell_set.values())):
            w.fail("tool_environment_mismatch", "Native tool environment could expose inherited auth/config.")
        if shell.get("filters") != {name: "include" for name in sorted(TOOL_ENV)}:
            w.fail("tool_environment_mismatch", "Native shell environment filters do not match the closed nonsecret allowlist.")
        admitted = rpc.call("permissionProfile/list", {"cwd": self.expected["cwd"]})
        rows = admitted.get("data", admitted.get("profiles", []))
        if not isinstance(rows, list) or not set(self.names.values()) <= {row.get("id") for row in rows if isinstance(row, dict) and row.get("allowed") is True}:
            w.fail("native_profile_unavailable", "Native runtime did not admit both named profiles.")
        if os.name == "nt" and self.context.get("schema") != 2:
            readiness = rpc.call("windowsSandbox/readiness", {})
            if readiness.get("status") != "ready":
                w.fail("native_sandbox_unready", "Native Windows sandbox is not ready; no automatic installation/elevation.")

    def _close(self, rpc, journal):
        proof = rpc.close()
        journal.update(cleanup=proof, execution_lifetime="daemon" if rpc.transport.shared else "foreground")
        if journal.guard:
            journal.guard()

    def _approval_params(self):
        # Schema1 retains its historical method contract; schema2 never falls back.
        approval = self.context["approval"] if self.context.get("schema") == 2 else {"policy": "on-request", "reviewer": "auto_review"}
        result = {"approvalPolicy": approval["policy"]}
        if approval["reviewer"] is not None:
            result["approvalsReviewer"] = approval["reviewer"]
        return result

    def _profile_params(self, stage):
        return {"model": self.expected["model"], "modelProvider": self.expected["native_provider"], "cwd": self.expected["cwd"],
                "config": {"model_reasoning_effort": self.expected["effort"]}, "permissions": self.names[stage],
                "runtimeWorkspaceRoots": self.context["writable_roots"], **self._approval_params()}

    def _thread(self, rpc, journal, resume=False):
        params = self._profile_params("task" if resume else "init")
        if resume:
            params.update(threadId=journal.state["thread_id"], excludeTurns=True)
        else:
            params.update(ephemeral=False, allowProviderModelFallback=False)
        response = rpc.call("thread/resume" if resume else "thread/start", params)
        thread = response.get("thread", {})
        thread_id = thread.get("id")
        w.identifier(thread_id, "native thread")
        if resume and thread_id != journal.state["thread_id"]:
            w.fail("native_chat_changed", "Native resume returned another thread.")
        # Persist ID before ANY further native call, including profile validation.
        journal.record_ack(journal.state["active_operation"], {"thread_id": thread_id})
        observed = check_identity(response, self.expected, self.names["task" if resume else "init"], self.context["approval"] if self.context.get("schema") == 2 else None)
        returned_roots = response.get("runtimeWorkspaceRoots")
        if (not isinstance(returned_roots, list) or any(not isinstance(x, str) for x in returned_roots)
                or {str(Path(x).resolve()) for x in returned_roots} != set(self.context["writable_roots"])):
            w.fail("native_root_mismatch", "Returned native workspace roots differ from the trusted complete parent roots.")
        journal.update(observed_native_profile=observed)
        return {"thread_id": thread_id, "observed": observed}

    def _connection_notice(self, method, value):
        """Closed connection metadata, discarded without progress or persistence."""
        if method not in {"configWarning", "remoteControl/status/changed", "account/rateLimits/updated"}:
            return False
        message = "Native connection notice is malformed; contents suppressed."
        if not isinstance(value, dict):
            w.fail("invalid_native_event", message)
        if method == "configWarning":
            if (not {"summary", "details"} <= value.keys() or set(value) - {"summary", "details", "path", "range"}
                    or not isinstance(value["summary"], str)
                    or (value["details"] is not None and not isinstance(value["details"], str))
                    or (value.get("path") is not None and not isinstance(value["path"], str))):
                w.fail("invalid_native_event", message)
            span = value.get("range")
            if span is not None:
                if not isinstance(span, dict) or set(span) != {"start", "end"}:
                    w.fail("invalid_native_event", message)
                for position in span.values():
                    if (not isinstance(position, dict) or set(position) != {"line", "column"}
                            or any(type(coordinate) is not int or not 1 <= coordinate <= 2 ** 64 - 1
                                   for coordinate in position.values())):
                        w.fail("invalid_native_event", message)
        elif method == "account/rateLimits/updated":
            if set(value) != {"rateLimits"} or not isinstance(value["rateLimits"], dict):
                w.fail("invalid_native_event", message)
            snapshot = value["rateLimits"]
            if set(snapshot) - {"limitId", "limitName", "normalModelSlug", "primary", "secondary", "credits",
                                "individualLimit", "spendControlReached", "planType", "rateLimitReachedType"}:
                w.fail("invalid_native_event", message)
            def signed(number, bits):
                return type(number) is int and -(2 ** (bits - 1)) <= number <= 2 ** (bits - 1) - 1
            for name in ("limitId", "limitName", "normalModelSlug", "planType"):
                if snapshot.get(name) is not None and not isinstance(snapshot[name], str):
                    w.fail("invalid_native_event", message)
            if snapshot.get("spendControlReached") is not None and type(snapshot["spendControlReached"]) is not bool:
                w.fail("invalid_native_event", message)
            reached = snapshot.get("rateLimitReachedType")
            if reached is not None and (not isinstance(reached, str) or reached not in {
                    "rate_limit_reached", "workspace_owner_credits_depleted", "workspace_member_credits_depleted",
                    "workspace_owner_usage_limit_reached", "workspace_member_usage_limit_reached"}):
                w.fail("invalid_native_event", message)
            for name in ("primary", "secondary"):
                window = snapshot.get(name)
                if window is None:
                    continue
                if (not isinstance(window, dict) or "usedPercent" not in window
                        or set(window) - {"usedPercent", "windowDurationMins", "resetsAt"}
                        or not signed(window["usedPercent"], 32)):
                    w.fail("invalid_native_event", message)
                for field in ("windowDurationMins", "resetsAt"):
                    if window.get(field) is not None and not signed(window[field], 64):
                        w.fail("invalid_native_event", message)
            credits = snapshot.get("credits")
            if credits is not None:
                if (not isinstance(credits, dict) or not {"hasCredits", "unlimited"} <= credits.keys()
                        or set(credits) - {"hasCredits", "unlimited", "balance"}
                        or type(credits["hasCredits"]) is not bool or type(credits["unlimited"]) is not bool
                        or (credits.get("balance") is not None and not isinstance(credits["balance"], str))):
                    w.fail("invalid_native_event", message)
            individual = snapshot.get("individualLimit")
            if individual is not None:
                if (not isinstance(individual, dict) or set(individual) != {"limit", "used", "remainingPercent", "resetsAt"}
                        or not isinstance(individual["limit"], str) or not isinstance(individual["used"], str)
                        or not signed(individual["remainingPercent"], 32) or not signed(individual["resetsAt"], 64)):
                    w.fail("invalid_native_event", message)
        elif (set(value) != {"status", "serverName", "installationId", "environmentId"}
                or not isinstance(value["status"], str) or value["status"] not in {"disabled", "connecting", "connected", "errored"}
                or not isinstance(value["serverName"], str) or not isinstance(value["installationId"], str)
                or (value["environmentId"] is not None and not isinstance(value["environmentId"], str))):
            w.fail("invalid_native_event", message)
        return True

    def _thread_event(self, method, value, journal):
        if method not in {"thread/started", "thread/name/updated", "thread/settings/updated", "thread/status/changed", "thread/tokenUsage/updated", "warning", "thread/goal/cleared"}:
            return False
        thread = value.get("thread") if method == "thread/started" else None
        if method == "thread/started" and not isinstance(thread, dict):
            w.fail("invalid_native_event", "Native thread-start notification is malformed.")
        thread_id = thread.get("id") if isinstance(thread, dict) else value.get("threadId")
        if thread_id != journal.state["thread_id"]:
            w.fail("foreign_native_event", "Thread lifecycle notification belongs to another native thread.")
        if method == "warning":
            if set(value) != {"threadId", "message"} or not isinstance(value.get("message"), str):
                w.fail("invalid_native_event", "Native thread warning shape is malformed; contents suppressed.")
        elif method == "thread/goal/cleared":
            if set(value) != {"threadId"}:
                w.fail("invalid_native_event", "Native goal-cleared notification shape is malformed; contents suppressed.")
        elif method == "thread/started":
            cwd = thread.get("cwd")
            if not isinstance(cwd, str) or str(w.absolute_path(cwd, "Native notification root")) != self.expected["cwd"]:
                w.fail("native_identity_mismatch", "Thread lifecycle notification changed the native root.")
            if thread.get("ephemeral") is True or ("modelProvider" in thread and thread["modelProvider"] != self.expected["native_provider"]):
                w.fail("native_identity_mismatch", "Thread lifecycle notification changed provider/persistence identity.")
        elif method == "thread/name/updated":
            if value.get("threadName") is not None and not isinstance(value["threadName"], str):
                w.fail("invalid_native_event", "Native thread name is malformed.")
        elif method == "thread/settings/updated":
            settings = value.get("threadSettings")
            if not isinstance(settings, dict):
                w.fail("invalid_native_event", "Native thread settings are malformed.")
            for key, expected in (("model", self.expected["model"]), ("modelProvider", self.expected["native_provider"]),
                                  ("effort", self.expected["effort"]), ("approvalPolicy", self.context["approval"]["policy"]),
                                  *([("approvalsReviewer", self.context["approval"]["reviewer"])] if self.context["approval"]["policy"] != "never" or self.context.get("schema") != 2 else [])):
                if settings.get(key) != expected:
                    w.fail("native_identity_mismatch", "Native thread settings changed model/provider/effort/approval requirements.")
            if not isinstance(settings.get("cwd"), str) or str(w.absolute_path(settings["cwd"], "Native settings root")) != self.expected["cwd"]:
                w.fail("native_identity_mismatch", "Native thread settings changed the working root.")
            # Legacy sandboxPolicy is observation only; it cannot replace or
            # downgrade separately verified named-profile permissions.
        return True

    def _reject_event(self, journal, code, message, method, value, turn_id):
        """Retain first content-free rejection facts, then preserve the failure."""
        if "rejected_native_event" not in journal.state:
            mapping = isinstance(value, dict)
            thread = value.get("threadId") if mapping else None
            nested = value.get("turn") if mapping else None
            turn = (value.get("turnId") or (nested.get("id") if isinstance(nested, dict) else None)) if mapping else None
            tag = type(value).__name__ if type(value) in (dict, list, str, int, float, bool, type(None)) else "other"
            journal.update(rejected_native_event={
                "code": code, "method_sha256": digest(method if isinstance(method, str) else None),
                "params_type": tag, "param_key_count": len(value) if mapping else 0,
                "thread_id_present": mapping and "threadId" in value,
                "thread_id_matches_original": isinstance(thread, str) and thread == journal.state["thread_id"],
                "turn_id_present": mapping and ("turnId" in value or isinstance(nested, dict) and "id" in nested),
                "turn_id_matches_current": isinstance(turn, str) and turn == turn_id})
        w.fail(code, message)

    def qualification_turn(self, rpc, journal, text, operation_id, stage, field, *, observer):
        require_legacy_unit(journal)
        if (journal.state.get("qualification_status") != "qualifying" or stage not in {"init", "task"}
                or not str(journal.state.get("active_operation", "")).startswith("qualify_" + stage + "_")
                or field != "assignment_turn_id" or not callable(observer)):
            w.fail("qualification_transition_invalid", "Synthetic tool observation requires the protected qualifying operation; no general initializer bypass.")
        return self._turn(rpc, journal, text, operation_id, stage, field, _qualification_observer=observer)

    def _turn(self, rpc, journal, text, operation_id, stage, field, *, _qualification_observer=None):
        params = {"threadId": journal.state["thread_id"], "input": [{"type": "text", "text": text, "text_elements": []}],
                  "model": self.expected["model"], "effort": self.expected["effort"], "permissions": self.names[stage],
                  **self._approval_params(), "clientUserMessageId": operation_id,
                  "runtimeWorkspaceRoots": self.context["writable_roots"]}
        response = rpc.call("turn/start", params)
        turn = response.get("turn", {})
        turn_id = w.identifier(turn.get("id"), "native turn")
        journal.record_ack(journal.state["active_operation"], {field: turn_id})
        journal.update(last_turn_status="inProgress")
        public, tool_items = "", []
        last_progress, warned, diagnosed, cancelling = time.monotonic(), False, False, False
        def check_silence():
            nonlocal warned, diagnosed, cancelling
            age = time.monotonic() - last_progress
            if age >= 120 and not warned:
                journal.update(observation={"stage": "warning", "silence_seconds": int(age)})
                warned = True
            if age >= 300 and not diagnosed:
                process = getattr(rpc.transport, "process", None)
                journal.update(observation={"stage": "diagnostics", "owner_alive": process is not None and process.poll() is None,
                                            "silence_seconds": int(age)})
                diagnosed = True
            if age >= 600:
                if cancelling:
                    w.fail("native_silence_cancelled", "Owned turn cancellation has no terminal confirmation; reconcile, never replay.")
                process = getattr(rpc.transport, "process", None)
                if not rpc.transport.shared and (process is None or process.poll() is not None):
                    w.fail("native_owner_ended", "Native owner ended without terminal turn proof.")
                journal.update(cancellation={"turn_id": turn_id, "status": "sending", "reason": "unconfirmed_progress_after_state_check"})
                rpc.call("turn/interrupt", {"threadId": journal.state["thread_id"], "turnId": turn_id})
                journal.update(cancellation={"turn_id": turn_id, "status": "acknowledged"})
                cancelling = True
        while True:
            check_silence()
            try:
                event = rpc.next_event()
            except w.WorkflowError as error:
                if error.code != "native_inactivity":
                    raise
                continue
            method, value = event.get("method"), event.get("params", {})
            if self._connection_notice(method, value):
                continue
            if isinstance(value, dict) and self._thread_event(method, value, journal):
                continue
            if not isinstance(value, dict) or value.get("threadId") != journal.state["thread_id"]:
                self._reject_event(journal, "foreign_native_event", "Event belongs to another native thread.", method, value, turn_id)
            turn_record = value.get("turn")
            event_turn = value.get("turnId") or (turn_record.get("id") if isinstance(turn_record, dict) else None)
            if method != "thread/status/changed" and event_turn != turn_id:
                self._reject_event(journal, "foreign_native_event", "Event belongs to another native turn.", method, value, turn_id)
            if stage == "init" and method in TOOL_PROGRESS and _qualification_observer is None:
                w.fail("unexpected_init_tool_use", "Initializer emitted native tool progress; task execution blocked.")
            if method == "item/completed":
                last_progress, warned, diagnosed = time.monotonic(), False, False
                item = value.get("item", {})
                kind = item.get("type")
                if stage == "init" and kind not in {"agentMessage", "userMessage", "reasoning"} and _qualification_observer is None:
                    w.fail("unexpected_init_tool_use", "Initializer used a tool; retain its chat and block task execution.")
                if _qualification_observer is not None and kind not in {"agentMessage", "userMessage", "reasoning", "plan"}:
                    if kind not in {"commandExecution", "fileChange", "functionCallOutput"}:
                        w.fail("native_tool_unqualified", "Qualification emitted an unplanned native tool family.")
                    # Raw native tool data remains bounded in memory only. The
                    # reviewed observer returns hashes/typed observations after
                    # terminal completion; Journal never receives these bytes.
                    if len(tool_items) >= 16 or len(json.dumps(item, ensure_ascii=False).encode("utf-8")) > 128 * 1024:
                        w.fail("oversize_qualification_item", "Native synthetic item exceeds its finite evidence bound.")
                    tool_items.append(item)
                if kind == "agentMessage" and _qualification_observer is None:
                    public += item.get("text", "")
                    if len(public) > 512 * 1024:
                        w.fail("oversize_result", "Native public result exceeds bound.")
            elif method == "turn/completed":
                observed = terminal_observation(event, thread_id=journal.state["thread_id"], turn_id=turn_id)
                status = observed["status"]
                journal.update(last_turn_status=status)
                if status != "completed":
                    w.fail("native_turn_failed", "Native turn did not complete; no automatic replacement or replay.")
                if _qualification_observer is not None:
                    result = _qualification_observer(tool_items, turn_id)
                    if not isinstance(result, dict) or len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 64 * 1024:
                        w.fail("invalid_qualification_observation", "Synthetic observer must return bounded safe structured evidence.")
                    return result
                if stage == "init" and not public.strip():
                    w.fail("missing_init_answer", "Initializer has no confirmed public readiness answer.")
                return {"turn_id": turn_id, "status": status, "public": public}
            elif method == "error":
                journal.update(observation=error_observation(value))
            elif method in PUBLIC_PROGRESS | REASONING_PROGRESS | {"item/started", "turn/started"}:
                last_progress, warned, diagnosed = time.monotonic(), False, False
            elif method == "autoApprovalReview/strictReviewRequired":
                w.fail("native_host_review_required", "Actual native approval route requires its supported host review; no approval answer fabricated.")
            elif method != "thread/status/changed":
                self._reject_event(journal, "unknown_native_event", "Native event shape is outside the qualified versioned protocol.", method, value, turn_id)

    def read_turn_items(self, rpc, thread_id, turn_id):
        """Exhaust one exact acknowledged turn, read-only, with bounded pages.

        Only the verified transport module's matched unsupported-method error
        permits a legacy full-turn read. Never infer this from free-form text.
        """
        w.identifier(thread_id, "history thread")
        w.identifier(turn_id, "history turn")
        items, typed, identities = [], set(), {}
        total_bytes = 0
        allowed = {"agentMessage", "userMessage", "reasoning", "plan", "commandExecution", "fileChange", "functionCallOutput"}
        def append(row):
            nonlocal total_bytes
            if not isinstance(row, dict):
                w.fail("native_history_invalid", "Malformed native history item.")
            if "item" in row:
                if (set(row) - {"turnId", "item", "startedAtMs", "completedAtMs"} or row.get("turnId") != turn_id
                        or any(value is not None and (type(value) is not int or not 0 <= value < 2 ** 63)
                               for value in (row.get("startedAtMs"), row.get("completedAtMs")))):
                    w.fail("native_history_invalid", "Foreign or malformed native history wrapper.")
                row = row["item"]
            if not isinstance(row, dict) or row.get("type") not in allowed:
                w.fail("native_history_invalid", "Unknown native history item family.")
            item_id = w.identifier(row.get("id"), "native history item")
            kind = row["type"]
            if (kind, item_id) in typed:
                w.fail("native_history_invalid", "Duplicate native typed item identity.")
            if "turnId" in row and row["turnId"] != turn_id:
                w.fail("native_history_invalid", "Foreign native history item.")
            prior = identities.get(item_id)
            if prior is not None:
                if ({prior["type"], kind} != {"fileChange", "functionCallOutput"}
                        or (row if kind == "functionCallOutput" else prior).get("name") != "apply_patch"):
                    w.fail("native_history_invalid", "Unsupported native cross-type item identity collision.")
            identities[item_id] = row
            typed.add((kind, item_id))
            if kind == "agentMessage" and not isinstance(row.get("text"), str):
                w.fail("native_history_invalid", "Malformed native public message.")
            total_bytes += len(json.dumps(row, ensure_ascii=False).encode("utf-8"))
            if len(items) >= 3200 or total_bytes > 4 * 1024 * 1024:
                w.fail("native_history_limit", "Exact turn item inventory exceeds bounded read limits.")
            items.append(row)
        def cursor_of(page, seen):
            cursor = page.get("nextCursor")
            if cursor is not None:
                if not isinstance(cursor, str) or not cursor or len(cursor) > 2048 or cursor in seen:
                    w.fail("native_history_invalid", "Native history cursor is malformed or repeated.")
                seen.add(cursor)
            return cursor
        cursor, seen = None, set()
        for page_number in range(32):
            params = {"threadId": thread_id, "turnId": turn_id, "limit": 1, "sortDirection": "asc"}
            if cursor is not None:
                params["cursor"] = cursor
            try:
                page = rpc.call("thread/items/list", params)
            except NativeRPCError as error:
                if page_number or error.method != "thread/items/list" or error.rpc_code != -32601:
                    raise
                break
            if not isinstance(page, dict) or not isinstance(page.get("data"), list) or len(page["data"]) > 100:
                w.fail("native_history_invalid", "Malformed native item page.")
            for row in page["data"]:
                append(row)
            cursor = cursor_of(page, seen)
            if cursor is None:
                return items
        else:
            w.fail("native_history_limit", "Exact turn item reader exceeds 32 pages; no partial proof.")
        # A complete legacy scan also rejects duplicate turn identities/cursors.
        cursor, seen, turns, found = None, set(), set(), False
        for _ in range(32):
            params = {"threadId": thread_id, "limit": 1, "itemsView": "full", "sortDirection": "asc"}
            if cursor is not None:
                params["cursor"] = cursor
            page = rpc.call("thread/turns/list", params)
            if not isinstance(page, dict) or not isinstance(page.get("data"), list) or len(page["data"]) > 100:
                w.fail("native_history_invalid", "Malformed native full-turn page.")
            for row in page["data"]:
                if not isinstance(row, dict):
                    w.fail("native_history_invalid", "Malformed native full turn.")
                identity = w.identifier(row.get("id"), "native history turn")
                if identity in turns or row.get("status") not in {"completed", "failed", "interrupted", "inProgress", "queued"}:
                    w.fail("native_history_invalid", "Malformed or duplicate native full turn.")
                turns.add(identity)
                if identity == turn_id:
                    if row["status"] != "completed" or not isinstance(row.get("items"), list):
                        w.fail("native_persistence_unconfirmed", "Exact legacy turn is not complete with full items.")
                    found = True
                    for item in row["items"]:
                        append(item)
            cursor = cursor_of(page, seen)
            if cursor is None:
                if not found:
                    w.fail("native_persistence_unconfirmed", "Exact legacy turn not found.")
                return items
        w.fail("native_history_limit", "Legacy exact-turn read exceeds 32 pages; no partial proof.")

    def _persisted(self, rpc, journal, *, require_idle=True):
        thread_id = journal.state["thread_id"]
        result = rpc.call("thread/read", {"threadId": thread_id, "includeTurns": False})
        thread = result.get("thread", {})
        if thread.get("id") != thread_id or str(Path(thread.get("cwd", "")).resolve()) != self.expected["cwd"]:
            w.fail("native_history_mismatch", "Native persisted chat root/ID changed.")
        prior = journal.state.get("initialization_turn_id")
        assignment = journal.state.get("assignment_turn_id")
        required = {prior}
        if assignment:
            required.add(assignment)
        # Reconciliation must observe the exact acknowledged ambiguous turns too;
        # human participation may place them beyond the newest history page.
        active = journal.state.get("active_operation")
        pending = journal.lookup_operation(active) if active else None
        if pending:
            required.update(value for key, value in pending["ack"].items() if key != "thread_id")
        rows, seen_ids, seen_cursors, cursor = [], set(), set(), None
        for _ in range(32):
            params = {"threadId": thread_id, "limit": 100, "itemsView": "notLoaded", "sortDirection": "desc"}
            if cursor is not None:
                params["cursor"] = cursor
            page = rpc.call("thread/turns/list", params)
            data = page.get("data") if isinstance(page, dict) else None
            if not isinstance(data, list) or len(data) > 100:
                w.fail("native_history_invalid", "Native turn history page is malformed or oversized.")
            for row in data:
                if (not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]
                        or len(row["id"]) > 1024 or row["id"] in seen_ids
                        or not isinstance(row.get("status"), str)
                        or row["status"] not in {"completed", "failed", "interrupted", "inProgress", "queued"}):
                    w.fail("native_history_invalid", "Native turn history identity/status is malformed or duplicated.")
                seen_ids.add(row["id"])
                rows.append(row)
            if require_idle and any(row["status"] in {"inProgress", "queued"} for row in data):
                w.fail("native_turn_active", "Native chat has an active/queued turn; do not resume over it.")
            next_cursor = page.get("nextCursor")
            if next_cursor is not None:
                if not isinstance(next_cursor, str) or not next_cursor or len(next_cursor) > 2048 or next_cursor in seen_cursors:
                    w.fail("native_history_invalid", "Native turn history cursor is invalid or repeated.")
                seen_cursors.add(next_cursor)
            if required <= seen_ids or next_cursor is None:
                break
            cursor = next_cursor
        else:
            w.fail("native_history_limit", "Exact acknowledged history exceeds 32 pages; no resume, allocation or replay permitted.")
        if not any(row["id"] == prior and row["status"] == "completed" for row in rows):
            w.fail("native_persistence_unconfirmed", "Terminal initializer not found after reconnection.")
        if require_idle and assignment and not any(row.get("id") == assignment and row.get("status") == "completed" for row in rows):
            w.fail("native_prior_turn_unconfirmed", "Exact last acknowledged assignment is missing or noncompleted; no follow-up sent.")
        items = self.read_turn_items(rpc, thread_id, prior)
        if any(row["type"] not in {"agentMessage", "userMessage", "reasoning", "plan"} for row in items):
            w.fail("unexpected_init_tool_use", "Persisted initializer contains tool activity; task dispatch blocked.")
        answers = [row.get("text", "") for row in items if row["type"] == "agentMessage"]
        if not answers or digest("".join(answers)) != journal.state.get("readiness_digest"):
            w.fail("native_persistence_unconfirmed", "Public readiness answer not preserved across reconnection.")
        visible = False
        cursor = None
        for _ in range(8):
            params = {"cwd": self.expected["cwd"], "limit": 100}
            if cursor:
                params["cursor"] = cursor
            page = rpc.call("thread/list", params)
            if any(row.get("id") == thread_id for row in page.get("data", [])):
                visible = True
                break
            cursor = page.get("nextCursor")
            if not cursor:
                break
        if not visible:
            w.fail("native_discovery_unconfirmed", "Stored chat absent from bounded default native discovery; do not create a replacement.")
        return rows

    def create(self, journal, brief):
        require_legacy_unit(journal)
        if self.context.get("schema") == 2:
            from native_sprint import ordinary_session_guard
            ordinary_session_guard(journal)
        if journal.state.get("thread_id") or journal.has_operations():
            w.fail("sprint_exists", "Sprint state exists; no duplicate create.")
        marker = uuid.uuid4().hex
        journal.update(attempt_marker=marker)
        rpc = self._open(journal)
        try:
            journal.perform("allocate", self.expected, lambda: self._thread(rpc, journal))
            title = "Sprint " + journal.identity["sprint"] + " " + marker
            journal.perform("name", title, lambda: rpc.call("thread/name/set", {"threadId": journal.state["thread_id"], "name": title}))
            result = journal.perform("initialize", marker, lambda: self._turn(rpc, journal, "Return a short readiness confirmation. Do not use tools, files, delegation or perform sprint work.", marker + "-init", "init", "initialization_turn_id"))
            journal.update(readiness_digest=digest(result["public"]))
        finally:
            self._close(rpc, journal)
        rpc = self._open(journal)
        try:
            self._persisted(rpc, journal)
            journal.update(backend_persistence="confirmed", client_visibility="pending")
            journal.perform("resume", journal.state["thread_id"], lambda: self._thread(rpc, journal, True))
            result = journal.perform("brief", digest(brief), lambda: self._turn(rpc, journal, brief, marker + "-brief", "task", "assignment_turn_id"))
            journal.update(operation_status="completed", last_turn_status=result["status"])
        finally:
            self._close(rpc, journal)

    def send(self, journal, text, operation_id):
        require_legacy_unit(journal)
        if self.context.get("schema") == 2:
            from native_sprint import ordinary_session_guard
            ordinary_session_guard(journal)
        if journal.state.get("backend_persistence") != "confirmed" or journal.state.get("last_turn_status") != "completed":
            w.fail("native_not_idle", "Same-chat follow-up needs confirmed persistence and terminal prior turn.")
        rpc = self._open(journal)
        try:
            self._persisted(rpc, journal)
            journal.perform(operation_id + "-resume", journal.state["thread_id"], lambda: self._thread(rpc, journal, True))
            result = journal.perform(operation_id, digest(text), lambda: self._turn(rpc, journal, text, operation_id, "task", "assignment_turn_id"))
            journal.update(operation_status="completed", last_turn_status=result["status"])
        finally:
            self._close(rpc, journal)

    def status(self, journal):
        require_legacy_unit(journal)
        if not journal.state.get("thread_id"):
            w.fail("allocation_unknown", "Creation ID unknown; trusted-owner bounded reconciliation required, never automatic create retry.")
        rpc = self._open(journal)
        try:
            turns = self._persisted(rpc, journal, require_idle=False)
            journal.update(native_read_status="active" if any(row.get("status") in {"inProgress", "queued"} for row in turns) else "persistent_idle")
        finally:
            self._close(rpc, journal)

    def reconcile(self, journal):
        """Only a known acknowledged turn ID can reconcile an ambiguous wait.

        Unknown allocation/title/resume/acceptance stays unresolved; no replay.
        """
        rpc = self._open(journal)
        try:
            turns = self._persisted(rpc, journal, require_idle=False)
            terminal = {row["id"]: row["status"] for row in turns if row.get("status") in {"completed", "failed", "interrupted"}}
            name = journal.state.get("active_operation")
            if name:
                record = journal.lookup_operation(name)
                ids = [value for key, value in (record or {}).get("ack", {}).items() if key != "thread_id"]
                if len(ids) != 1 or ids[0] not in terminal:
                    w.fail("native_reconciliation_required", "Ambiguous operation lacks exact acknowledged terminal turn proof.")
                journal.resolve_terminal(name, {"turn_id": ids[0], "status": terminal[ids[0]], "reconciled": True})
            elif journal.has_unresolved():
                w.fail("native_reconciliation_required", "Unresolved owned cleanup requires trusted reconciliation.")
            journal.update(operation_status="complete", native_read_status="reconciled")
        finally:
            self._close(rpc, journal)

    def steer(self, journal, text, operation_id, expected_turn_id):
        self._management(journal, operation_id, expected_turn_id, "turn/steer", text)

    def interrupt(self, journal, operation_id, expected_turn_id):
        self._management(journal, operation_id, expected_turn_id, "turn/interrupt", None)

    def _management(self, journal, operation_id, expected_turn_id, method, text):
        require_legacy_unit(journal)
        if not expected_turn_id or expected_turn_id != journal.state.get("assignment_turn_id") or journal.state.get("last_turn_status") != "inProgress":
            w.fail("turn_ownership_mismatch", "Management requires the exact owned active turn.")
        rpc = self._open(journal)
        try:
            params = {"threadId": journal.state["thread_id"], "expectedTurnId": expected_turn_id} if text is not None else {"threadId": journal.state["thread_id"], "turnId": expected_turn_id}
            if text is not None:
                params["input"] = [{"type": "text", "text": text, "text_elements": []}]
            journal.perform(operation_id, params, lambda: rpc.call(method, params))
        finally:
            self._close(rpc, journal)
