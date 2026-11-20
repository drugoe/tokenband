"""Protected persistent native sprint operations. Human/context provenance is
supplied by the trusted caller; JSON validation cannot authenticate either.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import unicodedata
import uuid
import worker as w

COMMON = {"kind", "runtime", "sha256", "version", "protocol", "connection", "native_home"}
ROOT_KEYS = {"schema", "writable_roots", "temp_roots", "protected_names"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def validate_driver_config(config):
    drivers = config.get("drivers", {})
    if not isinstance(drivers, dict) or len(drivers) > 128:
        w.fail("invalid_drivers", "Drivers must be a bounded named mapping.")
    for name, spec in drivers.items():
        w.identifier(name, "driver")
        w.object_keys(spec, COMMON, "native driver", {"initialization_profile", "execution_profile", "settings", "settings_sha256", "native_helpers", "disabled_mcp_servers", "native_base_url", "native_wire_api", "effective_native_executables", "native_auth_dependencies", "qualification", "qualification_sha256", "native_model_catalog"})
        if spec["kind"] not in {"codex", "claude-code"}:
            w.fail("unsupported_driver", "Configure an implemented native driver kind.")
        if "native_model_catalog" in spec:
            if spec["kind"] != "codex":
                w.fail("invalid_driver", "Native model catalogs apply only to Codex.")
            catalog = spec["native_model_catalog"]
            w.object_keys(catalog, {"path", "final_sha256", "source_entry_sha256"}, "native model catalog")
            w.validate_path_reference(catalog["path"])
            w.digest_pin(catalog["final_sha256"])
            w.digest_pin(catalog["source_entry_sha256"])
        w.digest_pin(spec["sha256"])
        if ("qualification" in spec) != ("qualification_sha256" in spec):
            w.fail("missing_qualification_pin", "Configure qualification and qualification_sha256 together.")
        if "qualification" in spec:
            w.digest_pin(spec["qualification_sha256"])
        w.validate_path_reference(spec["runtime"], purpose="native")
        if spec["runtime"].startswith("@runtime:") and spec["runtime"][9:] not in config.get("runtimes", {}):
            w.fail("missing_runtime", "Native driver references an undeclared runtime.")
        helpers = spec.get("native_helpers", {})
        if not isinstance(helpers, dict) or set(helpers) - {"codex-command-runner.exe", "codex-windows-sandbox-setup.exe"}:
            w.fail("invalid_helpers", "Native helper pins must name only versioned native sibling helpers.")
        for pin in helpers.values():
            w.digest_pin(pin)
        dependencies = spec.get("native_auth_dependencies", {})
        if not isinstance(dependencies, dict) or len(dependencies) > 32:
            w.fail("invalid_auth_dependencies", "Native auth dependencies must be a bounded protected path-to-SHA mapping.")
        for path, pin in dependencies.items():
            w.validate_path_reference(path)
            w.digest_pin(pin)
        effective = spec.get("effective_native_executables", {})
        roles = ({"main"}, {"main", "runner", "setup"}) if w.host_platform() == "windows" else ({"main"},)
        if not isinstance(effective, dict) or (effective and set(effective) not in roles):
            w.fail("invalid_native_executables", "Actual materialized native executables must name exactly this platform's main/runner/setup roles.")
        for record in effective.values():
            w.object_keys(record, {"path", "sha256"}, "effective native executable")
            w.validate_path_reference(record["path"], purpose="native")
            w.digest_pin(record["sha256"])
        servers = spec.get("disabled_mcp_servers", [])
        if (not isinstance(servers, list) or len(servers) > 64
                or any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", name) for name in servers)
                or len(set(servers)) != len(servers)):
            w.fail("invalid_mcp_scope", "Disabled MCP servers must be a bounded unique list of native configuration names.")
        if servers and spec["kind"] != "codex":
            w.fail("invalid_mcp_scope", "Claude uses its protected strict-empty MCP file, not Codex overrides.")
        if helpers and (spec["kind"] != "codex" or w.host_platform() != "windows"):
            w.fail("invalid_helpers", "This native driver/platform has no separate qualified helper executables.")
        if "qualification" in spec:
            w.validate_path_reference(spec["qualification"])
        if spec["native_home"] is not None:
            w.validate_path_reference(spec["native_home"])
        w.identifier(spec["version"], "native version")
        if spec["kind"] == "codex":
            if "native_base_url" in spec:
                w.connection_url({"base_url": spec["native_base_url"]})
            if "native_wire_api" in spec and spec["native_wire_api"] != "responses":
                w.fail("unsupported_wire_api", "Qualified Codex native providers use the responses wire protocol.")
            if spec["protocol"] != "codex-0.160" or spec["version"] != "0.160.0" or spec["connection"] not in {"auto", "owned-stdio", "shared-unix"}:
                w.fail("unsupported_protocol", "Codex requires qualified 0.160.0 protocol.")
            if "settings" in spec or "settings_sha256" in spec:
                w.fail("invalid_driver", "Claude settings cannot alter Codex.")
            for field in ("initialization_profile", "execution_profile"):
                if field in spec and spec[field] != ":danger-full-access":
                    w.identifier(spec[field], "permission profile")
        else:
            if {"native_base_url", "native_wire_api", "effective_native_executables"} & spec.keys():
                w.fail("invalid_driver", "Codex native endpoint pins cannot alter Claude.")
            if spec["protocol"] != "claude-restricted-print" or spec["connection"] != "owned-stdio":
                w.fail("unsupported_protocol", "Claude supports owned restricted-print baseline only.")
            if not {"settings", "settings_sha256"} <= spec.keys():
                w.fail("missing_settings", "Claude needs protected explicit settings.")
            w.validate_path_reference(spec["settings"])
            w.digest_pin(spec["settings_sha256"])
            if {"initialization_profile", "execution_profile"} & spec.keys():
                w.fail("invalid_driver", "Codex profiles cannot alter Claude.")
    for profile in config.get("models", {}).values():
        if "chat" in profile:
            binding = profile["chat"]
            w.object_keys(binding, {"driver", "native_provider"}, "native binding")
            w.identifier(binding["driver"], "driver")
            w.identifier(binding["native_provider"], "native provider")
            if binding["driver"] not in drivers:
                w.fail("missing_driver", "Native binding names an undeclared driver.")
    return config


def uses_windows_sandbox(context):
    # All actual schema2 phases (init, task and local probe) use full access.
    return w.host_platform() == "windows" and context.get("schema") != 2


def protection_context(config, path, root, *, tools=False):
    return w.caller_protection_context(config, path, root, tools=tools)


def freeze_file(path, expected=None):
    raw = w.lexical_path(path, "Frozen native control")
    canonical = w.absolute_path(raw, "Frozen native control", must_exist=True)
    pin = w.file_hash(canonical)
    if expected is not None and pin != expected.lower():
        w.fail("control_changed", "Expected protected native control bytes changed before parsing.")
    return raw, canonical, expected.lower() if expected is not None else pin


def check_frozen(record, roots):
    raw, canonical, pin = record
    w.protect_path(raw, roots)
    if raw.resolve() != canonical or w.file_hash(canonical) != pin:
        w.fail("control_changed", "Frozen native control alias/bytes changed; no further mutation.")


def freeze_model_catalog(config, spec, model, roots):
    """Pin one protected catalog and verify a reversible, one-field full-entry change."""
    catalog = spec["native_model_catalog"]
    raw, _ = config.path_context.resolve_pair(catalog["path"])
    w.plain_control_path(raw)
    record = freeze_file(raw, catalog["final_sha256"])
    check_frozen(record, roots)
    message = "Native model catalog is malformed or differs from its trusted full-entry pins; contents suppressed."
    try:
        document = w.read_json(record[1])
        pending = [(document, 1)]
        while pending:
            item, depth = pending.pop()
            if depth > 64:
                w.fail("invalid_model_catalog", message)
            if isinstance(item, dict):
                pending.extend((value, depth + 1) for value in item.values())
            elif isinstance(item, list):
                pending.extend((value, depth + 1) for value in item)
        rows = document.get("models") if isinstance(document, dict) else None
        if not isinstance(rows, list):
            w.fail("invalid_model_catalog", message)
        selected = [row for row in rows if isinstance(row, dict) and row.get("slug") == model]
        if len(selected) != 1 or selected[0].get("tool_mode") != "direct":
            w.fail("invalid_model_catalog", message)
        original = dict(selected[0], tool_mode="code_mode_only")
        if digest(original) != catalog["source_entry_sha256"].lower():
            w.fail("invalid_model_catalog", message)
    except (RecursionError, UnicodeError, ValueError, TypeError, OverflowError):
        w.fail("invalid_model_catalog", message)
    check_frozen(record, roots)
    return record, {"lexical": str(record[0]), "canonical": str(record[1]), "sha256": record[2],
                    "source_entry_sha256": catalog["source_entry_sha256"].lower()}


def scope_binding(spec, expected, context, source, home, modules, helpers):
    """Exact portable proof scope; no credentials or mutable authorization bytes."""
    public = {key: value for key, value in context.items() if not key.startswith("_")}
    driver = {key: value for key, value in spec.items() if not key.startswith("_") and key not in {"qualification", "qualification_sha256"}}
    raw_home = spec.get("_raw_native_home", spec.get("_native_home"))
    binding = {"context": public, "context_source": {"lexical": str(source[0]), "canonical": str(source[1]), "sha256": source[2]},
               "protection_paths": [str(path) for path in context["_protection_roots"]], "driver": driver,
               "expected": expected, "native_home": {"lexical": str(raw_home), "canonical": spec.get("_native_home")},
               "runtime": {"lexical": spec["_raw_runtime"], "canonical": spec["_runtime"], "sha256": spec["sha256"]},
               "modules": modules, "native_helpers": helpers}
    if "_native_config" in spec:
        binding["native_config"] = spec["_native_config"]
    if "_native_auth_dependencies" in spec:
        binding["native_auth_dependencies"] = spec["_native_auth_dependencies"]
    if "_native_model_catalog" in spec:
        binding["native_model_catalog"] = spec["_native_model_catalog"]
    if spec["kind"] == "codex":
        from native_codex import profiles, profile_names, TOOL_ENV
        binding["profiles"] = profiles(context, [home], spec["_native_home"])
        profile_names(context, spec, binding["profiles"])  # Reject incompatible overrides before allocation.
        binding["enabled_tool_families"] = ["shell", "patch"]
        binding["effective_native_executables"] = spec["_effective_native_executables"]
        names = TOOL_ENV | {"CODEX_HOME", "OPENAI_BASE_URL", "CODEX_OSS_BASE_URL", "CODEX_OSS_PORT"}
        binding["environment"] = {name: os.environ.get(name) for name in sorted(names)}
    else:
        from native_claude import ENVIRONMENT_NAMES
        binding["profiles"] = {"tools": []}
        binding["environment"] = {name: os.environ.get(name) for name in ENVIRONMENT_NAMES}
    binding["environment_names"] = sorted(os.environ)
    return binding


class Journal:
    """One permanent guard, a small state, ordinary immutable operation files."""
    def __init__(self, directory, host, root, sprint, parent, *, _migration=None):
        for value in (host, sprint, parent):
            w.identifier(value)
        self.identity = {"host": host, "root": str(w.absolute_path(root, "Working root")), "sprint": sprint}
        self.key = digest(self.identity)
        self.directory, self.parent = Path(directory) / self.key, parent
        self.state, self.guard, self._locked = None, None, False
        self._migration = _migration
        self._io_failed = False
        self._entry_lock = threading.Lock()
        self.path = self.directory / "state.json"
        self.operations = self.directory / "operations"

    def __enter__(self):
        if not self._entry_lock.acquire(blocking=False):
            w.fail("sprint_owned", "This exact Journal instance already has an owner.")
        try:
            return self._enter()
        except BaseException:
            try:
                self._release_kernel()
            finally:
                self._entry_lock.release()
            raise

    def _enter(self):
        w.plain_control_path(self.directory)
        lock = w.plain_control_path(self.directory / "lock")
        prior = lock.exists()
        if not prior:
            prior = self.directory.exists() and any(self.directory.iterdir())
            if prior and self.path.exists():
                if self._migration is not None:
                    orphan, _ = self._migration_current(*self._migration)
                else:
                    orphan = w.read_json(w.plain_control_path(self.path))
                self._reject_retired_unit(orphan)
            w.make_control_directory(self.directory)
        self.handle = lock.open("a+b")
        try:
            os.set_inheritable(self.handle.fileno(), False)
            self.handle.seek(0)
        except BaseException:
            self.handle.close()
            raise
        # Take the kernel guard before touching the guard byte: on Windows the
        # byte-range lock is mandatory, so a contending handle cannot read that
        # byte and must fail closed as ownership instead of an I/O error. Only a
        # refused acquisition is ownership; preparation and guard-byte I/O keep
        # their own error identity.
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            w.fail("sprint_owned", "Another owner holds this exact host/root/sprint.")
        self._locked = True
        info = os.fstat(self.handle.fileno())
        self._guard_identity = (info.st_dev, info.st_ino)
        try:
            self._check_lock()
            if self._migration is not None:
                state, current_pin = self._migration_current(*self._migration)
            else:
                state = w.read_json(w.plain_control_path(self.path)) if self.path.exists() else None
            self._reject_retired_unit(state)
            if not self.handle.read(1):
                self.handle.write(b"0")
                self.handle.flush()
                os.fsync(self.handle.fileno())
            self.handle.seek(0)
            if self._migration is not None:
                self._migrate(*self._migration, current=state, current_pin=current_pin)
                return self
            if state is not None:
                self.state = state
                if not isinstance(self.state, dict) or type(self.state.get("schema")) is not int or self.state["schema"] not in {1, 2}:
                    w.fail("invalid_journal", "Unsupported journal object/version; retain evidence.")
                if self.state.get("identity") != self.identity or self.state.get("parent") != self.parent:
                    w.fail("parent_mismatch", "Retain immutable original sprint ownership.")
                if self.state.get("schema") != 2 or any(key in self.state for key in ("operations", "native_turns", "claude_operations")):
                    w.fail("legacy_journal", "Explicit pinned same-ID migration required; no implicit adoption.")
                self._validate_state()
                if self.state.get("migration_status"):
                    w.fail("migration_pending", "Resume the same pinned local migration; no sends.")
                active = self.state.get("active_operation")
                if active:
                    record = self.lookup_operation(active)
                    if record is None:
                        if self.state["operation_status"] != "preparing":
                            w.fail("invalid_journal", "Active intent missing; retain current reservation and evidence.")
                        return self  # Valid cut before intent publication; keep the preparing fence unchanged.
                    if record and record["status"] == "complete":
                        patch = dict(record["ack"])
                        if record["result"].get("status") in {"completed", "failed", "interrupted"}:
                            patch["last_turn_status"] = record["result"]["status"]
                        self.update(active_operation=None, operation_status="complete", **patch)
                    else:
                        self.update(operation_status="unknown", **(record["ack"] if record else {}))
            else:
                if prior:
                    w.fail("journal_missing", "Prior guard/evidence without state cannot initialize a new sprint.")
                self.state = {"schema": 2, "identity": self.identity, "parent": self.parent,
                              "active_operation": None, "operation_status": "pending", "backend_persistence": "pending",
                              "client_visibility": "pending", "actual_serving_model": "unknown"}
                self.update()
            return self
        except BaseException:
            raise

    def _validate_state(self, state=None):
        """Validate current scalar authority before admission, repair or import."""
        state = self.state if state is None else state
        if (not isinstance(state, dict) or type(state.get("schema")) is not int or state["schema"] != 2
                or state.get("identity") != self.identity or state.get("parent") != self.parent
                or any(key in state for key in ("operations", "native_turns", "claude_operations"))):
            w.fail("invalid_journal", "Invalid current ownership/schema; preserve evidence.")
        enums = {"operation_status": {"pending", "preparing", "sending", "unknown", "complete", "completed"},
                 "backend_persistence": {"pending", "unconfirmed", "confirmed"},
                 "client_visibility": {"pending"}, "actual_serving_model": {"unknown"}}
        for key, values in enums.items():
            if not isinstance(state.get(key), str) or state[key] not in values:
                w.fail("invalid_journal", "Required current scalar missing/invalid; no admission or rewrite.")
        if "active_operation" not in state:
            w.fail("invalid_journal", "Current state requires an explicit active operation or null.")
        active, phase = state["active_operation"], state["operation_status"]
        if active is not None:
            w.identifier(active, "active operation", assignment=True)
        if (phase in {"preparing", "sending", "unknown"}) != (active is not None):
            w.fail("invalid_journal", "Current phase and active operation contradict; preserve evidence.")
        migration = state.get("migration_status")
        if migration is not None and (not isinstance(migration, str) or migration not in {"pending", "needs_reconciliation"}):
            w.fail("invalid_journal", "Invalid current migration phase.")
        if migration is not None or "migration_source_sha256" in state:
            w.digest_pin(state.get("migration_source_sha256"))
        if "migration_unresolved_count" in state:
            count = state["migration_unresolved_count"]
            if type(count) is not int or count < 0:
                w.fail("invalid_journal", "Invalid current migration unresolved count.")
        if migration == "pending" and active is not None:
            w.fail("invalid_journal", "Pending import cannot supersede an active runtime operation.")
        if migration == "needs_reconciliation" and (phase != "unknown" or state.get("migration_unresolved_count", 0) <= 1):
            w.fail("invalid_journal", "Migration reconciliation phase requires its unresolved reservation count.")

    def __exit__(self, *_):
        try:
            self._release_kernel()
        finally:
            self._entry_lock.release()

    def _release_kernel(self):
        if self._locked:
            try:
                self.handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            finally:
                self.handle.close()
                self._locked = False

    def _check_lock(self):
        if not self._locked:
            w.fail("journal_unlocked", "Mutation requires the existing kernel guard.")
        if self._io_failed:
            w.fail("journal_io_unknown", "Control publication outcome uncertain; release and reopen before any effect.")
        path = w.plain_control_path(self.directory / "lock")
        info = path.stat()
        if (info.st_dev, info.st_ino) != self._guard_identity:
            w.fail("guard_changed", "Permanent guard identity changed; no effect permitted.")

    def update(self, **values):
        self._check_lock()
        self._reject_retired_unit(self.state)
        if any(key in values for key in ("operations", "native_turns", "claude_operations")):
            w.fail("invalid_journal", "Cumulative maps are not control state.")
        for key in ("identity", "parent", "selected", "thread_id"):
            if key in values and key in self.state and self.state[key] != values[key]:
                w.fail("sprint_identity_changed", "Existing native identity/binding is immutable.")
        new = dict(self.state, **values)
        self._reject_retired_unit(new)
        try:
            w.atomic_json(self.path, new)
        except (OSError, w.WorkflowError):
            self._io_failed = True
            raise
        self.state = new

    def _op_path(self, name, suffix):
        w.identifier(name, "operation", assignment=True)
        return w.plain_control_path(self.operations / ("op-" + name + "." + suffix))

    def _receipt(self, name, kind, **values):
        return {"schema": 2, "kind": kind, "operation_id": name, "identity": self.identity,
                "parent": self.parent, "binding_sha256": digest(self.state.get("selected")), **values}

    def _read_receipt(self, name, kind, path):
        doc = w.read_json(path)
        if (not isinstance(doc, dict) or type(doc.get("schema")) is not int or doc.get("schema") != 2 or doc.get("kind") != kind
                or doc.get("operation_id") != name or doc.get("identity") != self.identity
                or doc.get("parent") != self.parent or doc.get("binding_sha256") != digest(self.state.get("selected"))):
            w.fail("operation_conflict", "Receipt identity/binding conflicts; no replay.")
        return doc

    def lookup_operation(self, name):
        self._check_lock()
        path = self._op_path(name, "intent.json")
        if not path.exists():
            if self._op_path(name, "terminal.json").exists() or self._op_path(name, "ack.json").exists():
                w.fail("invalid_journal", "Referenced intent disappeared; preserve evidence.")
            return None
        intent = self._read_receipt(name, "intent", path)
        w.digest_pin(intent.get("sha256"))
        result = {"sha256": intent["sha256"], "status": "unknown", "ack": {}}
        ack = self._op_path(name, "ack.json")
        if ack.exists():
            ids = self._read_receipt(name, "ack", ack).get("ids")
            if not isinstance(ids, dict) or not ids or set(ids) - {"thread_id", "initialization_turn_id", "assignment_turn_id"}:
                w.fail("invalid_journal", "Malformed saved native acknowledgement.")
            for value in ids.values():
                w.identifier(value, "saved native acknowledgement")
            result["ack"] = ids
        terminal = self._op_path(name, "terminal.json")
        if terminal.exists():
            doc = self._read_receipt(name, "terminal", terminal)
            if doc.get("intent_sha256") != w.file_hash(path) or not isinstance(doc.get("result"), dict):
                w.fail("invalid_journal", "Terminal receipt does not bind its original intent.")
            result.update(status="complete", result=doc["result"])
        return result

    def has_operations(self):
        self._check_lock()
        if self.state.get("active_operation"):
            return True
        if self.operations.exists():
            w.plain_control_path(self.operations)
            with os.scandir(self.operations) as entries:
                return any(entry.name.startswith(("op-", "logical-")) for entry in entries)
        return False

    def has_unresolved(self):
        return bool(self.state.get("active_operation") or self.state.get("migration_status")
                    or self.state.get("operation_status") == "unknown")

    def reserve_logical(self, name, payload_sha256):
        self._check_lock()
        w.identifier(name, "logical operation", assignment=True)
        w.digest_pin(payload_sha256)
        if self.has_unresolved():
            w.fail("operation_unknown", "Prior operation unresolved.")
        path = w.plain_control_path(self.operations / ("logical-" + name + ".json"))
        if path.exists():
            w.fail("duplicate_operation", "Logical reservation exists; retain component history.")
        w.write_exclusive(path, self._receipt(name, "logical", sha256=payload_sha256,
                          components=[name + "-persistence", name]))

    def record_ack(self, name, ids):
        self._check_lock()
        if name != self.state.get("active_operation") or not self.lookup_operation(name):
            w.fail("operation_unknown", "Acknowledgement requires the exact active intent.")
        if not isinstance(ids, dict) or not ids or set(ids) - {"thread_id", "initialization_turn_id", "assignment_turn_id"}:
            w.fail("invalid_journal", "Only exact native correlation identities may be acknowledged.")
        for value in ids.values():
            w.identifier(value, "native acknowledgement")
        w.write_exclusive(self._op_path(name, "ack.json"), self._receipt(name, "ack", ids=ids))
        self.update(**ids)

    def _saved_result(self, name, result, *, _existing=False):
        if not isinstance(result, dict):
            return {}
        self._check_lock()
        saved = {}
        if isinstance(result.get("status"), str) and result["status"] in {"complete", "completed", "failed", "interrupted", "observed"}:
            saved["status"] = result["status"]
        for field in ("turn_id", "session_id", "thread_id"):
            if field in result:
                saved[field] = w.identifier(result[field], "returned native identity")
        if result.get("reconciled") is True:
            saved["reconciled"] = True
        for field, values in (("type", {"commandExecution", "fileChange", "functionCallOutput"}),
                              ("stage", {"init", "task"}), ("case", {"allowed", "denied"})):
            if isinstance(result.get(field), str) and result[field] in values:
                saved[field] = result[field]
        if "target" in result and "case" in saved:
            saved["target"] = str(w.absolute_path(result["target"], "synthetic target"))
        observed = result.get("observed")
        expected = self.state.get("selected", {}).get("expected", {})
        if isinstance(observed, dict) and expected:
            fields = {"model": "model", "modelProvider": "native_provider", "reasoningEffort": "effort", "cwd": "cwd"}
            if all(observed.get(key) == expected.get(source) for key, source in fields.items()):
                saved["observed"] = {key: observed[key] for key in fields}
                context = self.state.get("selected", {}).get("permission_identity", {}).get("context", {})
                if context.get("schema") == 2:
                    approval = w.actual_approval(context.get("approval"))
                    requested, reviewer = observed.get("requestedApprovalsReviewer"), observed.get("approvalsReviewer")
                    if (observed.get("approvalPolicy") != approval["policy"] or requested != approval["reviewer"]
                            or (reviewer is not None and (not isinstance(reviewer, str) or reviewer not in w.APPROVAL_REVIEWERS))
                            or (approval["policy"] != "never" and reviewer != requested)):
                        w.fail("native_policy_mismatch", "Immutable native result changed actual approval identity.")
                    saved["observed"].update(approvalPolicy=approval["policy"], requestedApprovalsReviewer=requested, approvalsReviewer=reviewer)
                else:
                    for key, values in (("approvalPolicy", {"on-request"}), ("approvalsReviewer", {"auto_review"})):
                        if isinstance(observed.get(key), str) and observed[key] in values:
                            saved["observed"][key] = observed[key]
        items = result.get("native_items")
        if isinstance(items, list) and len(items) <= 16:
            safe = []
            for item in items:
                if (not isinstance(item, dict) or not isinstance(item.get("type"), str) or item.get("type") not in {"commandExecution", "fileChange", "functionCallOutput"}
                        or not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])):
                    continue
                safe.append({"id": w.identifier(item.get("id"), "synthetic native item"), "type": item["type"], "sha256": item["sha256"]})
            if len(safe) == len(items):
                saved["native_items"] = safe
        for field in ("public", "text"):
            if field in result:
                path = self._op_path(name, "public.txt")
                if _existing and path.exists():
                    raw = result[field].encode("utf-8")
                    descriptor = {"schema_version": 2, "content_file": str(path), "content_sha256": hashlib.sha256(raw).hexdigest(),
                                  "content_bytes": len(raw), "completeness": "unknown", "public_availability": "available" if result[field].strip() else "empty"}
                    w.read_public(descriptor, path)
                    saved[field] = descriptor
                else:
                    saved[field] = w.write_public(path, result[field], completeness="unknown" if _existing else "complete")
        return saved

    def _finish(self, name, result):
        self._check_lock()
        intent = self._op_path(name, "intent.json")
        w.write_exclusive(self._op_path(name, "terminal.json"), self._receipt(name, "terminal",
                          intent_sha256=w.file_hash(intent), result=result))
        patch = {}
        if result.get("status") in {"completed", "failed", "interrupted"}:
            patch["last_turn_status"] = result["status"]
        self.update(active_operation=None, operation_status="complete", **patch)

    def resolve_terminal(self, name, result):
        record = self.lookup_operation(name)
        if name != self.state.get("active_operation") or not record or record["status"] == "complete":
            w.fail("operation_unknown", "Only the exact unresolved intent may be reconciled.")
        if result.get("turn_id") not in record["ack"].values() or result.get("status") not in {"completed", "failed", "interrupted"}:
            w.fail("native_reconciliation_required", "Exact acknowledged terminal turn proof required.")
        self._finish(name, self._saved_result(name, result))
        self.update(last_turn_status=result["status"])

    def perform(self, name, payload, callback):
        self._check_lock()
        w.identifier(name, "operation", assignment=True)
        if self.guard:
            self.guard()
        record = self.lookup_operation(name)
        if record:
            w.fail("operation_exists" if record["sha256"] == digest(payload) else "operation_conflict",
                   "Operation reserved; reconcile instead of replay.")
        if self.has_unresolved():
            w.fail("operation_unknown", "Earlier mutation ambiguous; new sends blocked.")
        if self._op_path(name, "public.txt").exists():
            w.fail("operation_exists", "Existing public path reserves this operation.")
        # Current bounded body plus intent/ack/terminal and control temp capacity.
        w.require_storage(self.directory, 5 * w.MAX_JSON)
        self.update(active_operation=name, operation_status="preparing")
        try:
            w.write_exclusive(self._op_path(name, "intent.json"), self._receipt(name, "intent", sha256=digest(payload)))
            self.update(operation_status="sending")
            if self.guard:
                self.guard()
            result = callback()
            self._check_lock()
            if self.guard:
                self.guard()
            self._finish(name, self._saved_result(name, result))
            return result  # Compatible bounded transient callback return.
        except BaseException:
            try:
                self.update(operation_status="unknown")
            except (OSError, w.WorkflowError):
                pass  # The previously persisted preparing/sending fence remains.
            raise

    @classmethod
    def migrate_legacy(cls, directory, host, root, sprint, parent, *, source_sha256, max_bytes=w.MAX_JSON):
        """Explicit local-only import; trusted caller supplies approved hash/read bound.

        No CLI/provider route or authorization is created here. Unknown larger or
        corrupt inputs require a separate scoped recovery decision.
        """
        w.digest_pin(source_sha256)
        if type(max_bytes) is not int or max_bytes <= 0:
            w.fail("invalid_journal", "Migration requires an approved finite byte bound.")
        with cls(directory, host, root, sprint, parent, _migration=(source_sha256, max_bytes)) as journal:
            return {"status": "needs_reconciliation" if journal.has_unresolved() else "migrated", "identity": journal.identity,
                    "source_sha256": source_sha256, "state": str(journal.path)}

    def _migration_current(self, source_sha256, max_bytes):
        if not self.path.exists():
            return None, None
        try:
            with w.plain_control_path(self.path).open("rb") as stream:
                raw = stream.read(max(w.MAX_JSON, max_bytes) + 1)
            if len(raw) > w.MAX_JSON and len(raw) > max_bytes:
                w.fail("migration_source", "Exact approved migration source/bound differs.")
            pin = hashlib.sha256(raw).hexdigest()
            if len(raw) > w.MAX_JSON and pin != source_sha256:
                w.fail("migration_source", "Exact approved migration source/bound differs.")
            state = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=w.json_pairs,
                               parse_constant=lambda _: w.fail("invalid_journal", "Nonfinite migration state."))
        except (OSError, UnicodeError, ValueError, RecursionError):
            w.fail("migration_source", "Current migration authority unreadable/malformed; retain original evidence.")
        self._reject_retired_unit(state)
        if len(raw) > w.MAX_JSON and (not isinstance(state, dict) or type(state.get("schema")) is not int or state["schema"] != 1):
            w.fail("migration_source", "Larger migration state must be the exact approved legacy original.")
        return state, pin

    @staticmethod
    def _reject_retired_unit(state):
        if isinstance(state, dict):
            selected = state.get("selected")
            permission = selected.get("permission_identity") if isinstance(selected, dict) else None
            if "desktop_unit" in state or isinstance(permission, dict) and "desktop" in permission:
                w.fail("desktop_unit_required", "Historical Desktop claim or scope is frozen; retain its original evidence.")

    def _migrate(self, source_sha256, max_bytes, *, current, current_pin):
        self._check_lock()
        archive = w.plain_control_path(self.directory / "legacy-state.json")
        if archive.exists() and not self.path.exists():
            w.fail("migration_source", "Prior archive without current state is not resume authority; retain all evidence.")
        source = archive if archive.exists() else self.path
        try:
            with source.open("rb") as stream:
                raw = stream.read(max_bytes + 1)
            if len(raw) > max_bytes or hashlib.sha256(raw).hexdigest() != source_sha256:
                w.fail("migration_source", "Exact approved migration source/bound differs.")
            legacy = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=w.json_pairs,
                                parse_constant=lambda _: w.fail("invalid_journal", "Nonfinite legacy state."))
        except (OSError, UnicodeError, ValueError, RecursionError):
            w.fail("migration_source", "Legacy source unreadable/malformed; retain original evidence.")
        self._reject_retired_unit(legacy)
        if (not isinstance(legacy, dict) or type(legacy.get("schema")) is not int or legacy.get("schema") != 1 or legacy.get("identity") != self.identity or legacy.get("parent") != self.parent
                or not isinstance(legacy.get("operations"), dict) or not isinstance(legacy.get("native_turns", {}), dict)
                or not isinstance(legacy.get("claude_operations", {}), dict)):
            w.fail("migration_source", "Legacy ownership/maps differ; no automatic adoption.")
        initial = {key: value for key, value in legacy.items() if key not in {"operations", "native_turns", "claude_operations"}}
        for key, value in (("backend_persistence", "pending"), ("client_visibility", "pending"), ("actual_serving_model", "unknown")):
            initial.setdefault(key, value)
        initial.update(schema=2, active_operation=None, operation_status="pending", migration_status="pending", migration_source_sha256=source_sha256)
        unresolved = self._legacy_unresolved(legacy)
        w.require_storage(self.directory, len(raw) + 5 * w.MAX_JSON)
        if not archive.exists():
            fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                if stream.write(raw) != len(raw):
                    raise OSError("Incomplete legacy archive write.")
                stream.flush()
                os.fsync(stream.fileno())
            w.fsync_directory(archive.parent)
        elif self.path.exists():
            if not isinstance(current, dict):
                w.fail("migration_source", "Current migration authority must be a valid object.")
            original_unchanged = type(current.get("schema")) is int and current["schema"] == 1 and current_pin == source_sha256
            pending = (type(current.get("schema")) is int and current["schema"] == 2 and current.get("migration_source_sha256") == source_sha256
                       and isinstance(current.get("migration_status"), str)
                       and current["migration_status"] in {"pending", "needs_reconciliation"})
            if not original_unchanged and not pending:
                w.fail("migration_source", "Completed/changed live state cannot be overwritten by old migration evidence.")
            if pending:
                self.state = current
                self._validate_state()
                expected = initial
                reconciliation = current["migration_status"] == "needs_reconciliation"
                if reconciliation:
                    expected = dict(initial, active_operation=unresolved[0] if unresolved else None,
                                    operation_status="unknown" if unresolved else "complete",
                                    migration_status="needs_reconciliation" if len(unresolved) > 1 else None,
                                    migration_unresolved_count=len(unresolved))
                if current != expected:
                    w.fail("migration_source", "Current phase/reservations/imported fields contradict the exact archive; no replacement.")
                self._check_import_receipts(legacy, complete_import=reconciliation)
        self.state = initial
        self._validate_state()
        self.update()  # Old exact writer rejects missing operations before its update.
        for name, row in legacy["operations"].items():
            w.identifier(name, "legacy operation", assignment=True)
            if not isinstance(row, dict) or row.get("status") not in {"complete", "unknown", "sending"}:
                w.fail("migration_source", "Unsupported legacy operation; keep migration fenced.")
            w.digest_pin(row.get("sha256"))
            intent = self._receipt(name, "intent", sha256=row["sha256"])
            path = self._op_path(name, "intent.json")
            if path.exists():
                if w.read_json(path) != intent:
                    w.fail("migration_source", "Partial/conflicting imported intent; trusted recovery required.")
            else:
                w.write_exclusive(path, intent)
            ids = self._legacy_ack(legacy, name, row)
            result = row.get("result", {})
            if ids:
                ack = self._receipt(name, "ack", ids=ids)
                path = self._op_path(name, "ack.json")
                if path.exists():
                    if w.read_json(path) != ack:
                        w.fail("migration_source", "Imported ack conflict.")
                else:
                    w.write_exclusive(path, ack)
            if row["status"] == "complete":
                path = self._op_path(name, "terminal.json")
                if path.exists():
                    record = self.lookup_operation(name)
                    if not record or record["status"] != "complete":
                        w.fail("migration_source", "Imported terminal invalid.")
                    for field in ("public", "text"):
                        if field in record["result"]:
                            w.read_public(record["result"][field], self._op_path(name, "public.txt"))
                else:
                    saved = self._saved_result(name, result, _existing=True)
                    w.write_exclusive(path, self._receipt(name, "terminal", intent_sha256=w.file_hash(self._op_path(name, "intent.json")), result=saved))
        for name, pin in legacy.get("claude_operations", {}).items():
            w.identifier(name, "legacy logical operation", assignment=True)
            w.digest_pin(pin)
            path = w.plain_control_path(self.operations / ("logical-" + name + ".json"))
            expected = self._receipt(name, "logical", sha256=pin, components=[name + "-persistence", name])
            if path.exists():
                if w.read_json(path) != expected:
                    w.fail("migration_source", "Imported logical reservation conflict.")
            else:
                w.write_exclusive(path, expected)
        self.update(active_operation=unresolved[0] if unresolved else None,
                    operation_status="unknown" if unresolved else "complete",
                    migration_status="needs_reconciliation" if len(unresolved) > 1 else None,
                    migration_unresolved_count=len(unresolved))

    def _legacy_unresolved(self, legacy):
        """Derive only the already bounded archive's declared reservations."""
        operations = legacy["operations"]
        unresolved = []
        for name, row in operations.items():
            w.identifier(name, "legacy operation", assignment=True)
            if (not isinstance(row, dict) or not isinstance(row.get("status"), str)
                    or row["status"] not in {"complete", "unknown", "sending"}):
                w.fail("migration_source", "Unsupported legacy reservation; no resume.")
            w.digest_pin(row.get("sha256"))
            if row["status"] != "complete":
                unresolved.append(name)
        for name, pin in legacy.get("claude_operations", {}).items():
            w.identifier(name, "legacy logical operation", assignment=True)
            w.digest_pin(pin)
            if not all(operations.get(component, {}).get("status") == "complete" for component in (name + "-persistence", name)):
                if name not in unresolved:
                    unresolved.append(name)
        return unresolved

    def _legacy_ack(self, legacy, name, row):
        ids = {}
        turn = legacy.get("native_turns", {}).get(name)
        if turn is not None:
            field = "initialization_turn_id" if turn == legacy.get("initialization_turn_id") else "assignment_turn_id"
            ids[field] = w.identifier(turn, "legacy acknowledged turn")
        result = row.get("result", {})
        if isinstance(result, dict) and "thread_id" in result:
            ids["thread_id"] = w.identifier(result["thread_id"], "legacy native thread")
        return ids

    def _check_import_receipts(self, legacy, *, complete_import):
        """Read only exact archive-named files before replacing current control."""
        for name, row in legacy["operations"].items():
            intent = self._op_path(name, "intent.json")
            ack = self._op_path(name, "ack.json")
            terminal = self._op_path(name, "terminal.json")
            if complete_import and not intent.exists():
                w.fail("migration_source", "Finished import lost a declared intent; preserve evidence.")
            if intent.exists() and self._read_receipt(name, "intent", intent) != self._receipt(name, "intent", sha256=row["sha256"]):
                w.fail("migration_source", "Imported payload/intent differs before resume.")
            ids = self._legacy_ack(legacy, name, row)
            if complete_import and ids and not ack.exists():
                w.fail("migration_source", "Finished import lost a declared acknowledgement.")
            if ack.exists() and (not intent.exists() or not ids or self._read_receipt(name, "ack", ack) != self._receipt(name, "ack", ids=ids)):
                w.fail("migration_source", "Imported acknowledgement differs before resume.")
            if complete_import and row["status"] == "complete" and not terminal.exists():
                w.fail("migration_source", "Finished import lost a declared terminal.")
            if terminal.exists():
                if row["status"] != "complete":
                    w.fail("migration_source", "New terminal is outside original import; trusted reconciliation required.")
                record = self.lookup_operation(name)
                if not record or record["status"] != "complete":
                    w.fail("migration_source", "Imported terminal differs before resume.")
                source = row.get("result", {})
                for field in ("thread_id", "turn_id", "session_id"):
                    if isinstance(source, dict) and record["result"].get(field) != source.get(field):
                        w.fail("migration_source", "Imported terminal identity differs from archive.")
                for field in ("public", "text"):
                    if (isinstance(source, dict) and field in source) != (field in record["result"]):
                        w.fail("migration_source", "Imported public field presence differs from archive; no replacement.")
                    if field in record["result"]:
                        descriptor = record["result"][field]
                        text = w.read_public(descriptor, self._op_path(name, "public.txt"))
                        if text != source[field]:
                            w.fail("migration_source", "Imported public body differs from archive.")
                        if (descriptor["completeness"] != "unknown"
                                or descriptor["public_availability"] != ("available" if text.strip() else "empty")):
                            w.fail("migration_source", "Imported public descriptor differs from its source projection.")
        for name, pin in legacy.get("claude_operations", {}).items():
            path = w.plain_control_path(self.operations / ("logical-" + name + ".json"))
            expected = self._receipt(name, "logical", sha256=pin, components=[name + "-persistence", name])
            if (complete_import and not path.exists()) or (path.exists() and w.read_json(path) != expected):
                w.fail("migration_source", "Imported logical reservation differs before resume.")
            for component in expected["components"]:
                if component not in legacy["operations"] and any(self._op_path(component, suffix).exists() for suffix in ("intent.json", "ack.json", "terminal.json", "public.txt")):
                    w.fail("migration_source", "Logical component has newer evidence outside this archive; no replacement.")

    def connection_dir(self):
        self._check_lock()
        return self.directory / ("connection-" + uuid.uuid4().hex)


def check_identity(response, expected, permission_profile, approval=None):
    for key, source in (("model", "model"), ("modelProvider", "native_provider"), ("reasoningEffort", "effort"), ("cwd", "cwd")):
        actual = response.get(key)
        if key == "cwd" and isinstance(actual, str):
            actual = str(w.absolute_path(actual, "Native root"))
        if actual != expected[source]:
            w.fail("native_identity_mismatch", "Native returned model/provider/effort/root differs from frozen role.")
    requested = approval or {"system": "codex", "policy": "on-request", "reviewer": "auto_review"}
    w.actual_approval(requested)
    reviewer = response.get("approvalsReviewer")
    if (not isinstance(response.get("activePermissionProfile"), dict) or response["activePermissionProfile"].get("id") != permission_profile
            or response.get("approvalPolicy") != requested["policy"]
            or (reviewer is not None and (not isinstance(reviewer, str) or reviewer not in w.APPROVAL_REVIEWERS))
            or (requested["policy"] != "never" and reviewer != requested["reviewer"])):
        w.fail("native_policy_mismatch", "Native effective profile/approval route not preserved.")
    result = {key: response.get(key) for key in ("model", "modelProvider", "reasoningEffort", "cwd", "approvalPolicy", "approvalsReviewer")}
    if approval is not None:
        result["requestedApprovalsReviewer"] = requested["reviewer"]
    return result


def claude_identity(event, session_id, model):
    if (event.get("type") != "system" or event.get("subtype") != "init" or event.get("session_id") != session_id
            or event.get("model") != model or event.get("tools") != [] or event.get("mcp_servers", []) != [] or event.get("plugins", []) != []):
        w.fail("claude_identity_mismatch", "Claude init changed UUID/model or exposed tools; brief withheld.")
    return {"session_id": session_id, "model": model, "tools": []}


def qualification(config, spec, expected, roots, tools, binding):
    if "qualification" not in spec or "qualification_sha256" not in spec:
        w.fail("missing_qualification_pin", "Schema1 and Claude require paired qualification and qualification_sha256 pins.")
    raw, path = config.path_context.resolve_pair(spec["qualification"])
    w.protect_path(raw, roots)
    frozen = freeze_file(raw, spec["qualification_sha256"])
    value = w.read_json(path)
    check_frozen(frozen, roots)
    w.object_keys(value, {"schema", "runtime_sha256", "platform", "protocol", "native_provider", "models", "checks"}, "native qualification", {"claude", "binding", "bootstrap", "filesystem_isolation", "recipe"})
    actual = binding.get("context", {}).get("schema") == 2
    schema = 2 if actual else 1
    if actual:
        from native_qualification import REAL_RECIPE
        if value.get("recipe") != REAL_RECIPE:
            w.fail("unqualified_native", "This changed sealed bundle requires freshly bound real-edit qualification.")
    if actual and value.get("filesystem_isolation") is not False:
        w.fail("unqualified_native", "Actual full-access proof must disclaim filesystem isolation.")
    w.digest_pin(value["runtime_sha256"])
    if (type(value["schema"]) is not int or value["schema"] != schema or value["runtime_sha256"].lower() != spec["sha256"].lower() or value["platform"] != w.host_platform()
            or value["protocol"] != spec["protocol"] or value["native_provider"] != expected["native_provider"]):
        w.fail("unqualified_native", "Qualification does not cover these runtime bytes/platform/connection/protocol.")
    if not isinstance(value["models"], list) or {"model": expected["model"], "effort": expected["effort"]} not in value["models"]:
        w.fail("unqualified_model", "Provider-specific native model/effort qualification is missing.")
    if value.get("binding") != binding:
        w.fail("qualification_scope_changed", "Native proof does not bind the exact current context/profiles/modules/helpers/home/environment.")
    required = {"protocol", "identity", "persistence", "no_replay", "ownership"}
    if tools and actual:
        required |= {"task_read_shell", "task_write_patch", "actual_permissions", "tool_environment"}
    elif tools:
        required |= {"initializer_deny_read_shell", "initializer_deny_read_file", "task_deny_read_shell", "task_deny_read_file", "root_confinement", "tool_environment"}
    checks = value["checks"]
    if not isinstance(checks, dict) or not required <= checks.keys() or len(checks) > 32:
        w.fail("unqualified_native", "Required native behavior/permission proof is missing; mocks do not qualify live execution.")
    snapshots, successful_tools = [frozen], {}
    observations = {"protocol": spec["protocol"], "identity": digest(expected),
                    "persistence": "same-session-terminal-after-reconnect", "no_replay": "ambiguous-request-not-replayed",
                    "ownership": "kernel-cleanup-confirmed", "root_confinement": digest(binding["profiles"]),
                    "tool_environment": digest(binding["environment"])}
    if actual:
        observations.update(task_read_shell="successful-exact-shell-read-v2", task_write_patch="successful-native-real-edit-restored-patch-v1",
            actual_permissions=digest({"profiles": binding["profiles"], "approval": binding["context"]["approval"], "roots": binding["context"]["writable_roots"]}))
    for stage in ("initializer", "task"):
        for family in ("shell", "file"):
            observations[stage + "_deny_read_" + family] = "allowed-positive-and-permission-denied-negative"
    for name in required:
        item = checks[name]
        w.object_keys(item, {"expected", "observed", "receipt", "sha256"}, "native check proof")
        if item["expected"] != observations[name] or item["observed"] != observations[name]:
            w.fail("unqualified_native", "Native evidence does not demonstrate the required behavior.")
        raw_receipt, receipt = config.path_context.resolve_pair(item["receipt"])
        w.protect_path(raw_receipt, roots)
        w.digest_pin(item["sha256"])
        record = freeze_file(raw_receipt, item["sha256"])
        evidence = w.read_json(receipt)
        check_frozen(record, roots)
        w.object_keys(evidence, {"schema", "check", "binding", "observation", "native_observations"}, "typed native evidence")
        if (type(evidence["schema"]) is not int or evidence["schema"] != schema or evidence["check"] != name
                or evidence["binding"] != binding or evidence["observation"] != observations[name]):
            w.fail("qualification_scope_changed", "Typed native evidence does not match its check and current proof scope.")
        rows = evidence["native_observations"]
        if not isinstance(rows, list) or not rows or len(rows) > 128 or any(not isinstance(row, dict) for row in rows):
            w.fail("unqualified_native", "Evidence needs bounded observed native protocol/tool/kernel records, not equal strings alone.")
        for row in rows:
            w.object_keys(row, {"channel", "name", "data"}, "native observation record")
            if row["channel"] not in {"rpc", "tool", "kernel", "journal"} or not isinstance(row["data"], dict) or len(row["data"]) > 128:
                w.fail("unqualified_native", "Observation must be a typed bounded public native record.")
            w.identifier(row["name"], "native observation")
            if "reasoning" in row["name"].lower():
                w.fail("unqualified_native", "Reasoning is not qualification evidence.")
        if actual and name in {"task_read_shell", "task_write_patch"}:
            from native_qualification import valid_tool_observation
            family = "shell" if name == "task_read_shell" else "patch"
            valid = [row["data"] for row in rows if row["channel"] == "tool" and valid_tool_observation(row["data"], family, actual=actual)
                     and row["data"]["stage"] == "task" and row["data"]["case"] == "allowed"]
            if len(valid) != 1:
                w.fail("unqualified_native", "Successful exact native tool evidence is required for the actual-rights check.")
            successful_tools[family] = valid[0]
        snapshots.append(record)
    if actual and "bootstrap" not in value:
        w.fail("same_chat_qualification_required", "Actual rights require accepted same-chat bootstrap evidence.")
    if "bootstrap" in value:
        w.object_keys(value["bootstrap"], {"receipt", "acceptance"}, "accepted same-chat bootstrap")
        for reference in value["bootstrap"].values():
            w.object_keys(reference, {"path", "sha256"}, "protected bootstrap reference")
            raw, _ = config.path_context.resolve_pair(reference["path"])
            w.digest_pin(reference["sha256"])
            record = freeze_file(raw, reference["sha256"])
            check_frozen(record, roots)
            snapshots.append(record)
        if actual:
            receipt_path = config.path_context.resolve_pair(value["bootstrap"]["receipt"]["path"])[1]
            bootstrap = w.read_json(receipt_path)
            from native_qualification import validate_restoration
            validate_restoration(bootstrap)
            if (bootstrap.get("schema") != 2 or bootstrap.get("kind") != "native-qualification-observations"
                    or bootstrap.get("filesystem_isolation") is not False or bootstrap.get("binding") != binding
                    or bootstrap.get("status") != "awaiting_independent_acceptance"
                    or bootstrap.get("observations") != [successful_tools[family] for family in ("shell", "patch")]):
                w.fail("unqualified_native", "Actual tool check receipts must bind the exact successful same-chat bootstrap observations.")
    return value, snapshots


def ordinary_session_guard(journal):
    forbidden = sorted(key for key in journal.state if key.startswith("qualification_") or key in {"accepted_bootstrap", "accepted_qualification_sha256"})
    if forbidden:
        w.fail("legacy_qualification_state", "Ordinary schema2 sessions cannot carry qualification journal metadata: " + ", ".join(forbidden))
    if journal.has_unresolved():
        w.fail("operation_unknown", "Prior operation unresolved.")


def require_legacy_unit(journal):
    Journal._reject_retired_unit(journal.state)


def preflight(config_path, workdir, parent_context, *, needs_tools, local_only=False, profile_id=None):
    initial = [freeze_file(config_path), freeze_file(parent_context)]
    manifest = Path(__file__).with_name("native-manifest.json")
    manifest_record = freeze_file(manifest, w.NATIVE_MANIFEST_PIN)
    modules = w.read_json(manifest)
    module_records = [freeze_file(manifest.parent / name, pin) for name, pin in modules.items()]
    module_records.append(freeze_file(w.__file__))
    config = w.load_config(config_path)
    root = w.absolute_path(workdir, "Working root", must_exist=True)
    context = protection_context(config, parent_context, root, tools=needs_tools)
    roots = context["_protection_roots"]
    for record in initial + [manifest_record] + module_records:
        check_frozen(record, roots)
    w.verify_config_paths(config, roots=roots)
    main, reserve = config["roles"]["main_external"], config["roles"]["reserve_primary"]
    if profile_id is None:
        profile_id = main
    if profile_id is None:
        w.fail("missing_profile", "Configure roles.main_external and a native binding.")
    if profile_id not in (main, reserve):
        w.fail("invalid_native_profile", "Native профиль должен быть main_external или настроенным reserve_primary.")
    profile = config["models"][profile_id]
    if config["mode"] == "primary-only":
        w.fail("mode_restriction", "Primary-only mode prohibits external sprint creation.")
    if config["mode"] == "external-only" and profile["provider"] in config["primary_providers"]:
        w.fail("mode_restriction", "External-only запрещает primary reserve на native маршруте.")
    if profile_id == reserve:
        # Eligibility — предложение, не grant, cleanup или разрешение обхода.
        w.select_role(config, "reserve_primary", needs_tools=needs_tools)
    binding = profile.get("chat")
    if not binding:
        w.fail("missing_chat_binding", "External main needs an implemented native chat binding.")
    if profile_id == reserve and profile.get("transport") != "native-chat":
        w.fail("native_capability_mismatch", "Reserve должен иметь действующий native-chat маршрут.")
    spec = dict(config["drivers"][binding["driver"]])
    if needs_tools != (spec["kind"] == "codex"):
        w.fail("native_capability_mismatch", "Selected driver needs Codex tools context or Claude explicit no-tools context.")
    if needs_tools and context.get("schema") != 2 and context["approval"] != {"system": "codex", "policy": "on-request", "reviewer": "auto_review"}:
        w.fail("unsupported_permission_contract", "Native driver cannot preserve the actual parent approval requirement.")
    reference = spec["runtime"]
    if reference.startswith("@runtime:"):
        raw_runtime, executable = w.discover_runtime(config, reference, spec["sha256"], roots=roots)
    else:
        raw_runtime, executable = config.path_context.resolve_pair(reference, purpose="native")
    w.protect_path(raw_runtime, roots)
    w.native_executable(executable)
    if w.file_hash(executable) != spec["sha256"].lower():
        w.fail("pin_mismatch", "Native runtime bytes changed.")
    spec["_runtime"] = str(executable)
    spec["_raw_runtime"] = str(raw_runtime)
    if spec["native_home"] is not None:
        raw_home, native_home = config.path_context.resolve_pair(spec["native_home"])
        w.protect_path(raw_home, roots)
        spec["_native_home"] = str(native_home)
    elif spec["kind"] == "codex":
        raw_home = w.lexical_path(os.environ.get("CODEX_HOME", Path.home() / ".codex"), "Native home")
        w.protect_path(raw_home, roots)
        spec["_native_home"] = str(raw_home.resolve())
    else:
        raw_home = w.lexical_path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"), "Native home")
        w.protect_path(raw_home, roots)
        spec["_native_home"] = str(raw_home.resolve())
    spec["_raw_native_home"] = str(raw_home)
    if not w.absolute_path(raw_home, "Existing configured native home", must_exist=True).is_dir():
        w.fail("missing_native_home", "Native host setup/credentials directory must already exist.")
    native_config_records = []
    if spec["kind"] == "codex":
        if not {"native_base_url", "native_wire_api"} <= spec.keys():
            w.fail("missing_native_endpoint", "Configure separate native_base_url and native_wire_api pins; text protocol does not establish native wire support.")
        connection = config.get("connections", {}).get(profile["provider"])
        if connection and (connection["base_url"] != spec["native_base_url"] or connection["native_provider"] != binding["native_provider"]):
            w.fail("native_provider_mismatch", "Selected native endpoint/provider differs from the trusted profile connection.")
        record = freeze_file(Path(raw_home) / "config.toml")
        check_frozen(record, roots)
        native_config_records.append(record)
        spec["_native_config"] = {"lexical": str(record[0]), "canonical": str(record[1]), "sha256": record[2]}
    catalog_records = []
    if "native_model_catalog" in spec:
        record, spec["_native_model_catalog"] = freeze_model_catalog(config, spec, profile["model"], roots)
        catalog_records.append(record)
    helper_records, helpers = [], {}
    required_helpers = {"codex-command-runner.exe", "codex-windows-sandbox-setup.exe"} if needs_tools and uses_windows_sandbox(context) else set()
    if set(spec.get("native_helpers", {})) != required_helpers:
        w.fail("missing_helper_pins", "Configure exact versioned native sandbox helper pins for this platform.")
    for name, pin in spec.get("native_helpers", {}).items():
        record = freeze_file(Path(raw_runtime).parent / name, pin)
        check_frozen(record, roots)
        helper_records.append(record)
        helpers[name] = {"lexical": str(record[0]), "canonical": str(record[1]), "sha256": record[2]}
    dependency_records, dependencies = [], {}
    for reference, pin in spec.get("native_auth_dependencies", {}).items():
        raw, _ = config.path_context.resolve_pair(reference)
        record = freeze_file(raw, pin)
        check_frozen(record, roots)
        dependency_records.append(record)
        dependencies[reference] = {"lexical": str(record[0]), "canonical": str(record[1]), "sha256": record[2]}
    spec["_native_auth_dependencies"] = dependencies
    if spec["kind"] == "codex":
        effective = spec.get("effective_native_executables", {})
        required = {"main", "runner", "setup"} if uses_windows_sandbox(context) else {"main"}
        if set(effective) != required:
            w.fail("missing_materialized_native_pins", "Configure actual materialized main/runner/setup paths and byte pins for this platform; declarations require separate routing/linkage proof.")
        spec["_effective_native_executables"] = {}
        source_pins = {"main": spec["sha256"], "runner": spec.get("native_helpers", {}).get("codex-command-runner.exe"),
                       "setup": spec.get("native_helpers", {}).get("codex-windows-sandbox-setup.exe")}
        for role, item in effective.items():
            raw, _ = config.path_context.resolve_pair(item["path"], purpose="native")
            record = freeze_file(raw, item["sha256"])
            check_frozen(record, roots)
            if record[2] != source_pins[role].lower():
                w.fail("native_materialization_changed", "Materialized native bytes differ from their pinned source executables.")
            dependency_records.append(record)
            spec["_effective_native_executables"][role] = {"lexical": str(record[0]), "canonical": str(record[1]), "sha256": record[2]}
        record = freeze_file(Path(os.sys.executable).resolve())
        check_frozen(record, roots)
        dependency_records.append(record)
        spec["_effective_native_executables"]["probe_interpreter"] = {"lexical": str(record[0]), "canonical": str(record[1]), "sha256": record[2]}
    expected = {"model": profile["model"], "effort": profile["effort"], "native_provider": binding["native_provider"], "cwd": str(root)}
    frozen_binding = scope_binding(spec, expected, context, initial[1], config.path_context.anchors["workflow_home"][0],
                                   dict(modules, **{"worker.py": module_records[-1][2]}), helpers)
    spec["_binding"] = frozen_binding
    ordinary_codex_schema2 = spec["kind"] == "codex" and context.get("schema") == 2
    if local_only or ordinary_codex_schema2:
        qualified, snapshots = {"checks": {}}, []
    else:
        qualified, snapshots = qualification(config, spec, expected, roots, needs_tools, frozen_binding)
    snapshots += initial + [manifest_record] + module_records + helper_records + native_config_records + catalog_records + dependency_records + [freeze_file(raw_runtime, spec["sha256"]), freeze_file(Path(os.sys.executable).resolve())]
    for field in ("settings",):
        if field in spec:
            raw, path = config.path_context.resolve_pair(spec[field])
            snapshots.append(freeze_file(raw, spec[field + "_sha256"]))
            spec["_" + field] = str(path)
    if spec["kind"] == "claude-code" and not local_only:
        claude = qualified.get("claude", {})
        raw, path = config.path_context.resolve_pair(claude.get("claude_mcp_file", ""))
        spec["_mcp"] = str(path)
        snapshots.append(freeze_file(raw, claude.get("claude_mcp_sha256")))
    def guard():
        w.verify_config_paths(config, roots=roots)
        for record in snapshots:
            check_frozen(record, roots)
        w.protect_path(spec["_raw_native_home"], roots)
        if str(Path(spec["_raw_native_home"]).resolve()) != spec["_native_home"]:
            w.fail("control_changed", "Effective native-home alias changed.")
    guard()
    return config, profile_id, profile, spec, expected, context, qualified, guard


def probe(config_path, workdir, parent_context, linkage_file=None, linkage_sha256=None):
    """Local native configuration/kernel/synthetic-shell checks; NEVER a turn.

    A successful probe cannot qualify provider identity, model file tools or
    persistent inference. Its output is evidence for exactly the listed checks.
    """
    if (linkage_file is None) != (linkage_sha256 is None):
        w.fail("invalid_probe_scope", "Full probe needs both protected linkage-file and linkage-sha256; diagnostic probe needs neither.")
    config, _, _, spec, expected, context, qualified, guard = preflight(config_path, workdir, parent_context, needs_tools=True, local_only=True)
    from native_codex import CodexDriver
    from native_qualification import local_probe_command, fixture_identity
    actual = context.get("schema") == 2
    home = config.path_context.anchors["workflow_home"][0]
    w.protect_path(home, context["_protection_roots"])
    host_path = home / "native-host.json"
    if not host_path.exists():
        try:
            w.write_exclusive(host_path, {"schema": 1, "host": uuid.uuid4().hex})
        except w.WorkflowError as error:
            if error.code != "existing_receipt":
                raise
    host_record = freeze_file(host_path)
    check_frozen(host_record, context["_protection_roots"])
    full = linkage_file is not None
    linkage_record = None
    if full:
        w.digest_pin(linkage_sha256)
        linkage_record = freeze_file(linkage_file, linkage_sha256)
        check_frozen(linkage_record, context["_protection_roots"])
        linkage = w.read_json(linkage_record[1])
        if linkage.get("kind") != "native-tool-linkage" or linkage.get("binding") != spec["_binding"]:
            w.fail("qualification_scope_changed", "Full native probe needs linkage for this exact final binding; independent acceptance is checked before qualification.")
    attempt = uuid.uuid4().hex
    directory = home / "native-probes" / attempt
    directory.mkdir(parents=True, exist_ok=False)
    secret = home / "native-qualification-fixtures" / attempt / "denied.txt" if full else directory / "synthetic-denied.txt"
    if not actual:
        secret.parent.mkdir(parents=True, exist_ok=True)
        with secret.open("xb") as stream:
            stream.write(("workflow-qualification:" + attempt + ":denied\n" if full else "Synthetic noncredential probe " + attempt).encode("ascii"))
    allowed = w.lexical_path(workdir, "Probe root") / (".workflow-qualification-" + attempt + "-allowed.txt" if full else ".workflow-probe-" + attempt)
    with allowed.open("xb") as stream:
        stream.write(("workflow-qualification:" + attempt + ":allowed\n" if full else "Synthetic readable probe").encode("ascii"))
    records, full_checks = {}, []
    fixtures = {case: {"lexical": str(path), "canonical": str(path.resolve()), "sha256": w.file_hash(path), "identity": fixture_identity(path)}
                for case, path in ([("allowed", allowed)] if actual else [("allowed", allowed), ("denied", secret)])}
    def probe_guard():
        guard()
        check_frozen(host_record, context["_protection_roots"])
        if linkage_record:
            check_frozen(linkage_record, context["_protection_roots"])
        for item in fixtures.values():
            raw = Path(item["lexical"])
            if raw.resolve() != Path(item["canonical"]) or w.file_hash(raw) != item["sha256"] or fixture_identity(raw) != item["identity"]:
                w.fail("synthetic_fixture_changed", "Probe fixture identity/content changed; no further native operation.")
    # Journal provides the same physical ownership and generated deny namespace,
    # but probe never allocates a thread or turn or reads auth contents.
    with Journal(home / "native-probe-runs", "local-probe", Path(workdir), attempt, "local-human-probe") as journal:
        journal.guard = probe_guard
        driver = CodexDriver(spec, expected, context, qualified)
        rpc = None
        try:
            rpc = driver._open(journal)
            for stage in ("init", "task"):
                for name, path, expected_code in ([("positive_read", allowed, 0)] if actual else [("positive_read", allowed, 0), ("deny_read_shell", secret, 41)]):
                    probe_guard()
                    command = local_probe_command(path.resolve())
                    result = rpc.call("command/exec", {"command": command,
                                     "cwd": str(Path(workdir).resolve()), "permissionProfile": driver.names[stage],
                                     "timeoutMs": 15000, "outputBytesCap": 1024})
                    observed = result.get("exitCode")
                    if observed != expected_code:
                        w.fail("native_local_probe_failed", "Synthetic native shell confinement/readability check failed; no model called.")
                    records[stage + "_" + name] = {"expected": str(expected_code), "observed": str(observed)}
                    full_checks.append({"stage": stage, "case": "allowed" if expected_code == 0 else "denied", "profile": driver.names[stage],
                                        "target": str(path.resolve()), "command_sha256": digest(command), "exit_code": observed,
                                        "sentinel": "native-positive-read" if expected_code == 0 else "native-PermissionError"})
        finally:
            try:
                if rpc is not None:
                    driver._close(rpc, journal)
            finally:
                if not full or len(full_checks) != (2 if actual else 4) or not isinstance(journal.state.get("cleanup"), dict) or journal.state["cleanup"].get("empty") is not True:
                    allowed.unlink(missing_ok=True)
        receipt = {"schema": 2 if actual else 1, "runtime_sha256": spec["sha256"], "platform": w.host_platform(),
                   "protocol": spec["protocol"], "checks": records, "cleanup": journal.state.get("cleanup"),
                   "inference_started": False, "provider_access_confirmed": False, "file_tool_confinement_confirmed": False}
        if full:
            probe_guard()
            if not isinstance(journal.state.get("cleanup"), dict) or journal.state["cleanup"].get("empty") is not True:
                w.fail("cleanup_unknown", "Full probe requires actual owned kernel cleanup; no qualification evidence produced.")
            receipt = {"schema": 2 if actual else 1, "kind": "native-local-probe", "author": "native-local-probe-runner", "binding": spec["_binding"],
                       "root": {"lexical": str(w.lexical_path(workdir, "Probe root")), "canonical": expected["cwd"]}, "attempt": attempt,
                       "profile_names": driver.names, "fixtures": fixtures, "checks": full_checks, "cleanup": journal.state["cleanup"],
                       "inference_started": False, "linkage": {"path": str(linkage_record[0]), "sha256": linkage_record[2]}}
        if actual:
            receipt["filesystem_isolation"] = False
        receipt_path = directory / "receipt.json"
        w.write_exclusive(receipt_path, receipt)
        return {"status": "local_probe_passed", "receipt": str(receipt_path), "sha256": w.file_hash(receipt_path),
                "inference_started": False, "next": "Independently review receipt; model file-tool, identity and persistence gates remain unconfirmed."}


def authorize(path, root, sprint, parent, profile_id, profile, brief_digest, operation, operation_id):
    doc = w.read_json(path)
    w.object_keys(doc, {"schema_version", "source", "authorizations"}, "trusted native scope")
    if type(doc["schema_version"]) is not int or doc["schema_version"] != 1 or not isinstance(doc["authorizations"], list) or len(doc["authorizations"]) > 128:
        w.fail("invalid_authorization", "Native authorization needs bounded schema1 records.")
    w.object_keys(doc["source"], {"kind", "reference", "text"}, "trusted human source")
    if doc["source"]["kind"] != "human_instruction":
        w.fail("invalid_authorization", "Human evidence provenance must be established by the trusted caller.")
    for field in ("reference", "text"):
        w.bounded_text(doc["source"][field], "human evidence")
    fields = {"kind", "workdir", "sprint_id", "parent_chat_id", "profile", "provider", "brief_sha256", "operation", "operation_id"}
    matched = False
    for record in doc["authorizations"]:
        if not isinstance(record, dict) or record.get("kind") not in {"native-sprint", "top"}:
            w.fail("invalid_authorization", "Native authorization records must be exact native-sprint or separate top scopes.")
        if record["kind"] == "top":
            w.object_keys(record, {"kind", "assignment_id", "workdir", "role", "profile"}, "separate top scope")
            continue
        if isinstance(record, dict) and record.get("kind") == "native-sprint":
            w.object_keys(record, fields, "native sprint scope")
            if (w.absolute_path(record["workdir"], "Authorized root") == root and record["sprint_id"] == sprint and record["parent_chat_id"] == parent
                    and record["profile"] == profile_id and record["provider"] == profile["provider"] and record["brief_sha256"] == brief_digest
                    and record["operation"] == operation and record["operation_id"] == operation_id):
                matched = True
    if matched:
        return
    w.fail("missing_authorization", "Human evidence must cover exact sprint/profile/provider/brief/operation/parent scope.")


def native_top_assignment(root, sprint, parent, operation, operation_id, profile):
    return "native-" + digest({"workdir": str(w.absolute_path(root, "Native consent root")), "sprint_id": sprint,
                              "parent_chat_id": parent, "operation": operation, "operation_id": operation_id, "profile": profile})


def run(config_path, workdir, sprint, parent, authorization_file, parent_context, *, command="create", brief=None,
        operation_id="create", needs_tools=True, expected_turn_id=None, driver_factory=None, profile_id=None):
    if command in {"steer", "interrupt"}:
        w.fail("live_control_unavailable", "Foreground owner holds the exact journal; live CLI control is unavailable. Use terminal same-ID follow-up after completion.")
    if command not in {"create", "send", "status", "reconcile"}:
        w.fail("unsupported_operation", "Unknown native worker operation.")
    config, profile_id, profile, spec, expected, context, qualified, guard = preflight(config_path, workdir, parent_context, needs_tools=needs_tools, profile_id=profile_id)
    root, roots = Path(expected["cwd"]), context["_protection_roots"]
    home = config.path_context.anchors["workflow_home"][0]
    for control in (home, authorization_file):
        w.protect_path(control, roots)
    text = ""
    if brief is not None:
        with Path(brief).open("rb") as stream:
            raw = stream.read(512 * 1024 + 1)
        if len(raw) > 512 * 1024:
            w.fail("oversize_brief", "Sprint brief exceeds bounded limit.")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeError:
            w.fail("invalid_brief", "Sprint brief must be UTF-8.")
        w.bounded_text(text, "brief", 512 * 1024)
    brief_digest = hashlib.sha256(text.encode()).hexdigest()
    auth_record = freeze_file(authorization_file)
    check_frozen(auth_record, roots)
    if command != "status":
        authorize(authorization_file, root, sprint, parent, profile_id, profile, brief_digest, command, operation_id)
        if w.needs_consent(config, profile_id):
            document = w.read_json(authorization_file)
            assignment = native_top_assignment(root, sprint, parent, command, operation_id, profile_id)
            try:
                w.require_authorization(document, "top", root, assignment_id=assignment, role="main_external", profile=profile_id)
            except w.WorkflowError as error:
                if error.code == "missing_authorization":
                    w.fail("missing_authorization", "Separate native top scope requires assignment_id=" + assignment + ", role=main_external and this exact profile/root.")
                raise
    check_frozen(auth_record, roots)
    host_path = home / "native-host.json"
    if not host_path.exists():
        try:
            w.write_exclusive(host_path, {"schema": 1, "host": uuid.uuid4().hex})
        except w.WorkflowError as error:
            if error.code != "existing_receipt":
                raise
    host_doc = w.read_json(host_path)
    w.object_keys(host_doc, {"schema", "host"}, "stable host identity")
    if host_doc["schema"] != 1:
        w.fail("invalid_host", "Invalid stable host identity.")
    if driver_factory is None:
        if spec["kind"] == "codex":
            from native_codex import CodexDriver
            driver_factory = CodexDriver
        else:
            from native_claude import ClaudeDriver
            driver_factory = ClaudeDriver
    with Journal(home / "native-runs", host_doc["host"], root, sprint, parent) as journal:
        def frozen_guard():
            guard()
            check_frozen(auth_record, roots)
            w.protect_path(journal.directory, roots)
        journal.guard = frozen_guard
        frozen_guard()
        if command in {"create", "send"} and spec["kind"] == "codex" and context.get("schema") == 2:
            ordinary_session_guard(journal)
        selected = {"profile": profile_id, "binding": profile["chat"], "expected": expected, "runtime_sha256": spec["sha256"],
                    "permission_identity": spec["_binding"]}
        if "selected" in journal.state and journal.state["selected"] != selected:
            w.fail("sprint_identity_changed", "Existing sprint binding is immutable; reconcile the original chat.")
        journal.update(selected=selected)
        if context.get("schema") == 2:
            spec["_qualification_config"] = config
        driver = driver_factory(spec, expected, context, qualified)
        if command == "create":
            if journal.state.get("thread_id") or journal.has_operations():
                w.fail("sprint_exists", "Sprint has native state; status/reconcile instead of create.")
            w.atomic_json(journal.directory / "brief.json", {"sha256": brief_digest, "text": text})
            driver.create(journal, text)
        elif command == "send":
            legacy_acceptance = journal.state.get("qualification_status") == "awaiting_independent_acceptance"
            if (spec["kind"] != "codex" or context.get("schema") != 2) and (context.get("schema") == 2 or legacy_acceptance):
                from native_qualification import accept_qualification
                accept_qualification(config, spec, expected, context, journal, qualified)
            driver.send(journal, text, operation_id)
        elif command == "steer":
            driver.steer(journal, text, operation_id, expected_turn_id)
        elif command == "interrupt":
            driver.interrupt(journal, operation_id, expected_turn_id)
        elif command == "status":
            driver.status(journal)
        elif command == "reconcile":
            if not hasattr(driver, "reconcile"):
                w.fail("native_reconciliation_required", "Driver cannot prove ambiguous outcome automatically; retain original session and request trusted-owner resolution.")
            driver.reconcile(journal)
        else:
            w.fail("unsupported_operation", "Unsupported native operation.")
        return {key: journal.state.get(key) for key in ("thread_id", "initialization_turn_id", "assignment_turn_id", "backend_persistence", "client_visibility",
                "operation_status", "last_turn_status", "actual_serving_model", "observed_native_profile")} | {"live_steer": False, "live_interrupt": False, "live_cli_status": False}
