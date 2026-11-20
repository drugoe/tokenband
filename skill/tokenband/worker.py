#!/usr/bin/env python3
"""Portable workflow control and bounded OpenAI-compatible text-only transport.

Only explicit built-in text dispatch reads a protected credential reference.
Native sprint commands send explicitly scoped persistent turns through pinned
drivers. This CLI never launches fallback or fabricates approval answers.
User authorization records must originate from a trusted human;
validating their structure is not authenticating the human or bypassing approval.
"""
from __future__ import annotations

import argparse
import codecs
import copy
from contextlib import contextmanager
from datetime import timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from types import MappingProxyType
import urllib.error
import urllib.parse
import urllib.request

MAX_JSON = 2 * 1024 * 1024
MAX_LINE = 1024 * 1024
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}\Z")
ASSIGNMENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
MODES = {"primary-budget-saving", "primary-only", "external-only"}
ROLES = {"orchestrator", "top_primary", "reserve_primary", "main_external"}
STAGES = {"ordinary", "architecture", "critical", "optional_top"}
RPC_METHODS = {"initialize", "thread/start", "thread/list", "thread/read"}
MAX_KEY = 8192
TEXT_TERMINAL_STATUSES = {"text_completed", "text_incomplete", "text_terminal_unknown", "text_empty", "text_content_unavailable", "text_failed"}
_INVALID_OPTIONAL_NUMBER = object()
TEXT_INACTIVITY_TIMEOUT = 300
ANCHORS = {"workflow_home", "skill", "config", "home"}
RUNTIME_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
NATIVE_MANIFEST_PIN = "f7115e151dd286861637cf55b4e70feb32b088d068817aa16bfd5cdb7ca1f184"


def native_module():
    """Verify the closed native bundle before importing any of its code."""
    import importlib.util
    root = Path(__file__).parent
    manifest_path = root / "native-manifest.json"
    if file_hash(manifest_path) != NATIVE_MANIFEST_PIN:
        fail("native_bundle_changed", "Native manifest differs from this reviewed worker; install the sealed bundle.")
    manifest = read_json(manifest_path)
    expected = {"native_sprint.py", "native_transport.py", "native_owned.py", "native_codex.py", "native_claude.py", "native_qualification.py"}
    if set(manifest) != expected:
        fail("native_bundle_changed", "Native manifest must contain exactly the bundled modules.")
    sources = {}
    for name, pin in manifest.items():
        digest_pin(pin)
        path = root / name
        source = path.read_bytes()
        if path.is_symlink() or hashlib.sha256(source).hexdigest() != pin:
            fail("native_bundle_changed", "Native module bytes differ from the sealed bundle.")
        sources[name] = source
    if file_hash(manifest_path) != NATIVE_MANIFEST_PIN:
        fail("native_bundle_changed", "Native manifest changed during verification.")
    # Isolated Python deliberately has no script directory on sys.path. Load only
    # the fully verified closed bundle; do not add a directory search path.
    for module_name in ("native_transport", "native_sprint", "native_codex", "native_claude", "native_qualification"):
        path = root / (module_name + ".py")
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            exec(compile(sources[module_name + ".py"], str(path), "exec"), module.__dict__)
        except BaseException:
            sys.modules.pop(module_name, None)
            raise
    return sys.modules["native_sprint"]


def text_responses_module():
    """Load the single bundled Responses transport next to this worker.

    It is plain stdlib-only Python with no private host/runtime import, no
    second driver, framework, service, daemon or queue. The module is loaded
    once per dispatch so that the exception class raised by the client is the
    same object this worker catches.
    """
    import importlib.util
    path = Path(__file__).resolve().parent / "text_responses.py"
    spec = importlib.util.spec_from_file_location("tokenband_text_responses", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["tokenband_text_responses"] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop("tokenband_text_responses", None)
        raise
    return module


class WorkflowError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def fail(code, message):
    raise WorkflowError(code, message)


def host_platform():
    if sys.platform == "win32":
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    fail("unsupported_host", "This worker supports Windows and Linux hosts.")


def identifier(value, label="identifier", assignment=False):
    pattern = ASSIGNMENT_RE if assignment else ID_RE
    if not isinstance(value, str) or not pattern.fullmatch(value):
        fail("invalid_identifier", f"Invalid {label}; use a bounded identifier without spaces or control characters.")
    return value


def bounded_text(value, label, limit=8192):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        fail("invalid_text", f"Invalid bounded {label}.")
    return value


def object_keys(value, required, label, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        fail("invalid_schema", f"Invalid {label} structure: required fields missing or unknown fields present.")


def string_list(value, label):
    if not isinstance(value, list) or len(value) > 128:
        fail("invalid_schema", f"Invalid {label} list.")
    for entry in value:
        identifier(entry, label)
    if len(set(value)) != len(value):
        fail("invalid_schema", f"Duplicate entries in {label}.")


def absolute_path(value, label, must_exist=False):
    if not isinstance(value, (str, Path)):
        fail("invalid_path", f"Invalid {label} path.")
    text = str(value)
    if not text or len(text) > 32768 or any(ord(c) < 32 for c in text):
        fail("invalid_path", f"Invalid {label} path.")
    path = Path(text).expanduser()
    if not path.is_absolute():
        fail("invalid_path", f"{label} must be an absolute host path.")
    try:
        return path.resolve(strict=must_exist)
    except (OSError, RuntimeError):
        fail("missing_path", f"{label} path is unavailable; configure the host prerequisite.")


def is_within(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def require_outside(path, workdir):
    path = absolute_path(path, "Protected artifact")
    root = absolute_path(workdir, "Working root", must_exist=True)
    if is_within(path, root):
        fail("unprotected_artifact", "Config, adapter and control artifacts must be outside the working root; native adapters enforce stronger permission boundaries.")
    return path


def json_pairs(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            fail("duplicate_json_key", "Duplicate JSON keys are not permitted.")
        data[key] = value
    return data


def read_json(path):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_JSON + 1)
        if len(raw) > MAX_JSON:
            fail("oversize_json", "JSON artifact exceeds the bounded size limit.")
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=json_pairs,
                          parse_constant=lambda value: fail("invalid_json", "Nonfinite JSON numbers are not permitted."))
    except WorkflowError:
        raise
    except (OSError, UnicodeError, ValueError):
        fail("invalid_json", "JSON artifact is missing, unreadable or malformed; contents are not logged.")


def file_hash(path):
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                digest.update(block)
    except OSError:
        fail("missing_runtime", "Pinned local runtime artifact is unavailable.")
    return digest.hexdigest()


def bounded_key_hash(path):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_KEY + 3)
    except OSError:
        fail("credential_unavailable", "Protected credential reference is unavailable; contents are suppressed.")
    if len(raw) > MAX_KEY + 2:
        fail("invalid_credential", "Credential file exceeds the bounded single-line size limit.")
    return hashlib.sha256(raw).hexdigest()


def digest_pin(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", value):
        fail("invalid_pin", "Runtime SHA256 must be a 64-character hexadecimal digest.")


def validate_path_reference(value, *, purpose="path", ordinary_only=False):
    if not isinstance(value, (str, Path)):
        fail("invalid_path_reference", "Path reference must be a bounded string.")
    value = str(value)
    if not value or len(value) > 32768 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        fail("invalid_path_reference", "Invalid bounded path reference.")
    if not value.startswith("@"):
        if ordinary_only or not Path(value).is_absolute():
            fail("invalid_path_reference", "Configure an anchored reference or legacy absolute host path.")
        return "absolute"
    if value == "@python":
        if purpose != "interpreter" or ordinary_only:
            fail("invalid_path_reference", "Current-Python reference is valid only for an adapter interpreter.")
        return "python"
    if value.startswith("@runtime:"):
        name = value[len("@runtime:"):]
        if purpose != "native" or ordinary_only or not RUNTIME_ID_RE.fullmatch(name):
            fail("invalid_path_reference", "Declared runtime reference is valid only in a pinned native executable field.")
        return "runtime"
    anchor, *segments = value[1:].split("/")
    if anchor not in ANCHORS:
        fail("invalid_path_reference", "Unknown path anchor.")
    for segment in segments:
        if (not segment or segment in {".", ".."} or any(c in segment for c in '\\:*?[]')
                or (host_platform() == "windows" and
                    (any(c in segment for c in '<>"|') or segment.endswith((".", " "))
                     or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", segment)))):
            fail("invalid_path_reference", "Reference suffix contains an invalid segment or anchor escape.")
    return "anchor"


def workflow_home(home=None):
    if "WORKFLOW_HOME" in os.environ:
        value = os.environ["WORKFLOW_HOME"]
        validate_path_reference(value)
        if value.startswith("@"):
            fail("invalid_workflow_home", "WORKFLOW_HOME must be an absolute host path.")
        return lexical_path(value, "Workflow home")
    try:
        default = lexical_path((Path.home() if home is None else home) / ".tokenband", "Workflow home")
    except RuntimeError:
        fail("missing_home", "Current home is unavailable; configure an absolute WORKFLOW_HOME prerequisite.")
    sentinel = default / "PRESERVE-EXISTING-STATE"
    if sentinel.exists() or sentinel.is_symlink():
        fail("existing_state_binding", "Set explicit WORKFLOW_HOME to the original state home specified in the user-level instructions before invoking this worker.")
    return default


class PathContext:
    """Fixed anchors with lexical paths retained for later physical protection."""
    __slots__ = ("anchors", "python")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            fail("immutable_path_context", "Invocation path context cannot be changed after creation.")
        object.__setattr__(self, name, value)

    def __init__(self, config_file, *, home=None, module_file=None):
        config = lexical_path(config_file, "Config location")
        try:
            current_home = lexical_path(Path.home() if home is None else home, "Home")
        except RuntimeError:
            current_home = None
        module = absolute_path(__file__ if module_file is None else module_file, "Worker module", must_exist=True)
        neutral = workflow_home(current_home) if current_home is not None or "WORKFLOW_HOME" in os.environ else None
        raw = {"home": current_home, "workflow_home": neutral, "config": config.parent, "skill": module.parent}
        self.anchors = MappingProxyType({name: (path, absolute_path(path, "Anchor")) if path is not None else None
                                        for name, path in raw.items()})
        self.python = str(sys.executable)

    def resolve_pair(self, value, *, purpose="path"):
        kind = validate_path_reference(value, purpose=purpose)
        value = str(value)
        if kind == "runtime":
            fail("runtime_pin_required", "Runtime discovery requires its native consumer's reviewed pin and protection context.")
        if kind == "absolute":
            raw = lexical_path(value, "Legacy configured path")
            return raw, absolute_path(raw, "Legacy configured path")
        if kind == "python":
            if not self.python or sys.version_info < (3, 10):
                fail("missing_python", "Current supported Python interpreter is unavailable.")
            raw = lexical_path(self.python, "Current Python")
            return raw, native_executable(raw)
        anchor, *segments = value[1:].split("/")
        if self.anchors[anchor] is None:
            fail("missing_home", "Requested home anchor is unavailable; configure the real host prerequisite.")
        raw_root, physical_root = self.anchors[anchor]
        if absolute_path(raw_root, "Anchor") != physical_root:
            fail("snapshot_changed", "Path anchor changed after context creation.")
        raw = raw_root.joinpath(*segments)
        for candidate in (raw, *list(raw.parents)[:len(segments)]):
            if not is_within(absolute_path(candidate, "Anchored path"), physical_root):
                fail("anchor_escape", "Referenced path or an intermediate alias escapes its physical anchor.")
        return raw, absolute_path(raw, "Anchored path")

    def resolve(self, value, *, purpose="path"):
        return self.resolve_pair(value, purpose=purpose)[1]


class ResolvedConfig(dict):
    """Configuration keys stay strict; host-resolution records are not JSON keys."""
    def __init__(self, cfg, context):
        super().__init__(copy.deepcopy(cfg))
        self.path_context = context
        self.path_records = []
        self.native_records = {}
        self.legacy_absolute_paths = []

    def resolve_field(self, obj, field, purpose, label):
        reference = obj[field]
        if validate_path_reference(reference, purpose=purpose) == "runtime":
            return  # Optional native integration discovery is deferred until used.
        raw, canonical = self.path_context.resolve_pair(reference, purpose=purpose)
        self.path_records.append((str(reference), purpose, raw, canonical))
        if not str(reference).startswith("@"):
            self.legacy_absolute_paths.append(label)
        obj[field] = str(canonical)


def verify_config_paths(cfg, *, roots=()):
    if not isinstance(cfg, ResolvedConfig):
        return
    for reference, purpose, raw, canonical in cfg.path_records:
        current_raw, current = cfg.path_context.resolve_pair(reference, purpose=purpose)
        if current_raw != raw or current != canonical:
            fail("snapshot_changed", "Configured path resolution changed after selection; no rediscovery or replay.")
        if roots:
            protect_path(raw, roots)
            protect_path(canonical, roots)


def native_executable(path):
    path = absolute_path(path, "Native runtime", must_exist=True)
    if not path.is_file() or path.suffix.lower() in {".cmd", ".bat", ".ps1", ".py", ".sh"}:
        fail("invalid_runtime", "Runtime must be a regular native host image; script/shim execution is forbidden.")
    try:
        with path.open("rb") as stream:
            header = stream.read(64)
            if host_platform() == "windows":
                if len(header) != 64 or header[:2] != b"MZ":
                    fail("invalid_runtime", "Native Windows runtime must be a PE image.")
                offset = struct.unpack_from("<I", header, 60)[0]
                if not 64 <= offset <= 1024 * 1024:
                    fail("invalid_runtime", "Invalid bounded native PE header.")
                stream.seek(offset)
                if stream.read(4) != b"PE\0\0":
                    fail("invalid_runtime", "Native Windows runtime must be a PE image.")
            elif (len(header) < 52 or header[:4] != b"\x7fELF" or header[4] not in (1, 2)
                  or header[5] not in (1, 2) or header[6] != 1
                  or int.from_bytes(header[16:18], "little" if header[5] == 1 else "big") not in (2, 3)
                  or not os.access(path, os.X_OK)):
                fail("invalid_runtime", "Native Linux runtime must be an executable ELF image.")
    except OSError:
        fail("missing_runtime", "Native runtime is unavailable; no raw filesystem error is logged.")
    return path


def discover_runtime(cfg, reference, expected_hash, *, roots=()):
    digest_pin(expected_hash)
    runtime = cfg["runtimes"][reference[len("@runtime:"):]]
    context = cfg.path_context
    seen, inspected = set(), 0
    def count_candidate():
        nonlocal inspected
        inspected += 1
        if inspected > 128:
            fail("runtime_discovery_limit", "Native discovery exceeded its bounded candidate scan.")
    def consider(raw, canonical):
        if canonical in seen:
            return None
        seen.add(canonical)
        try:
            if roots:
                protect_path(raw, roots)
            native_executable(canonical)
            if file_hash(canonical) != expected_hash.lower():
                return None
        except WorkflowError:
            return None
        return raw, canonical
    for candidate in runtime["candidates"]:
        count_candidate()
        raw, canonical = context.resolve_pair(candidate)
        result = consider(raw, canonical)
        if result:
            cfg.path_records.append((candidate, "path", raw, canonical))
            return result
    directories = os.environ.get("PATH", "").split(os.pathsep)
    if len(directories) > 128:
        fail("runtime_discovery_limit", "Native discovery exceeded its bounded PATH directory scan.")
    for directory in directories:
        if not directory or not Path(directory).is_absolute():
            continue
        raw_directory = lexical_path(directory, "Installed runtime directory")
        try:
            if roots:
                protect_path(raw_directory, roots)
        except WorkflowError:
            continue
        for command in runtime["commands"]:
            count_candidate()  # Missing files and aliases consume scan budget too.
            # Absolute path argument prevents which from consulting cwd implicitly
            # on Windows; only this already-filtered directory is searched.
            found = shutil.which(str(raw_directory / command), path=str(raw_directory))
            if found:
                result = consider(lexical_path(found, "Discovered runtime"), absolute_path(found, "Discovered runtime"))
                if result:
                    cfg.path_records.append((str(result[0]), "path", result[0], result[1]))
                    return result
    fail("missing_native_runtime", "No configured protected native candidate matches the reviewed pin; install/seed that prerequisite, never a shim.")


def validate_config(cfg):
    object_keys(cfg, {"schema_version", "mode", "human_language", "primary_providers", "models", "roles", "external_order", "adapters", "app_server"}, "user config", {"connections", "runtimes", "drivers", "internal_language"})
    if type(cfg["schema_version"]) is not int or cfg["schema_version"] != 1:
        fail("invalid_version", "Unsupported config schema_version; expected 1.")
    if not isinstance(cfg["mode"], str) or cfg["mode"] not in MODES:
        fail("invalid_config", "Configure a supported mode.")
    identifier(cfg["human_language"], "human_language")
    if "internal_language" in cfg:
        identifier(cfg["internal_language"], "internal_language")
    string_list(cfg["primary_providers"], "primary providers")
    string_list(cfg["external_order"], "external order")
    for group in ("models", "adapters", "connections", "runtimes"):
        if group in {"connections", "runtimes"} and group not in cfg:
            continue
        if not isinstance(cfg[group], dict) or len(cfg[group]) > 128:
            fail("invalid_schema", f"Invalid {group} mapping.")
        for name in cfg[group]:
            identifier(name, group)
            if group == "runtimes" and not RUNTIME_ID_RE.fullmatch(name):
                fail("invalid_runtime_id", "Runtime IDs must be bounded bare identifiers.")
    for runtime in cfg.get("runtimes", {}).values():
        object_keys(runtime, {"candidates", "commands"}, "runtime discovery")
        candidates, commands = runtime["candidates"], runtime["commands"]
        if (not isinstance(candidates, list) or not isinstance(commands, list)
                or len(candidates) + len(commands) > 128):
            fail("invalid_runtime_discovery", "Runtime candidates and commands must be bounded lists.")
        for candidate in candidates:
            validate_path_reference(candidate, ordinary_only=True)
        for command in commands:
            if not isinstance(command, str) or not RUNTIME_ID_RE.fullmatch(command):
                fail("invalid_runtime_discovery", "Discovery commands must be bare executable names without arguments.")
        if len(set(candidates)) != len(candidates) or len(set(commands)) != len(commands):
            fail("invalid_runtime_discovery", "Runtime discovery entries must not contain duplicates.")
    object_keys(cfg["roles"], ROLES, "roles")
    for connection in cfg.get("connections", {}).values():
        object_keys(connection, {"base_url", "native_provider"}, "connection",
                    {"api_key_env", "api_key_file", "protocol"})
        identifier(connection["native_provider"], "native provider")
        connection_url(connection)
        if connection.get("protocol", "openai-chat") not in {"openai-chat", "responses"}:
            fail("unsupported_protocol", "This protocol requires a separately reviewed host adapter.")
        if ("api_key_env" in connection) == ("api_key_file" in connection):
            fail("invalid_credential_reference", "Configure exactly one existing environment or protected file credential reference.")
        if "api_key_env" in connection:
            name = connection["api_key_env"]
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", name):
                fail("invalid_credential_reference", "Environment credential reference must be a bounded variable name.")
        else:
            validate_path_reference(connection["api_key_file"])
    for name, adapter in cfg["adapters"].items():
        object_keys(adapter, {"interpreter", "script", "sha256", "platform", "reviewed", "owns_kernel_cleanup", "preserves_parent_permissions"}, "adapter")
        for key in ("interpreter", "script"):
            validate_path_reference(adapter[key], purpose="interpreter" if key == "interpreter" else "path")
        digest_pin(adapter["sha256"])
        if not isinstance(adapter["platform"], str) or adapter["platform"] not in {"windows", "linux"}:
            fail("invalid_platform", "Adapter platform must be windows or linux.")
        for flag in ("reviewed", "owns_kernel_cleanup", "preserves_parent_permissions"):
            if adapter[flag] is not True:
                fail("unreviewed_adapter", "Adapters must declare reviewed permission preservation and owned kernel cleanup.")
    for name, model in cfg["models"].items():
        object_keys(model, {"provider", "model", "effort", "transport", "adapter", "requires_consent"}, "model profile", {"chat"})
        for field in ("provider", "model", "effort", "transport"):
            identifier(model[field], "profile " + field)
        if type(model["requires_consent"]) is not bool:
            fail("invalid_config", "requires_consent must be a boolean.")
        adapter = model["adapter"]
        if adapter is not None:
            identifier(adapter, "adapter reference")
        if adapter is not None and adapter not in cfg["adapters"]:
            fail("missing_adapter", "A model profile refers to an undeclared reviewed adapter.")
        primary = model["provider"] in cfg["primary_providers"]
        builtin = model["transport"] == "text-api" and adapter is None
        native_chat = model["transport"] == "native-chat" and adapter is None and "chat" in model
        if builtin and model["provider"] not in cfg.get("connections", {}):
            fail("missing_connection", "Built-in text profiles require a declared protected connection.")
        if adapter is None and not primary and not builtin and not native_chat:
            fail("missing_adapter", "External profiles require a reviewed host adapter.")
        if adapter is None and model["transport"] != "desktop" and not builtin and not native_chat:
            fail("invalid_transport", "Profiles without adapters must use desktop transport.")
        if adapter is not None and model["transport"] == "desktop":
            fail("invalid_transport", "Desktop profiles cannot dispatch through a host adapter.")
    for role, profile_id in cfg["roles"].items():
        if profile_id is None:
            continue
        identifier(profile_id, "role profile")
        if profile_id not in cfg["models"]:
            fail("missing_profile", "A role refers to an undeclared model profile.")
        primary = cfg["models"][profile_id]["provider"] in cfg["primary_providers"]
        if (role == "main_external") == primary:
            fail("invalid_role", "Primary roles require primary profiles; main_external requires an external profile.")
    for profile_id in cfg["external_order"]:
        if profile_id not in cfg["models"] or cfg["models"][profile_id]["provider"] in cfg["primary_providers"]:
            fail("invalid_external_pool", "External order must contain declared external profiles only.")
    main = cfg["roles"]["main_external"]
    if main is not None and main not in cfg["external_order"]:
        fail("invalid_external_pool", "main_external must be included in external_order.")
    server = cfg["app_server"]
    if server is not None:
        object_keys(server, {"executable", "sha256"}, "app_server")
        kind = validate_path_reference(server["executable"], purpose="native")
        if kind == "runtime" and server["executable"][len("@runtime:"):] not in cfg.get("runtimes", {}):
            fail("missing_runtime_reference", "Native executable refers to an undeclared runtime.")
        digest_pin(server["sha256"])
    if "drivers" in cfg or any("chat" in value for value in cfg["models"].values()):
        native_module().validate_driver_config(cfg)
    return cfg


def default_config_path():
    # Keep the lexical path: resolving here would hide writable junction/symlink
    # ancestors before dispatch's trusted all-root physical protection checks.
    return workflow_home() / "workflow-config.json"


def load_config(path, *, context=None):
    cfg = validate_config(read_json(path))
    result = ResolvedConfig(cfg, context or PathContext(path))
    for name, adapter in result["adapters"].items():
        result.resolve_field(adapter, "interpreter", "interpreter", "adapter interpreter")
        result.resolve_field(adapter, "script", "path", "adapter script")
    for connection in result.get("connections", {}).values():
        if "api_key_file" in connection:
            result.resolve_field(connection, "api_key_file", "path", "credential reference")
    if result["app_server"] is not None:
        result.resolve_field(result["app_server"], "executable", "native", "native runtime")
    return result


def fsync_directory(path):
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def json_bytes(data):
    raw = (json.dumps(data, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_JSON:
        fail("oversize_json", "Encoded JSON exceeds its reader bound; no write permitted.")
    return raw


def plain_control_path(path):
    """Local protected paths only; inherited permissions/ACLs exclude substitution.

    No network filesystem or privileged path-race qualification is inferred.
    """
    import stat
    raw = Path(os.path.abspath(str(path)))
    if os.name == "nt":
        text = str(raw)
        if text.startswith("\\\\") or ":" in text[2:]:
            fail("unsafe_state", "UNC/device/alternate-stream control paths are unsupported.")
    for part in (raw, *raw.parents):
        stem = part.name.split(".")[0].upper()
        if part.name.endswith((".", " ")) or re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", stem):
            fail("unsafe_state", "Nonportable device/ambiguous control filename; no effect permitted.")
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        reparse = getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)) or reparse
                or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)):
            fail("unsafe_state", "Control path contains an alias, reparse point or multi-link file.")
    return raw


def make_control_directory(path):
    """Publish newly created directory ancestry before an external effect."""
    path = plain_control_path(path)
    missing, parent = [], path
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    for created in reversed(missing):
        fsync_directory(created.parent)
    return path


def require_storage(path, possible_bytes):
    import shutil
    ancestor = plain_control_path(path)
    while not ancestor.exists():
        ancestor = ancestor.parent
    if shutil.disk_usage(ancestor).free < possible_bytes:
        fail("storage_full", "Insufficient observed space before dispatch; retain reservations.")


def write_exclusive(path, data):
    raw = json_bytes(data)
    path = plain_control_path(path)
    make_control_directory(path.parent)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        fail("existing_receipt", "An existing assignment receipt blocks duplicate launch; reconcile with its owned runtime.")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            if stream.write(raw) != len(raw):
                raise OSError("Short write; publication is incomplete.")
            stream.flush()
            os.fsync(stream.fileno())
        fsync_directory(path.parent)
    except Exception:
        # A partial receipt is deliberately retained: uncertain creation cannot replay.
        raise


def atomic_json(path, data):
    raw = json_bytes(data)
    path = plain_control_path(path)
    if path.is_symlink():
        fail("unsafe_state", "State/receipt file cannot be a symlink.")
    make_control_directory(path.parent)
    descriptor, temporary = tempfile.mkstemp(prefix=".workflow-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            if stream.write(raw) != len(raw):
                raise OSError("Short write; publication is incomplete.")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_public(path, text, *, completeness="unknown", max_bytes=MAX_JSON):
    """Caller supplies already filtered public text under its owned reservation.

    One immutable UTF-8 body; directory durability on Windows is not inferred.
    """
    if not isinstance(text, str) or "\0" in text:
        fail("invalid_public", "Only filtered public text may be staged.")
    try:
        raw = text.encode("utf-8")
    except UnicodeError:
        fail("invalid_public", "Public text is not valid UTF-8.")
    if len(raw) > max_bytes:
        fail("oversize_result", "Public answer exceeds its producer bound.")
    path = plain_control_path(path)
    if path.exists() or path.is_symlink():
        fail("existing_receipt", "Public body exists; no overwrite or request replay.")
    make_control_directory(path.parent)
    fd, temporary = tempfile.mkstemp(prefix=".workflow-public-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            if stream.write(raw) != len(raw):
                raise OSError("Short write; publication is incomplete.")
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists() or path.is_symlink():
            fail("existing_receipt", "Public body appeared; no overwrite.")
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"schema_version": 2, "content_file": str(path), "content_sha256": hashlib.sha256(raw).hexdigest(),
            "content_bytes": len(raw), "completeness": completeness,
            "public_availability": "available" if text.strip() else "empty"}


def read_public(descriptor, expected_path, *, limit=MAX_JSON):
    """Verify an exact expected body before returning bounded public UTF-8."""
    object_keys(descriptor, {"schema_version", "content_file", "content_sha256", "content_bytes", "completeness", "public_availability"}, "public descriptor")
    expected = plain_control_path(expected_path)
    size = descriptor["content_bytes"]
    if (type(descriptor["schema_version"]) is not int or descriptor["schema_version"] != 2
            or descriptor["content_file"] != str(expected) or expected.is_symlink()
            or type(size) is not int or not 0 <= size <= limit
            or descriptor["completeness"] not in {"complete", "incomplete", "unknown"}
            or descriptor["public_availability"] not in {"available", "partial", "empty"}):
        fail("public_result", "Public descriptor identity/bound differs.")
    digest_pin(descriptor["content_sha256"])
    try:
        with expected.open("rb") as stream:
            raw = stream.read(size + 1)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != descriptor["content_sha256"]:
            fail("public_result", "Public body size/hash differs; content cannot be accepted.")
        return raw.decode("utf-8")
    except (OSError, UnicodeError):
        fail("public_result", "Public body unavailable or invalid; no request replay.")


def reported_usage(body):
    """Optional numeric fields only. Provider identifier strings are deferred."""
    source = body.get("usage")
    source = source if isinstance(source, dict) else {}
    usage, reasons = {}, {}
    for target, source_key in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens"),
                               ("total_tokens", "total_tokens")):
        value = source.get(source_key)
        valid = type(value) is int and 0 <= value <= 2**63 - 1
        usage[target] = value if valid else None
        reasons[target] = None if valid else ("missing" if value is None else "invalid")
    for target, parent, key in (("cached_input_tokens", "prompt_tokens_details", "cached_tokens"),
                                ("reasoning_tokens", "completion_tokens_details", "reasoning_tokens")):
        detail = source.get(parent)
        value = detail.get(key) if isinstance(detail, dict) else None
        valid = type(value) is int and 0 <= value <= 2**63 - 1
        usage[target] = value if valid else None
        reasons[target] = None if valid else ("missing" if value is None else "invalid")
    total = usage["total_tokens"]
    if total is not None and usage["input_tokens"] is not None and usage["output_tokens"] is not None:
        if total != usage["input_tokens"] + usage["output_tokens"]:
            reasons["total_tokens"] = "inconsistent"
    return {"usage": usage, "usage_scope": "response", "reasons": reasons,
            "model": None, "request_id": None, "response_id": None, "string_fields_reason": "deferred"}


def init_config(path):
    path = absolute_path(path, "User config")
    if path.exists():
        load_config(path)
        return {"status": "existing", "config": str(path)}
    template = load_config(Path(__file__).with_name("config-template.json"))
    try:
        write_exclusive(path, template)
    except WorkflowError as error:
        if error.code != "existing_receipt":
            raise
        load_config(path)
        return {"status": "existing", "config": str(path)}
    return {"status": "created", "config": str(path), "next": "Configure supported roles and reviewed host adapters; no inference was started."}


def runtime_available(adapter):
    if adapter["platform"] != host_platform():
        fail("host_mismatch", "Configured adapter targets another host platform.")
    interpreter = native_executable(adapter["interpreter"])
    script = absolute_path(adapter["script"], "Adapter script", must_exist=True)
    if not interpreter.is_file() or not script.is_file() or script.suffix.lower() != ".py":
        fail("invalid_runtime", "Configure a local Python interpreter and reviewed Python adapter script.")
    if file_hash(script) != adapter["sha256"].lower():
        fail("pin_mismatch", "Adapter pin mismatch; obtain the reviewed runtime instead of changing its pin to bypass doctor.")
    return interpreter, script


def server_executable(cfg, workdir=None, *, protection_roots=()):
    server = cfg["app_server"]
    if server is None:
        fail("missing_app_server", "Configure a reviewed pinned native executable for metadata; no chat was created.")
    roots = [absolute_path(root, "Runtime protection root") for root in protection_roots]
    roots.append(absolute_path(workdir if workdir is not None else Path.cwd(), "Working root"))
    verify_config_paths(cfg)
    reference = server["executable"]
    if isinstance(cfg, ResolvedConfig) and "app_server" in cfg.native_records:
        raw, executable = cfg.native_records["app_server"]
        if absolute_path(raw, "Selected native runtime") != executable:
            fail("snapshot_changed", "Selected native runtime alias changed; no rediscovery is permitted.")
    elif str(reference).startswith("@runtime:"):
        if not isinstance(cfg, ResolvedConfig):
            fail("missing_path_context", "Runtime references require a loaded immutable path context.")
        raw, executable = discover_runtime(cfg, reference, server["sha256"], roots=roots)
        cfg.native_records["app_server"] = (raw, executable)
    else:
        raw = lexical_path(reference, "Native executable")
        executable = absolute_path(raw, "Native executable", must_exist=True)
    protect_path(raw, roots)
    native_executable(executable)
    if file_hash(executable) != server["sha256"].lower():
        fail("pin_mismatch", "Native executable SHA256 differs from its reviewed configuration.")
    return executable


def doctor(path):
    cfg = load_config(path)
    result = {"status": "local_prerequisites", "inference_started": False, "adapters": {}}
    result["connections"] = {}
    for name, connection in cfg.get("connections", {}).items():
        if "api_key_env" in connection:
            available = connection["api_key_env"] in os.environ
            kind = "environment"
        else:
            available = absolute_path(connection["api_key_file"], "Credential reference").is_file()
            kind = "file"
        result["connections"][name] = {"credential_reference_kind": kind,
            "credential_reference_available": available, "access_confirmed": False,
            "text_only": True, "native_tool_access_confirmed": False}
    for name, adapter in cfg["adapters"].items():
        try:
            runtime_available(adapter)
            result["adapters"][name] = {"available": True, "access_confirmed": False}
        except WorkflowError as error:
            result["adapters"][name] = {"available": False, "blocker": error.code}
    try:
        executable = server_executable(cfg)
        result["app_server"] = {"available": True, "protocol_confirmed": False, "executable": str(executable),
                                "all_parent_protections_confirmed": False}
    except WorkflowError as error:
        result["app_server"] = {"available": False, "blocker": error.code}
    result["next"] = "Availability is local path/pin evidence only; credentials, account access and host permission enforcement are not inferred."
    result["legacy_absolute_path_fields"] = cfg.legacy_absolute_paths
    return result


def connection_url(connection):
    value = connection["base_url"]
    if (not isinstance(value, str) or not value or len(value) > 2048
            or any(ord(c) <= 32 or ord(c) >= 127 for c in value) or "\\" in value or "%" in value):
        fail("invalid_endpoint", "Configure a bounded HTTPS base URL without credentials or URL overrides.")
    try:
        parsed = urllib.parse.urlsplit(value)
        valid = (parsed.scheme == "https" and parsed.hostname and parsed.netloc
                 and parsed.username is None and parsed.password is None
                 and not parsed.query and not parsed.fragment and "?" not in value and "#" not in value
                 and (parsed.port is None or 1 <= parsed.port <= 65535))
    except ValueError:
        valid = False
    if not valid:
        fail("invalid_endpoint", "Configure HTTPS without userinfo, query, fragment or invalid port.")
    # The Responses API reuses the same frozen base URL with its own path; the
    # existing openai-chat path is preserved byte-for-byte.
    path = "/responses" if connection.get("protocol", "openai-chat") == "responses" else "/chat/completions"
    return value.rstrip("/") + path


def native_provider(cfg, provider):
    return cfg.get("connections", {}).get(provider, {}).get("native_provider", provider)


def model_tuple(model):
    return model["provider"], model["model"]


def text_transport(transport):
    """Transport capability is explicit; unfamiliar transports need native tools."""
    return transport == "text-api" or transport.endswith("-text-api")


def needs_consent(cfg, profile_id):
    selected = cfg["models"][profile_id]
    top = cfg["roles"]["top_primary"]
    return selected["requires_consent"] or (top is not None and model_tuple(selected) == model_tuple(cfg["models"][top]))


def review_gate(stage, additional_top=0):
    if stage not in STAGES or type(additional_top) is not int or additional_top not in (0, 1, 2):
        fail("invalid_gate", "Review stage must be supported and additional top count must be 0, 1 or 2.")
    if stage != "critical" and additional_top:
        fail("invalid_gate", "Additional top counts apply to critical gates only.")
    mandatory = 2 if stage == "critical" else (0 if stage == "optional_top" else 1)
    return {"mandatory_non_top": mandatory, "additional_top": additional_top, "total": mandatory + additional_top}


def select_role(cfg, role, *, stage="ordinary", allowed_providers=None,
                author_profiles=(), author_invocations=(), invocation_id=None, needs_tools=False,
                _uncertainty_reserve=False):
    validate_config(cfg)
    if role not in ROLES | {"external", "reviewer"} or stage not in STAGES:
        fail("invalid_role", "Select a configured role or independent reviewer stage.")
    authors = set(author_invocations)
    for author in authors:
        identifier(author, "author invocation")
    tuples = set()
    for author in author_profiles:
        if author not in cfg["models"]:
            fail("missing_profile", "Actual author profile must be declared, including any fallback/coauthor profile.")
        tuples.add(model_tuple(cfg["models"][author]))
    if role == "reviewer":
        if not authors or not author_profiles or invocation_id is None:
            fail("missing_identity", "Review selection requires actual author profiles/invocations and a fresh reviewer invocation ID.")
        identifier(invocation_id, "reviewer invocation")
        if invocation_id in authors:
            fail("self_review", "Author/coauthor invocation cannot independently review its own work.")
    if allowed_providers is not None:
        string_list(list(allowed_providers), "task provider restriction")
    candidates = []
    reserve = cfg["roles"]["reserve_primary"]
    if role in ROLES:
        candidates = [cfg["roles"][role]]
    elif role == "external":
        candidates = list(cfg["external_order"]) + ([reserve] if _uncertainty_reserve else [])
    elif stage == "optional_top":
        candidates = [cfg["roles"]["top_primary"]]
    else:
        candidates = list(cfg["external_order"]) + [reserve]
    def eligible_profile(profile_id):
        if profile_id is None:
            return False
        model = cfg["models"][profile_id]
        primary = model["provider"] in cfg["primary_providers"]
        if (cfg["mode"] == "primary-only" and not primary) or (cfg["mode"] == "external-only" and primary):
            return False
        if allowed_providers is not None and model["provider"] not in allowed_providers:
            return False
        if needs_tools and text_transport(model["transport"]):
            return False
        if needs_tools and model["transport"] == "native-chat" and cfg["drivers"][model["chat"]["driver"]]["kind"] != "codex":
            return False
        if role == "reviewer" and stage == "architecture" and not primary and model_tuple(model) in tuples:
            return False
        consent = needs_consent(cfg, profile_id)
        if role == "reviewer" and stage == "critical" and consent:
            return False
        return True

    found = []
    for profile_id in dict.fromkeys(candidates):
        if not eligible_profile(profile_id):
            continue
        model = cfg["models"][profile_id]
        consent = needs_consent(cfg, profile_id)
        found.append({"profile": profile_id, "provider": model["provider"], "model": model["model"],
                      "effort": model["effort"], "transport": model["transport"],
                      "requires_consent": consent, "requested_not_confirmed": True,
                      "reserve_requires_blockers": []})
    if not found:
        fail("no_eligible_role", "No eligible configured profile satisfies this role, mode, identity and provider restriction.")
    if cfg["mode"] == "primary-budget-saving":
        eligible_external = [profile for profile in cfg["external_order"] if eligible_profile(profile)]
        for entry in found:
            if entry["profile"] == reserve:
                entry["reserve_requires_blockers"] = eligible_external
    return {"status": "proposal_only", "role": role, "stage": stage,
            "candidates": found, "gate": review_gate(stage)}


def load_authorization(path, workdir):
    path = require_outside(path, workdir)
    doc = read_json(path)
    object_keys(doc, {"schema_version", "source", "authorizations"}, "authorization evidence")
    if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        fail("invalid_evidence", "Unsupported authorization evidence version.")
    object_keys(doc["source"], {"kind", "reference", "text"}, "trusted human source")
    if doc["source"]["kind"] != "human_instruction":
        fail("invalid_evidence", "Authorization requires actual trusted human instruction evidence; caller establishes provenance.")
    bounded_text(doc["source"]["reference"], "source reference")
    bounded_text(doc["source"]["text"], "human source text", 65536)
    records = doc["authorizations"]
    if not isinstance(records, list) or not records or len(records) > 128:
        fail("invalid_evidence", "Authorization records must be a nonempty bounded list.")
    fields = {"external": {"kind", "assignment_id", "workdir", "providers", "task_scope"},
              "top": {"kind", "assignment_id", "workdir", "role", "profile"},
              "chat": {"kind", "workdir", "sprint_id", "parent_chat_id"}}
    for record in records:
        if (not isinstance(record, dict) or not isinstance(record.get("kind"), str)
                or record.get("kind") not in fields):
            fail("invalid_evidence", "Unknown authorization scope.")
        object_keys(record, fields[record["kind"]], "authorization record")
        absolute_path(record["workdir"], "Evidence working root")
        if record["kind"] == "external":
            identifier(record["assignment_id"], "evidence assignment", assignment=True)
            string_list(record["providers"], "authorized providers")
            bounded_text(record["task_scope"], "task scope")
        elif record["kind"] == "top":
            identifier(record["assignment_id"], "evidence assignment", assignment=True)
            identifier(record["role"], "consented role")
            identifier(record["profile"], "consented profile")
        else:
            identifier(record["sprint_id"], "sprint", assignment=True)
            identifier(record["parent_chat_id"], "managing chat")
    return doc


def require_authorization(doc, kind, workdir, **scope):
    root = str(absolute_path(workdir, "Working root", must_exist=True))
    for record in doc["authorizations"]:
        if record["kind"] != kind or str(absolute_path(record["workdir"], "Evidence root")) != root:
            continue
        if all((value in record.get("providers", []) if key == "provider" else record.get(key) == value)
               for key, value in scope.items()):
            return
    fail("missing_authorization", "Trusted human evidence does not cover this exact assignment, role/profile/provider or folder/sprint/parent scope.")


def require_permissions(path, workdir):
    if path is None:
        fail("missing_parent_permissions", "Tool transport requires the real native parent-permission envelope; request it through the host rather than manufacturing one.")
    path = require_outside(path, workdir)
    envelope = read_json(path)
    if not isinstance(envelope, dict) or not envelope:
        fail("invalid_parent_permissions", "Parent-permission envelope must be a real nonempty native record; the adapter validates authenticity and actual constraints.")
    return path


def lexical_path(path, label):
    # Preserve lexical ancestors before resolve: a writable symlink pointing out
    # of a writable root still permits replacing the protected control path.
    absolute_path(path, label)
    return Path(os.path.abspath(os.path.expanduser(str(path))))


class ProtectionRoots(list):
    """Actual control roots; integrity_only makes no filesystem exclusion claim."""
    def __init__(self, roots, *, integrity_only=False):
        super().__init__(roots)
        self.integrity_only = integrity_only


APPROVAL_POLICIES = {"never", "on-request", "on-failure", "untrusted"}
APPROVAL_REVIEWERS = {"user", "auto_review"}


def actual_approval(value):
    object_keys(value, {"system", "policy", "reviewer"}, "actual approval requirement")
    if (value["system"] != "codex" or not isinstance(value["policy"], str) or value["policy"] not in APPROVAL_POLICIES
            or (value["reviewer"] is not None and (not isinstance(value["reviewer"], str) or value["reviewer"] not in APPROVAL_REVIEWERS))
            or (value["policy"] != "never" and value["reviewer"] is None)):
        fail("unsupported_permission_contract", "Actual approval policy/reviewer needs a supported host route.")
    return value


def actual_permissions(value, network):
    object_keys(value, {"extends", "network"}, "actual task permissions")
    object_keys(value["network"], {"enabled"}, "actual task network")
    if (value["extends"] != ":danger-full-access" or not isinstance(network, str) or network not in {"enabled", "disabled"}
            or type(value["network"]["enabled"]) is not bool or value["network"]["enabled"] != (network == "enabled")):
        fail("unsupported_permission_contract", "Schema2 implements only the observed builtin full-access profile with exact network setting.")
    return value


def caller_protection_context(config, path, root, *, tools=False, allow_actual_text=False):
    value = read_json(path)
    actual = (tools or allow_actual_text) and isinstance(value, dict) and type(value.get("schema")) is int and value["schema"] == 2
    extra = {"read_roots", "deny_read_paths", "network", "approval"} if tools or actual else set()
    if actual:
        extra.add("task_permissions")
    object_keys(value, {"schema", "writable_roots", "temp_roots", "protected_names"} | extra, "trusted parent context")
    if type(value["schema"]) is not int or value["schema"] not in ({1, 2} if actual else {1}):
        fail("invalid_context", "Context requires a supported integer schema.")
    names = value["protected_names"]
    if actual and isinstance(names, list) and any(not isinstance(name, str) for name in names):
        fail("invalid_context", "Actual protected names must be simple basenames.")
    if not isinstance(names, list) or (not names and not actual) or len(names) > 128 or len(set(names)) != len(names):
        fail("invalid_context", "Protected names must be bounded and unique.")
    if any(not isinstance(x, str) or x in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", x) for x in names):
        fail("invalid_context", "Protected names must be simple basenames.")
    result, roots = dict(value), []
    for field in ("writable_roots", "temp_roots", *(["read_roots", "deny_read_paths"] if tools or actual else [])):
        entries = value[field]
        if not isinstance(entries, list) or len(entries) > 128 or any(not isinstance(x, str) for x in entries) or len(set(entries)) != len(entries):
            fail("invalid_context", "Root lists must be complete, bounded and unique.")
        pairs = [config.path_context.resolve_pair(x) if config else (lexical_path(x, "Root"), absolute_path(x, "Root")) for x in entries]
        result[field] = [str(canonical) for _, canonical in pairs]
        if field in {"writable_roots", "temp_roots"}:
            roots.extend(path for pair in pairs for path in pair)
    root = absolute_path(root, "Working root", must_exist=True)
    if not any(is_within(root, Path(x)) for x in result["writable_roots"]):
        fail("incomplete_context", "Context must retain the working root and all real caller write/temp roots.")
    if tools or actual:
        object_keys(value["approval"], {"system", "policy", "reviewer"}, "actual approval requirement")
        if actual:
            actual_approval(value["approval"])
            actual_permissions(value["task_permissions"], value["network"])
        elif value["network"] != "disabled" or not value["read_roots"] or not value["deny_read_paths"]:
            fail("unsupported_context", "Tools require explicit read/secret boundaries and network disabled.")
    result["_protection_roots"] = ProtectionRoots(dict.fromkeys(roots), integrity_only=True) if actual else list(dict.fromkeys(roots))
    return result


def protection_context(path, root):
    if path is None:
        fail("missing_parent_permissions", "Built-in text dispatch requires a trusted host parent envelope for physical protection checks; it grants no tools.")
    source = lexical_path(path, "Parent permissions")
    require_outside(source, root)
    digest = file_hash(source)
    envelope = read_json(source)
    object_keys(envelope, {"schema", "sandbox", "read", "writable_roots", "temp_roots",
                          "protected_names", "network_access", "approval_policy", "approvals_reviewer"},
                "supported parent envelope")
    if (type(envelope["schema"]) is not int or envelope["schema"] != 1
            or envelope["sandbox"] != "workspace-write" or envelope["read"] != "root"
            or envelope["network_access"] is not False or envelope["approval_policy"] != "on-request"
            or envelope["approvals_reviewer"] != "auto_review"):
        fail("unsupported_parent_permissions", "Parent envelope is not a supported trusted host context; JSON structure alone never proves provenance.")
    names = envelope["protected_names"]
    if (not isinstance(names, list) or len(names) != 4 or not all(isinstance(name, str) for name in names)
            or set(names) != {".git", ".agents", ".codex", ".aws"}):
        fail("unsupported_parent_permissions", "Parent envelope must retain the supported host protected names.")
    roots = []
    for field in ("writable_roots", "temp_roots"):
        values = envelope[field]
        if not isinstance(values, list) or len(values) > 128 or (field == "writable_roots" and not values):
            fail("invalid_parent_permissions", "Parent root lists must be bounded and retain every real writable/temporary root.")
        for entry in values:
            raw = lexical_path(entry, "Parent protection root")
            roots.extend((raw, absolute_path(raw, "Parent protection root")))
    if root not in roots:
        fail("invalid_parent_permissions", "Parent envelope must include the working root and all other writable/temporary roots.")
    if file_hash(source) != digest:
        fail("snapshot_changed", "Parent envelope changed while loading.")
    protect_path(source, roots)
    return source, digest, roots


def protect_path(path, roots):
    if isinstance(roots, ProtectionRoots) and roots.integrity_only:
        return plain_control_path(path)
    raw = lexical_path(path, "Protected control")
    roots = [part for root in roots for part in (root, absolute_path(root, "Parent protection root"))]
    for candidate in (raw, *raw.parents):
        resolved = absolute_path(candidate, "Protected control")
        if any(is_within(candidate, root) or is_within(resolved, root) for root in roots):
            fail("unprotected_artifact", "Every control, credential and result path and its intermediate ancestors must be outside all parent writable/temporary roots.")
    return absolute_path(raw, "Protected control")


def read_credential(connection):
    """Called only after trusted context, scoped authorization and path checks."""
    if "api_key_env" in connection:
        value = os.environ.get(connection["api_key_env"])
    else:
        try:
            with Path(connection["api_key_file"]).open("rb") as stream:
                raw = stream.read(MAX_KEY + 3)
            value = raw.decode("utf-8")
        except (OSError, UnicodeError):
            fail("credential_unavailable", "Protected credential reference is unavailable; contents are suppressed.")
        # A single conventional terminal newline is permitted, never multiple lines.
        if value.endswith("\r\n"):
            value = value[:-2]
        elif value.endswith("\n"):
            value = value[:-1]
    if (not isinstance(value, str) or not value or len(value) > MAX_KEY
            or any(ord(c) <= 32 or ord(c) >= 127 for c in value)):
        fail("invalid_credential", "Credential must be a bounded single-line nonempty header-safe value; it is never logged.")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def retry_after(headers):
    value = headers.get("Retry-After") if headers is not None else None
    if value is None:
        return 0
    try:
        if re.fullmatch(r"[0-9]{1,10}", value.strip()):
            return int(value.strip())
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, parsed.timestamp() - time.time())
    except (ValueError, TypeError, OverflowError, AttributeError):
        fail("invalid_retry_after", "Invalid retry timing; no early replay is sent.")


def recovery_remaining(deadline):
    if deadline is None:
        return TEXT_INACTIVITY_TIMEOUT
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        fail("text_recovery_expired", "Recovery I/O budget expired after a request may have been sent; no replay.")
    return min(TEXT_INACTIVITY_TIMEOUT, remaining)


def text_response(response, endpoint, recovery_deadline=None, *, require_socket=False):
    if response.geturl() != endpoint or response.status != 200:
        fail("text_response_unknown", "Redirected or unexpected HTTP response; raw response is suppressed.")
    if recovery_deadline is None:
        raw = response.read(MAX_JSON + 1)
    else:
        # Standard urllib HTTPSResponse owns this socket through its BufferedReader.
        # Refresh its timeout before each bounded read instead of inheriting the
        # opener's now-stale timeout. An unfamiliar real response fails closed;
        # socket-free responses exist only in the Python fake-opener test API.
        network_socket = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
        if require_socket and (network_socket is None or not callable(getattr(network_socket, "settimeout", None))):
            fail("text_recovery_socket_unavailable", "Cannot enforce recovery body I/O timeout on this response; no replay.")
        chunks, size = [], 0
        while size <= MAX_JSON:
            remaining = recovery_remaining(recovery_deadline)
            if network_socket is not None:
                network_socket.settimeout(remaining)
                read = response.read1
            else:
                read = response.read
            chunk = read(min(65536, MAX_JSON + 1 - size))
            recovery_remaining(recovery_deadline)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        raw = b"".join(chunks)
    if len(raw) > MAX_JSON:
        fail("oversize_response", "Text response exceeded the bounded body limit; no replay is sent.")
    try:
        body = json.loads(raw.decode("utf-8"), object_pairs_hook=json_pairs,
                          parse_constant=lambda _: _INVALID_OPTIONAL_NUMBER)
    except (UnicodeError, ValueError):
        fail("invalid_response", "Malformed text response; raw response is suppressed.")
    if not isinstance(body, dict) or not isinstance(body.get("choices"), list) or len(body["choices"]) != 1:
        fail("invalid_response", "Expected one textual assistant response; raw response is suppressed.")
    choice = body["choices"][0]
    if not isinstance(choice, dict) or choice.get("finish_reason") not in (None, "stop", "length"):
        fail("invalid_response", "Unsupported response completion state; no replay is sent.")
    message = choice.get("message")
    if (not isinstance(message, dict) or message.get("role") != "assistant"
            or "tool_calls" in message or "function_call" in message
            or not isinstance(message.get("content"), str) or "\0" in message["content"]):
        fail("invalid_response", "Response must contain assistant text without any tool call; reasoning fields are never retained.")
    return {"content": message["content"], "acceptance": "accepted", "terminal": "completed",
            "finish_reason": choice.get("finish_reason") or "unknown",
            "completeness": "complete" if choice.get("finish_reason") == "stop" else (
                "incomplete" if choice.get("finish_reason") == "length" else "unknown"),
            "reported": reported_usage(body)}


def unavailable_public_descriptor(completeness):
    """A valid null public descriptor; the original terminal stays authoritative."""
    return {"schema_version": 2, "content_file": None, "content_sha256": None,
            "content_bytes": None, "completeness": completeness,
            "public_availability": "unavailable"}


def dispatch_text_responses(transport, *, key, endpoint, payload, opener, receipt, receipt_path,
                            result_path, protected_paths, output, assignment_id, roots, frozen,
                            inactivity_timeout=TEXT_INACTIVITY_TIMEOUT):
    """Accepted-architecture §2 Responses dispatch behind the frozen snapshot.

    The transport runs the frozen callback before every physical POST, enforces
    the strict SSE bounds and the closed terminal set, and never replays accepted
    or ambiguous work. This worker keeps credential redaction, path protection,
    the bounded public descriptor and the sanitized receipt exactly as the
    openai-chat path does.
    """
    try:
        client = transport.ResponsesTextClient(key=key, endpoint=endpoint, payload=payload,
                                               opener=opener, before_request=frozen,
                                               inactivity_timeout=inactivity_timeout)
        receipt["status"] = "launch_started"
        atomic_json(receipt_path, receipt)
        answer = client.submit()
        text = answer.content.replace(key, "[credential redacted]")
        frozen()
        for path in protected_paths:
            protect_path(path, roots)
        body_path = protect_path(output / (assignment_id + ".public.txt"), roots)
        if answer.terminal == "failed":
            # Known failed/cancelled/refusal/tool/reasoning-marker terminal: the
            # additive unavailable descriptor keeps the original fence intact.
            descriptor = unavailable_public_descriptor(answer.completeness)
            status = "text_failed"
        elif len(text.encode("utf-8")) > MAX_JSON:
            # A known completed/incomplete terminal whose final redacted body
            # exceeds the public bound is never truncated or downgraded.
            descriptor = unavailable_public_descriptor(answer.completeness)
            status = "text_content_unavailable"
        else:
            try:
                descriptor = write_public(body_path, text, completeness=answer.completeness)
            except OSError:
                # Terminal was observed. A small safe unavailable receipt may still
                # fit; if its own publication fails, the launch fence stays unknown.
                descriptor = unavailable_public_descriptor(answer.completeness)
            if answer.completeness == "incomplete" and text.strip() and descriptor["public_availability"] != "unavailable":
                descriptor["public_availability"] = "partial"
            status = ("text_incomplete" if answer.completeness == "incomplete" else (
                "text_completed" if text.strip() else "text_empty"))
            if descriptor["public_availability"] == "unavailable":
                status = "text_content_unavailable"
        write_exclusive(result_path, descriptor)
        receipt.update(status=status, result=str(result_path), result_sha256=file_hash(result_path),
                       acceptance="accepted", terminal=answer.terminal, completeness=answer.completeness,
                       public_availability=descriptor["public_availability"], reported=answer.reported,
                       requested_not_confirmed=True)
        if answer.failure_class is not None:
            receipt["failure_class"] = answer.failure_class
        if answer.terminal_metadata is not None:
            receipt["terminal_metadata"] = answer.terminal_metadata
        atomic_json(receipt_path, receipt)
    except transport.ResponsesError as exc:
        # Only sanitized classification is recorded; no raw body, header, error
        # text or reasoning is ever persisted.
        receipt["status"] = "rejected" if exc.acceptance == "unaccepted" else "unknown"
        receipt["acceptance"] = exc.acceptance
        if exc.terminal is not None:
            receipt["terminal"] = exc.terminal
        if exc.http_status is not None:
            receipt["http_status"] = exc.http_status
        if exc.failure_class is not None:
            receipt["failure_class"] = exc.failure_class
        protect_path(receipt_path, roots)
        atomic_json(receipt_path, receipt)
        if exc.acceptance == "unaccepted":
            fail(exc.code, "Responses dispatch failed; raw body, headers and errors are suppressed. No automatic replay.")
        fail("text_dispatch_unknown", "Responses dispatch outcome is unknown; sanitized receipt blocks replay.")
    except WorkflowError:
        if isinstance(roots, ProtectionRoots) and roots.integrity_only:
            # A frozen actual-text control may drift after a possible acceptance.
            # Retain the same exclusive fence, never claim a safe rejection/replay.
            receipt["status"] = "unknown"
            protect_path(receipt_path, roots)
            atomic_json(receipt_path, receipt)
            fail("text_dispatch_unknown", "Frozen text dispatch controls changed; the original receipt blocks replay.")
        raise
    except Exception:
        if receipt["status"] != "rejected":
            receipt["status"] = "unknown"
        protect_path(receipt_path, roots)
        atomic_json(receipt_path, receipt)
        fail("text_dispatch_" + receipt["status"], "Text dispatch did not complete; sanitized receipt blocks replay. Local descendants were never created; remote termination is unconfirmed.")
    return {"status": receipt["status"], "completeness": receipt["completeness"],
            "public_availability": receipt["public_availability"], "receipt": str(receipt_path), "result": str(result_path),
            "cleanup_confirmed": True, "local_descendants_created": False,
            "remote_termination_confirmed": False, "requested_not_confirmed": True}


def dispatch_text(config_path, cfg, proposal, *, role, profile_id, assignment_id,
                  root, prompt, output_dir, authorization_file, parent_permissions,
                  config_digest, author_invocations, invocation_id, external_blockers, http_opener,
                  protection_context_file=None, _before_text_launch=None):
    model = cfg["models"][profile_id]
    connection = cfg["connections"][model["provider"]]
    if protection_context_file is not None:
        if parent_permissions is not None:
            fail("conflicting_context", "Use the neutral text protection context separately from native tool permissions.")
        worker_source = lexical_path(__file__, "Text worker source")
        worker_pin = file_hash(worker_source)
        context_source = lexical_path(protection_context_file, "Caller protection context")
        permission_digest = file_hash(context_source)
        envelope = caller_protection_context(cfg, context_source, root, allow_actual_text=True)
        roots = envelope["_protection_roots"]
        permissions = protect_path(context_source, roots)
        if file_hash(permissions) != permission_digest:
            fail("snapshot_changed", "Caller context changed while parsing; no request is sent.")
    else:
        # Read compatibility for existing callers; this still grants no tools.
        permissions, permission_digest, roots = protection_context(parent_permissions, root)
        context_source = parent_permissions
    actual_text = isinstance(roots, ProtectionRoots) and roots.integrity_only
    protocol = connection.get("protocol", "openai-chat")
    raw_prompt = lexical_path(prompt, "Prompt") if actual_text else None
    if actual_text:
        plain_control_path(raw_prompt)
    raw_controls = [config_path, authorization_file, context_source, output_dir]
    config_path = protect_path(config_path, roots)
    authorization_file = protect_path(authorization_file, roots)
    output = protect_path(output_dir, roots)
    namespace = hashlib.sha256(os.path.normcase(str(root)).encode("utf-8")).hexdigest()
    receipt_path = plain_control_path(protect_path(config_path.parent / "workflow-receipts" / namespace / (assignment_id + ".json"), roots))
    result_path = plain_control_path(protect_path(output / (assignment_id + ".result.json"), roots))
    if receipt_path.exists() or result_path.exists():
        fail("existing_receipt", "An existing assignment receipt/result blocks duplicate text dispatch; reconcile owned state.")
    auth_digest = file_hash(authorization_file)
    doc = load_authorization(authorization_file, root)
    if model["provider"] not in cfg["primary_providers"]:
        require_authorization(doc, "external", root, assignment_id=assignment_id, provider=model["provider"])
    if proposal["requires_consent"]:
        require_authorization(doc, "top", root, assignment_id=assignment_id, role=role, profile=profile_id)
    prompt_path = absolute_path(prompt, "Prompt", must_exist=True)
    try:
        with prompt_path.open("rb") as stream:
            prompt_bytes = stream.read(MAX_JSON + 1)
        if len(prompt_bytes) > MAX_JSON:
            fail("oversize_prompt", "Text brief exceeds the bounded input limit.")
        content = prompt_bytes.decode("utf-8-sig")
    except (OSError, UnicodeError):
        fail("invalid_prompt", "Text brief must be readable UTF-8; no content is logged.")
    bounded_text(content, "Text brief", MAX_JSON)
    prompt_digest = hashlib.sha256(prompt_bytes).hexdigest()
    protected_paths = raw_controls + [config_path, authorization_file, permissions, output, receipt_path, result_path]
    key_digest = None
    key = None
    credential_field = "api_key_file" if "api_key_file" in connection else "api_key_env"
    credential_reference = connection[credential_field]
    if "api_key_file" in connection:
        key_path = protect_path(connection["api_key_file"], roots)
        connection = dict(connection, api_key_file=str(key_path))
        protected_paths.extend((cfg["connections"][model["provider"]]["api_key_file"], key_path))
        if not actual_text:
            key_digest = bounded_key_hash(key_path)
    snapshots = []
    root_bindings = []
    if actual_text:
        # Local invocation seals reuse existing path/hash checks. They assert
        # integrity only, not exclusion from this full-access caller's grants.
        for path, pin in ((raw_controls[0], config_digest), (raw_controls[1], auth_digest),
                          (context_source, permission_digest), (raw_prompt, prompt_digest)):
            raw = lexical_path(path, "Frozen text control")
            snapshots.append((raw, absolute_path(raw, "Frozen text control", must_exist=True), pin))
        sources = [(worker_source, worker_pin)]
        if protocol == "responses":
            helper_source = worker_source.with_name("text_responses.py")
            sources.append((helper_source, file_hash(helper_source)))
        for raw, pin in sources:
            plain_control_path(raw)
            canonical = absolute_path(raw, "Text source", must_exist=True)
            snapshots.append((raw, canonical, pin))
        root_bindings = [(path, absolute_path(path, "Caller root")) for path in roots]
    def frozen():
        verify_config_paths(cfg, roots=roots)
        for path in protected_paths:
            protect_path(path, roots)
        if actual_text:
            for raw, canonical, pin in snapshots:
                plain_control_path(raw)
                if absolute_path(raw, "Frozen text control") != canonical or file_hash(canonical) != pin:
                    fail("snapshot_changed", "Frozen actual-text reference/source changed; no new request is sent.")
            if (any(absolute_path(raw, "Caller root") != canonical for raw, canonical in root_bindings)
                    or connection.get(credential_field) != credential_reference
                    or cfg["connections"][model["provider"]].get(credential_field) != credential_reference):
                fail("snapshot_changed", "Frozen caller/credential reference changed; no new request is sent.")
        if (file_hash(config_path) != config_digest or file_hash(authorization_file) != auth_digest
                or file_hash(permissions) != permission_digest or file_hash(prompt_path) != prompt_digest
                or (key_digest is not None and bounded_key_hash(connection["api_key_file"]) != key_digest)
                or (key is not None and "api_key_env" in connection
                    and os.environ.get(connection["api_key_env"]) != key)):
            fail("snapshot_changed", "Frozen text dispatch artifacts changed; no new request is sent.")
    frozen()
    if actual_text and "api_key_file" in connection:
        key_digest = bounded_key_hash(connection["api_key_file"])
        frozen()
    key = read_credential(connection)
    frozen()
    # The key must never leave its fixed authentication header, even if a brief
    # accidentally includes the same value.
    if key in content:
        fail("credential_in_prompt", "Credential appears in the brief; dispatch is blocked without logging it.")
    if protocol == "responses":
        # One bundled stdlib-only Responses transport; the openai-chat request
        # shape below is preserved byte-for-byte for its own protocol.
        transport = text_responses_module()
        if actual_text:
            frozen()  # The helper seal precedes import and is checked after it.
        payload = json.dumps(transport.build_request_body(model["model"], content, model["effort"]),
                             ensure_ascii=False).encode("utf-8")
    else:
        payload = json.dumps({"model": model["model"], "messages": [{"role": "user", "content": content}],
                              "reasoning_effort": model["effort"], "stream": False}, ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_JSON:
        fail("oversize_prompt", "Encoded text request exceeds the bounded input limit.")
    if key.encode("ascii") in payload:
        fail("credential_in_request", "Credential appears in non-authentication request data; dispatch is blocked.")
    endpoint = connection_url(connection)
    if key.casefold() in endpoint.casefold():
        fail("credential_in_endpoint", "Credential appears in the endpoint; dispatch is blocked without logging it.")
    opener = http_opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open
    receipt = {"schema_version": 1, "assignment_id": assignment_id, "role": role, "profile": profile_id,
        "provider": model["provider"], "model": model["model"], "effort": model["effort"],
        "transport": "text-api", "protocol": protocol, "config_sha256": config_digest,
        "authorization_sha256": auth_digest, "parent_permissions_sha256": permission_digest,
        "prompt_sha256": prompt_digest, "workdir": str(root), "output_dir": str(output),
        "status": "prepared", "cleanup_confirmed": True, "local_descendants_created": False,
        "remote_termination_confirmed": False, "requested_not_confirmed": True,
        "author_invocations": list(author_invocations), "invocation_id": invocation_id or assignment_id,
        "external_blockers": list(external_blockers), "retries": 0}
    if key.encode("ascii") in json_bytes(receipt):
        fail("credential_in_metadata", "Credential appears in control metadata; dispatch is blocked without logging it.")
    if _before_text_launch is not None:
        # Continuation commits its intent after the complete ordinary preflight,
        # then releases its short kernel lock before any receipt/network work.
        _before_text_launch(receipt, receipt_path, result_path, frozen)
    require_storage(output, 4 * MAX_JSON)
    write_exclusive(receipt_path, receipt)
    if protocol == "responses":
        return dispatch_text_responses(transport, key=key, endpoint=endpoint, payload=payload, opener=opener,
                                       receipt=receipt, receipt_path=receipt_path, result_path=result_path,
                                       protected_paths=protected_paths, output=output,
                                       assignment_id=assignment_id, roots=roots, frozen=frozen)
    recovery_started = None
    try:
        for attempt in range(4):
            frozen()
            deadline = recovery_started + 180 if recovery_started is not None else None
            # Before another request is sent, expiry is still an explicit rejection.
            recovery_remaining(deadline)
            receipt["status"] = "launch_started"
            atomic_json(receipt_path, receipt)
            request = urllib.request.Request(endpoint, data=payload, method="POST", headers={
                "Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "tokenband/1"})
            try:
                # Initial dispatch has only its inactivity timeout. The explicit
                # unaccepted-429 series alone has a 180-second recovery budget.
                with opener(request, timeout=recovery_remaining(deadline)) as response:
                    recovery_remaining(deadline)
                    answer = text_response(response, endpoint, deadline, require_socket=http_opener is None)
                    recovery_remaining(deadline)
                break
            except urllib.error.HTTPError as error:
                try:
                    status = error.code
                    if type(status) is int and 100 <= status <= 599:
                        receipt["http_status"] = status
                    delay_hint = retry_after(error.headers) if status == 429 else 0
                finally:
                    error.close()  # Never read or persist raw HTTP error bodies.
                if status != 429:
                    if status in (400, 401, 403, 404, 405, 422):
                        receipt["status"] = "rejected"
                    fail("text_http_failure", "HTTP dispatch failed; raw body, headers and errors are suppressed. No automatic replay.")
                if recovery_started is None:
                    recovery_started = time.monotonic()
                receipt["status"] = "rejected"
                receipt["retries"] = attempt
                atomic_json(receipt_path, receipt)
                elapsed = time.monotonic() - recovery_started
                if attempt == 3:
                    fail("text_429_exhausted", "Explicit unaccepted 429 recovery exhausted; no account cooldown or fallback is imposed.")
                delay = max((15, 30, 60)[attempt], delay_hint)
                if delay + elapsed > 180:
                    fail("text_429_exhausted", "Retry-After exceeds the remaining 180-second recovery budget; no early retry.")
                time.sleep(delay)
                if time.monotonic() - recovery_started >= 180:
                    fail("text_429_exhausted", "Unaccepted 429 recovery budget exhausted; no retry.")
                receipt["retries"] = attempt + 1
        text = answer["content"].replace(key, "[credential redacted]")
        frozen()
        for path in protected_paths:
            protect_path(path, roots)
        body_path = protect_path(output / (assignment_id + ".public.txt"), roots)
        try:
            descriptor = write_public(body_path, text, completeness=answer["completeness"])
        except OSError:
            # Terminal was observed. A small safe unavailable receipt may still fit;
            # if its own publication fails, the existing launch fence stays unknown.
            descriptor = {"schema_version": 2, "content_file": None, "content_sha256": None,
                          "content_bytes": None, "completeness": answer["completeness"],
                          "public_availability": "unavailable"}
        if answer["completeness"] == "incomplete" and text.strip() and descriptor["public_availability"] != "unavailable":
            descriptor["public_availability"] = "partial"
        write_exclusive(result_path, descriptor)
        status = ("text_incomplete" if answer["completeness"] == "incomplete" else (
            "text_terminal_unknown" if answer["completeness"] == "unknown" else (
                "text_completed" if text.strip() else "text_empty")))
        if descriptor["public_availability"] == "unavailable":
            status = "text_content_unavailable"
        receipt.update(status=status, result=str(result_path), result_sha256=file_hash(result_path),
                       acceptance="accepted", terminal="completed", completeness=answer["completeness"],
                       public_availability=descriptor["public_availability"], finish_reason=answer["finish_reason"],
                       reported=answer["reported"], requested_not_confirmed=True)
        atomic_json(receipt_path, receipt)
    except Exception:
        if receipt["status"] != "rejected":
            receipt["status"] = "unknown"
        protect_path(receipt_path, roots)
        atomic_json(receipt_path, receipt)
        fail("text_dispatch_" + receipt["status"], "Text dispatch did not complete; sanitized receipt blocks replay. Local descendants were never created; remote termination is unconfirmed.")
    return {"status": receipt["status"], "completeness": receipt["completeness"],
            "public_availability": receipt["public_availability"], "receipt": str(receipt_path), "result": str(result_path),
            "cleanup_confirmed": True, "local_descendants_created": False,
            "remote_termination_confirmed": False, "requested_not_confirmed": True}


def dispatch(config_path, *, role, profile_id, assignment_id, workdir, prompt,
             output_dir, authorization_file, parent_permissions=None, protection_context_file=None,
             stage="ordinary", allowed_providers=None, author_profiles=(),
             author_invocations=(), invocation_id=None, external_blockers=(), needs_tools=False,
             http_opener=None, _before_text_launch=None, _uncertainty_reserve=False):
    identifier(assignment_id, "assignment", assignment=True)
    root = absolute_path(workdir, "Working root", must_exist=True)
    if not root.is_dir():
        fail("invalid_path", "Working root must be an existing folder.")
    raw_config_path = config_path
    config_path = require_outside(config_path, root)
    config_digest = file_hash(config_path)
    cfg = load_config(raw_config_path)
    if file_hash(config_path) != config_digest:
        fail("snapshot_changed", "User configuration changed while loading; no dispatch was prepared.")
    selection = select_role(cfg, role, stage=stage, allowed_providers=allowed_providers,
                            author_profiles=author_profiles, author_invocations=author_invocations,
                            invocation_id=invocation_id, needs_tools=needs_tools,
                            _uncertainty_reserve=_uncertainty_reserve)
    eligible = {entry["profile"]: entry for entry in selection["candidates"]}
    if profile_id not in eligible:
        fail("ineligible_profile", "Requested profile is not eligible for this role and actual author identity.")
    proposal = eligible[profile_id]
    missing = set(proposal["reserve_requires_blockers"]) - set(external_blockers)
    if missing:
        fail("missing_reserve_evidence", "Record assignment-specific obstacles for every eligible external alternative before reserve dispatch.")
    model = cfg["models"][profile_id]
    if model["transport"] == "text-api" and model["adapter"] is None:
        return dispatch_text(raw_config_path, cfg, proposal, role=role, profile_id=profile_id,
            assignment_id=assignment_id, root=root, prompt=prompt, output_dir=output_dir,
            authorization_file=authorization_file, parent_permissions=parent_permissions,
            config_digest=config_digest, author_invocations=author_invocations,
            invocation_id=invocation_id, external_blockers=external_blockers, http_opener=http_opener,
            protection_context_file=protection_context_file, _before_text_launch=_before_text_launch)
    if protection_context_file is not None:
        fail("text_context_only", "Neutral protection context grants no native tool permissions.")
    if model["transport"] == "native-chat":
        fail("native_sprint_required", "Use sprint-create/send for this persistent native profile.")
    if model["adapter"] is None:
        fail("desktop_execution_required", "This primary profile is managed by Desktop; use its purpose-built tools instead of a generic executor.")
    adapter = cfg["adapters"][model["adapter"]]
    verify_config_paths(cfg, roots=[root])
    interpreter, script = runtime_available(adapter)
    require_outside(interpreter, root)
    require_outside(script, root)
    output = require_outside(output_dir, root)
    prompt = absolute_path(prompt, "Prompt", must_exist=True)
    if not prompt.is_file():
        fail("missing_prompt", "Prompt must be an existing UTF-8 brief file.")
    try:
        decoder = codecs.getincrementaldecoder("utf-8-sig")()
        with prompt.open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                decoder.decode(block)
            decoder.decode(b"", final=True)
    except (OSError, UnicodeError):
        fail("invalid_prompt", "Prompt must be a readable UTF-8 brief.")
    authorization_digest = file_hash(authorization_file)
    doc = load_authorization(authorization_file, root)
    if file_hash(authorization_file) != authorization_digest:
        fail("snapshot_changed", "Human evidence changed while loading; no dispatch was prepared.")
    if model["provider"] not in cfg["primary_providers"]:
        require_authorization(doc, "external", root, assignment_id=assignment_id, provider=model["provider"])
    if proposal["requires_consent"]:
        require_authorization(doc, "top", root, assignment_id=assignment_id, role=role, profile=profile_id)
    permissions = None
    if not text_transport(model["transport"]):
        permissions = require_permissions(parent_permissions, root)
    elif parent_permissions is not None:
        fail("text_tools_forbidden", "Text-only transport must not receive model tool permissions.")
    argv = [str(interpreter), str(script), "--provider", model["provider"], "--model", model["model"],
            "--effort", model["effort"], "--workdir", str(root), "--prompt", str(prompt),
            "--output-dir", str(output), "--transport", model["transport"]]
    if permissions is not None:
        argv += ["--parent-permissions", str(permissions)]
    if text_transport(model['transport']) and model['adapter'] is not None:
        argv += ['--assignment-id', assignment_id, '--authorization-sha256', authorization_digest, '--config-sha256', config_digest, '--config-path', str(config_path), '--authorization-path', str(authorization_file), '--adapter-sha256', adapter['sha256'].lower()]
    # Stable protected namespace: changing output destinations cannot replay a job.
    root_namespace = hashlib.sha256(os.path.normcase(str(root)).encode("utf-8")).hexdigest()
    receipt_path = config_path.parent / "workflow-receipts" / root_namespace / (assignment_id + ".json")
    require_outside(receipt_path, root)
    receipt = {"schema_version": 1, "assignment_id": assignment_id, "role": role,
               "profile": profile_id, "provider": model["provider"], "model": model["model"],
               "effort": model["effort"], "transport": model["transport"], "adapter_sha256": adapter["sha256"].lower(),
               "resolved_interpreter": str(interpreter), "resolved_adapter_script": str(script),
               "prompt_sha256": file_hash(prompt), "config_sha256": config_digest,
               "authorization_sha256": authorization_digest,
               "parent_permissions_sha256": file_hash(permissions) if permissions else None,
               "workdir": str(root), "output_dir": str(output),
               "status": "prepared", "cleanup_confirmed": False,
               "requested_not_confirmed": True, "author_invocations": list(author_invocations),
               "invocation_id": invocation_id or assignment_id, "external_blockers": list(external_blockers)}
    write_exclusive(receipt_path, receipt)
    try:
        # Freeze pins immediately before handoff; native runtime independently rechecks its bundle.
        verify_config_paths(cfg, roots=[root])
        if (file_hash(script) != receipt["adapter_sha256"] or file_hash(prompt) != receipt["prompt_sha256"]
                or file_hash(config_path) != receipt["config_sha256"]
                or file_hash(authorization_file) != receipt["authorization_sha256"]
                or (permissions is not None and file_hash(permissions) != receipt["parent_permissions_sha256"])):
            fail("snapshot_changed", "Dispatch snapshot changed before launch; receipt remains blocking.")
        receipt["status"] = "launch_started"
        atomic_json(receipt_path, receipt)
        proc = subprocess.Popen(argv, shell=False, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                cwd=str(root), **hidden_process_options())
        exit_code = proc.wait()  # No global inference deadline and no process-group cancellation.
        receipt["status"] = "adapter_returned"
        receipt["adapter_exit_code"] = exit_code
        atomic_json(receipt_path, receipt)
    except (OSError, WorkflowError):
        receipt["status"] = "unknown"
        atomic_json(receipt_path, receipt)
        fail("launch_unknown", "Adapter handoff is unknown; reconcile the exclusive receipt and genuine native cleanup before any replacement. Raw errors are suppressed.")
    return {"status": "adapter_returned", "adapter_exit_code": exit_code,
            "receipt": str(receipt_path), "cleanup_confirmed": False,
            "requested_not_confirmed": True,
            "next": "Read native protected results; wrapper exit does not prove model confirmation or kernel cleanup."}


class UncertaintyLock:
    """Stable one-byte kernel lock; release on close/death, never unlink."""
    def __init__(self, path, roots):
        self.path, self.roots, self.handle = Path(path), roots, None

    def __enter__(self):
        protect_path(self.path, self.roots)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        os.set_inheritable(handle.fileno(), False)
        try:
            handle.seek(0)
            if not handle.read(1):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            elif sys.platform.startswith("linux"):
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                fail("uncertainty_lock_unsupported", "No qualified local locking primitive; reconcile without launching.")
            self.handle = handle
            return self
        except OSError as error:
            handle.close()
            if error.errno in (11, 13, 35, 36):
                fail("uncertainty_busy", "Another owner holds the protected chain lock.")
            fail("uncertainty_lock_unsupported", "Local lock failed; no ownership or dispatch is inferred.")
        except BaseException:
            handle.close()
            raise

    def release(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    def __exit__(self, *_):
        self.release()


def uncertainty_time(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value < 253402300799:
        fail("uncertainty_clock", "Invalid UTC wall clock; trusted reconciliation is required and state is preserved.")
    return value


def uncertainty_context(config_path, workdir, parent_permissions, protection_context_file):
    root = absolute_path(workdir, "Working root", must_exist=True)
    raw_root = lexical_path(workdir, "Working root")
    if not root.is_dir():
        fail("invalid_path", "Working root must be a directory.")
    raw_config = lexical_path(config_path, "User config")
    worker_source = lexical_path(__file__, "Text worker source")
    worker_pin = file_hash(worker_source)
    digest = file_hash(require_outside(raw_config, root))
    cfg = load_config(raw_config)
    if protection_context_file is not None:
        if parent_permissions is not None:
            fail("conflicting_context", "Select exactly one trusted caller protection envelope.")
        source = lexical_path(protection_context_file, "Caller protection context")
        permission_digest = file_hash(source)
        envelope = caller_protection_context(cfg, source, root, allow_actual_text=True)
        roots = envelope["_protection_roots"]
        if file_hash(source) != permission_digest:
            fail("snapshot_changed", "Caller context changed while parsing; uncertainty state is preserved.")
    else:
        source, permission_digest, roots = protection_context(parent_permissions, root)
    config_path = protect_path(raw_config, roots)
    protect_path(source, roots)
    namespace = hashlib.sha256(os.path.normcase(str(root)).encode("utf-8")).hexdigest()
    directory = protect_path(config_path.parent / "workflow-receipts" / namespace, roots)
    snapshots = []
    root_bindings = []
    if isinstance(roots, ProtectionRoots) and roots.integrity_only:
        for raw, pin in ((raw_config, digest), (source, permission_digest), (worker_source, worker_pin)):
            plain_control_path(raw)
            snapshots.append((raw, absolute_path(raw, "Frozen uncertainty control", must_exist=True), pin))
        root_bindings = [(path, absolute_path(path, "Caller root")) for path in roots]
    def frozen():
        verify_config_paths(cfg, roots=roots)
        for path in (raw_config, source, directory):
            protect_path(path, roots)
        for raw, canonical, pin in snapshots:
            plain_control_path(raw)
            if absolute_path(raw, "Frozen uncertainty control") != canonical or file_hash(canonical) != pin:
                fail("snapshot_changed", "Frozen uncertainty reference/source changed; state is preserved.")
        if any(absolute_path(raw, "Caller root") != canonical for raw, canonical in root_bindings):
            fail("snapshot_changed", "Frozen uncertainty caller roots changed; state is preserved.")
        if (file_hash(config_path) != digest or file_hash(source) != permission_digest
                or absolute_path(raw_root, "Working root") != root):
            fail("snapshot_changed", "Frozen uncertainty config/caller/root changed; trusted reconciliation is required.")
    frozen()
    return {"cfg": cfg, "root": root, "raw_root": raw_root, "config": config_path,
            "config_sha256": digest, "permissions_sha256": permission_digest,
            "roots": roots, "directory": directory, "frozen": frozen}


def uncertainty_scope(*, task_sha256, role, stage, allowed_providers,
                      author_profiles, author_invocations):
    digest_pin(task_sha256)
    if role not in {"external", "reviewer"} or stage not in STAGES:
        fail("uncertainty_scope", "Continuation is restricted to explicit external analysis or independent reviewer scope.")
    for values in (author_profiles, author_invocations):
        string_list(list(values), "actual author identities")
    if allowed_providers is not None:
        string_list(list(allowed_providers), "task provider restriction")
    return {"task_sha256": task_sha256.lower(), "role": role, "stage": stage,
            "allowed_providers": sorted(allowed_providers) if allowed_providers is not None else None,
            "author_profiles": sorted(author_profiles), "author_invocations": sorted(author_invocations)}


def uncertainty_receipt(ctx, assignment_id, expected=None):
    """Read only the namespace receipt and its expected protected result."""
    identifier(assignment_id, "source assignment", assignment=True)
    path = protect_path(ctx["directory"] / (assignment_id + ".json"), ctx["roots"])
    if not path.exists():
        return None
    receipt_hash = file_hash(path)
    doc = read_json(path)
    fields = ("schema_version", "assignment_id", "invocation_id", "role", "profile", "provider", "model",
              "effort", "transport", "protocol", "config_sha256", "authorization_sha256",
              "parent_permissions_sha256", "prompt_sha256", "workdir", "output_dir", "author_invocations")
    if not isinstance(doc, dict) or any(field not in doc for field in fields):
        fail("uncertainty_identity", "Source is not a supported schema1 text receipt; reconcile protected evidence.")
    if (type(doc["schema_version"]) is not int or doc["schema_version"] != 1
            or doc["assignment_id"] != assignment_id or doc["transport"] != "text-api"
            or doc["config_sha256"] != ctx["config_sha256"]
            or doc["parent_permissions_sha256"] != ctx["permissions_sha256"]
            or doc["workdir"] != str(ctx["root"]) or doc.get("local_descendants_created") is not False):
        fail("uncertainty_identity", "Receipt text/snapshot/caller identity differs; no continuation is authorized.")
    identifier(doc["invocation_id"], "source invocation")
    for field in ("config_sha256", "authorization_sha256", "parent_permissions_sha256", "prompt_sha256"):
        digest_pin(doc[field])
    string_list(doc["author_invocations"], "receipt author invocations")
    cfg = ctx["cfg"]
    identifier(doc["profile"], "source profile")
    model = cfg["models"].get(doc["profile"])
    if model is None or any(doc[key] != model[key] for key in ("provider", "model", "effort")):
        fail("uncertainty_identity", "Receipt model does not match the frozen configured profile.")
    expected_protocol = cfg.get("connections", {}).get(model["provider"], {}).get("protocol", "openai-chat")
    if doc["protocol"] != expected_protocol:
        fail("uncertainty_identity", "Receipt protocol differs from the frozen configured connection.")
    output = protect_path(doc["output_dir"], ctx["roots"])
    result = protect_path(output / (assignment_id + ".result.json"), ctx["roots"])
    identity = {field: doc[field] for field in fields}
    identity["expected_result"] = str(result)
    known = {field: doc[field] for field in ("stage", "allowed_providers", "author_profiles", "task_sha256") if field in doc}
    if known:
        if "stage" in known and (not isinstance(known["stage"], str) or known["stage"] not in STAGES):
            fail("uncertainty_scope", "Known source stage is invalid; trusted reconciliation is required.")
        if "allowed_providers" in known and known["allowed_providers"] is not None:
            string_list(known["allowed_providers"], "known source provider restrictions")
        if "author_profiles" in known:
            string_list(known["author_profiles"], "known source actual author profiles")
        if "task_sha256" in known:
            digest_pin(known["task_sha256"])
        identity["known_scope"] = known
    if expected is not None and identity != expected:
        fail("uncertainty_identity", "Stable receipt identity/path changed; preserve bytes for trusted reconciliation.")
    status = doc.get("status")
    # The Responses protocol has a closed terminal set of its own; text_terminal_unknown
    # is an openai-chat convention and is not a Responses transition.
    terminal_statuses = ({"text_completed", "text_empty", "text_incomplete", "text_failed", "text_content_unavailable"}
                         if expected_protocol == "responses" else set(TEXT_TERMINAL_STATUSES))
    if not isinstance(status, str) or status not in ({"prepared", "launch_started", "unknown", "rejected", "accepted", "running", "in_progress"} | terminal_statuses):
        fail("uncertainty_identity", "Unsupported receipt transition; trusted reconciliation is required.")
    result_hash = None
    if status in TEXT_TERMINAL_STATUSES:
        digest_pin(doc.get("result_sha256"))
        if doc.get("result") != str(result) or not result.is_file() or file_hash(result) != doc["result_sha256"]:
            fail("uncertainty_result", "Protected completion path/hash differs; no result is accepted.")
        descriptor = read_json(result)
        if descriptor.get("schema_version") == 2:
            try:
                if status in {"text_content_unavailable", "text_failed"}:
                    object_keys(descriptor, {"schema_version", "content_file", "content_sha256", "content_bytes", "completeness", "public_availability"}, "unavailable public descriptor")
                    if (descriptor["public_availability"] != "unavailable" or any(descriptor[key] is not None for key in ("content_file", "content_sha256", "content_bytes"))
                            or descriptor["completeness"] not in {"complete", "incomplete", "unknown"}):
                        fail("public_result", "Invalid unavailable terminal descriptor.")
                else:
                    public = protect_path(output / (assignment_id + ".public.txt"), ctx["roots"])
                    read_public(descriptor, public)
                # openai-chat always observes a completed transport terminal; the
                # Responses protocol adds its own known terminals.
                if expected_protocol == "responses":
                    expected_terminals = {"text_completed": {"completed"}, "text_empty": {"completed"},
                                          "text_incomplete": {"incomplete"}, "text_failed": {"failed"},
                                          "text_content_unavailable": {"completed", "incomplete"}}
                    # A Responses transition is only valid with its exact pair. An
                    # unavailable descriptor keeps the terminal/completeness that was
                    # actually observed, so it accepts exactly two pairs.
                    expected_pairs = {"text_completed": {("completed", "complete")},
                                      "text_empty": {("completed", "complete")},
                                      "text_incomplete": {("incomplete", "incomplete")},
                                      "text_failed": {("failed", "unknown")},
                                      "text_content_unavailable": {("completed", "complete"),
                                                                  ("incomplete", "incomplete")}}
                else:
                    expected_terminals = {name: {"completed"} for name in TEXT_TERMINAL_STATUSES}
                    expected_pairs = None
                expected_complete = {"text_completed": "complete", "text_empty": "complete", "text_incomplete": "incomplete",
                                     "text_terminal_unknown": "unknown", "text_failed": "unknown"}.get(status)
                observed_pair = (doc.get("terminal"), doc.get("completeness"))
                if (doc.get("acceptance") != "accepted" or doc.get("terminal") not in expected_terminals[status]
                        or doc.get("completeness") != descriptor["completeness"]
                        or doc.get("public_availability") != descriptor["public_availability"]
                        or expected_complete is not None and descriptor["completeness"] != expected_complete
                        or expected_pairs is not None and observed_pair not in expected_pairs[status]):
                    fail("public_result", "Terminal receipt/completeness descriptor conflict.")
            except WorkflowError:
                fail("uncertainty_result", "Public descriptor/body differs; no content intake or replay.")
        elif expected_protocol == "responses":
            # The Responses protocol has no legacy inline result: it requires the
            # schema 2 descriptor and the exact terminal/completeness pair above.
            fail("uncertainty_result", "Responses receipt without a schema 2 descriptor; retain evidence.")
        elif status != "text_completed" or not isinstance(descriptor.get("content"), str):
            fail("uncertainty_result", "Unsupported legacy public result; retain evidence.")
        result_hash = doc["result_sha256"]
    elif "result" in doc or "result_sha256" in doc:
        fail("uncertainty_result", "Incomplete receipt has an unexpected result; trusted reconciliation is required.")
    if file_hash(path) != receipt_hash:
        fail("snapshot_changed", "Source receipt changed during observation; retry protected observation.")
    return {"identity": identity, "receipt_sha256": receipt_hash, "status": status, "result_sha256": result_hash}


def uncertainty_chain_path(ctx, source_id):
    """A child always resolves to its existing root; aliases cannot reset clocks."""
    identifier(source_id, "source assignment", assignment=True)
    direct = protect_path(ctx["directory"] / (source_id + ".uncertainty.json"), ctx["roots"])
    matches = []
    if ctx["directory"].exists():
        for path in ctx["directory"].glob("*.uncertainty.json"):
            protect_path(path, ctx["roots"])
            doc = uncertainty_read_state(path)
            if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list):
                fail("uncertainty_state", "Malformed protected chain; trusted reconciliation is required.")
            if doc.get("root_assignment_id") == source_id or any(
                    isinstance(entry, dict) and entry.get("assignment_id") == source_id for entry in doc["entries"]):
                matches.append(path)
    if len(matches) > 1:
        fail("uncertainty_state", "Conflicting chain ownership requires trusted reconciliation.")
    return matches[0] if matches else direct


def uncertainty_read_state(path):
    try:
        return read_json(path)
    except WorkflowError:
        fail("uncertainty_state", "Protected uncertainty state is malformed/unreadable; preserve bytes for trusted operator reconciliation.")


def uncertainty_validate_state(ctx, state, scope, now):
    required = {"schema_version", "root_assignment_id", "workdir", "lexical_workdir", "config_sha256",
                "permissions_sha256", "scope", "original_role", "original_status", "first_receipt_sha256",
                "created_utc", "last_observed_utc", "entries"}
    object_keys(state, required, "uncertainty sidecar")
    if (type(state["schema_version"]) is not int or state["schema_version"] != 1
            or state["workdir"] != str(ctx["root"]) or state["lexical_workdir"] != str(ctx["raw_root"])
            or state["config_sha256"] != ctx["config_sha256"]
            or state["permissions_sha256"] != ctx["permissions_sha256"] or state["scope"] != scope):
        fail("uncertainty_scope", "Frozen task/config/stage/authors/caller differ; explicit trusted reconciliation is required.")
    identifier(state["root_assignment_id"], "root assignment", assignment=True)
    digest_pin(state["first_receipt_sha256"])
    created, last = uncertainty_time(state["created_utc"]), uncertainty_time(state["last_observed_utc"])
    if not created <= last <= now:
        fail("uncertainty_clock", "Clock regressed or stored UTC is in the future; preserve state for trusted reconciliation.")
    entries = state["entries"]
    if not isinstance(entries, list) or not entries or len(entries) > len(ctx["cfg"]["models"]) + 1:
        fail("uncertainty_state", "Invalid finite chain; preserve state for trusted reconciliation.")
    ids, invocations, tuples = set(), set(), set()
    fields = {"assignment_id", "invocation_id", "profile", "model_tuple", "identity", "receipt_sha256", "status",
              "first_unknown_utc", "expires_utc", "uncertainty_basis", "result_sha256", "intent"}
    for index, entry in enumerate(entries):
        object_keys(entry, fields, "uncertainty entry")
        identifier(entry["assignment_id"], "linked assignment", assignment=True)
        identifier(entry["invocation_id"], "linked invocation")
        identifier(entry["profile"], "linked profile")
        profile = ctx["cfg"]["models"].get(entry["profile"])
        if profile is None or entry["model_tuple"] != list(model_tuple(profile)):
            fail("uncertainty_state", "Linked model identity differs from frozen config.")
        pair = tuple(entry["model_tuple"])
        if entry["assignment_id"] in ids or entry["invocation_id"] in invocations or pair in tuples:
            fail("uncertainty_state", "Duplicate chain identity/model requires trusted reconciliation.")
        ids.add(entry["assignment_id"]); invocations.add(entry["invocation_id"]); tuples.add(pair)
        if not isinstance(entry["identity"], dict) or entry["identity"].get("assignment_id") != entry["assignment_id"]:
            fail("uncertainty_state", "Invalid linked stable receipt identity.")
        identity = entry["identity"]
        if (identity.get("invocation_id") != entry["invocation_id"] or identity.get("profile") != entry["profile"]
                or [identity.get("provider"), identity.get("model")] != entry["model_tuple"]
                or identity.get("config_sha256") != ctx["config_sha256"]
                or identity.get("parent_permissions_sha256") != ctx["permissions_sha256"]
                or identity.get("workdir") != str(ctx["root"])):
            fail("uncertainty_state", "Linked journal/receipt identities disagree; trusted reconciliation is required.")
        if not isinstance(entry["status"], str) or entry["status"] not in ({"intent", "prepared", "launch_started", "unknown", "rejected", "accepted", "running", "in_progress", "missing"} | TEXT_TERMINAL_STATUSES):
            fail("uncertainty_state", "Invalid linked status requires trusted reconciliation.")
        if entry["receipt_sha256"] is not None:
            digest_pin(entry["receipt_sha256"])
        if entry["result_sha256"] is not None:
            digest_pin(entry["result_sha256"])
        first, expiry = entry["first_unknown_utc"], entry["expires_utc"]
        if first is None:
            if expiry is not None or entry["uncertainty_basis"] is not None:
                fail("uncertainty_clock", "Incomplete uncertainty clock requires trusted reconciliation.")
        else:
            first, expiry = uncertainty_time(first), uncertainty_time(expiry)
            if not created <= first <= last or expiry != first + 900 or entry["uncertainty_basis"] not in {
                    "coordinator_first_observation", "explicit_lost_outcome", "intent_without_receipt"}:
                fail("uncertainty_clock", "Invalid uncertainty deadline requires trusted reconciliation.")
        if index == 0:
            if (entry["assignment_id"] != state["root_assignment_id"] or entry["intent"] is not None
                    or state["original_role"] != identity.get("role")
                    or not isinstance(state["original_status"], str)
                    or state["original_status"] not in {"prepared", "launch_started", "unknown"}):
                fail("uncertainty_state", "Invalid root linkage requires trusted reconciliation.")
        else:
            intent = entry["intent"]
            object_keys(intent, {"root_assignment_id", "config_sha256", "task_sha256", "authorization_sha256",
                                 "permissions_sha256", "prompt_sha256", "purpose", "created_utc"}, "dispatch intent")
            if (intent["root_assignment_id"] != state["root_assignment_id"]
                    or intent["config_sha256"] != ctx["config_sha256"] or intent["task_sha256"] != scope["task_sha256"]
                    or intent["permissions_sha256"] != ctx["permissions_sha256"] or intent["purpose"] not in {"analysis", "review"}
                    or not created <= uncertainty_time(intent["created_utc"]) <= last):
                fail("uncertainty_state", "Invalid durable intent binding requires trusted reconciliation.")
            for field in ("authorization_sha256", "permissions_sha256", "prompt_sha256"):
                digest_pin(intent[field])


def uncertainty_entry(observation):
    identity = observation["identity"]
    return {"assignment_id": identity["assignment_id"], "invocation_id": identity["invocation_id"],
            "profile": identity["profile"], "model_tuple": [identity["provider"], identity["model"]],
            "identity": identity, "receipt_sha256": observation["receipt_sha256"], "status": observation["status"],
            "first_unknown_utc": None, "expires_utc": None, "uncertainty_basis": None,
            "result_sha256": observation["result_sha256"], "intent": None}


def uncertainty_reconcile(ctx, path, scope, now, outcome_uncertain=False, asserted_source=None, *, persist=True):
    """Caller owns the stable chain lock. No network or native execution occurs."""
    ctx["frozen"]()
    if path.exists():
        state = uncertainty_read_state(path)
        uncertainty_validate_state(ctx, state, scope, now)
    else:
        source_id = path.name[:-len(".uncertainty.json")]
        observation = uncertainty_receipt(ctx, source_id)
        if observation is None:
            fail("uncertainty_source_missing", "No protected source receipt/linked intent exists.")
        identity, status = observation["identity"], observation["status"]
        for field, value in identity.get("known_scope", {}).items():
            asserted = scope[field]
            if field in {"allowed_providers", "author_profiles"} and value is not None:
                value = sorted(value)
            elif field == "task_sha256":
                value = value.lower()
            if value != asserted:
                fail("uncertainty_scope", "Known source stage/task/authors/provider restrictions cannot be replaced by legacy assertions.")
        if sorted(identity["author_invocations"]) != scope["author_invocations"]:
            fail("uncertainty_scope", "Actual source author invocations must be preserved exactly.")
        if (identity["role"] not in {"external", "reviewer", "main_external", "reserve_primary"}
                or (identity["role"] == "reviewer") != (scope["role"] == "reviewer")):
            fail("uncertainty_scope", "Original analysis/reviewer role must be preserved; legacy scope cannot downgrade review.")
        if status != "unknown" and not (status in {"prepared", "launch_started"} and outcome_uncertain):
            return None, {"status": "resolved" if status in TEXT_TERMINAL_STATUSES else "needs_reconciliation",
                          "root_assignment_id": source_id, "reason": "source_not_observed_uncertain", "inference_started": False}
        state = {"schema_version": 1, "root_assignment_id": source_id,
                 "workdir": str(ctx["root"]), "lexical_workdir": str(ctx["raw_root"]),
                 "config_sha256": ctx["config_sha256"], "permissions_sha256": ctx["permissions_sha256"],
                 "scope": scope, "original_role": identity["role"], "original_status": status,
                 "first_receipt_sha256": observation["receipt_sha256"], "created_utc": now,
                 "last_observed_utc": now, "entries": [uncertainty_entry(observation)]}
    transitions = {"prepared": {"prepared", "launch_started", "unknown", "rejected", "text_completed"},
                  "launch_started": {"launch_started", "unknown", "rejected", "text_completed"},
                  "unknown": {"unknown", "text_completed"}, "rejected": {"rejected"},
                  "text_completed": {"text_completed"}, "intent": {"prepared", "launch_started", "unknown", "rejected", "text_completed", "missing"},
                  "missing": {"missing", "prepared", "launch_started", "unknown", "rejected", "text_completed"}}
    for allowed in transitions.values():
        if "text_completed" in allowed:
            allowed.update(TEXT_TERMINAL_STATUSES)
    for terminal_status in TEXT_TERMINAL_STATUSES:
        transitions[terminal_status] = {terminal_status}
    results = []
    for entry in state["entries"]:
        observation = uncertainty_receipt(ctx, entry["assignment_id"], entry["identity"])
        if observation is None:
            if entry["intent"] is None or entry["receipt_sha256"] is not None:
                fail("uncertainty_identity", "Previously observed receipt disappeared; trusted reconciliation is required.")
            status = "missing"
        else:
            status = observation["status"]
        if status not in transitions.get(entry["status"], {entry["status"], "unknown", "text_completed"}):
            fail("uncertainty_identity", "Receipt status regressed; trusted reconciliation is required.")
        if entry["result_sha256"] is not None and (observation is None or observation["result_sha256"] != entry["result_sha256"]):
            fail("uncertainty_result", "Previously observed completion hash changed; trusted reconciliation is required.")
        entry["status"] = status
        if observation is not None:
            entry["receipt_sha256"] = observation["receipt_sha256"]
            entry["result_sha256"] = observation["result_sha256"]
        lost = outcome_uncertain and entry["assignment_id"] == asserted_source and status in {"prepared", "launch_started"}
        if entry["first_unknown_utc"] is None and (status in {"unknown", "missing"} or lost):
            entry.update(first_unknown_utc=now, expires_utc=now + 900,
                         uncertainty_basis="explicit_lost_outcome" if lost else (
                             "intent_without_receipt" if status == "missing" else "coordinator_first_observation"))
        if status in TEXT_TERMINAL_STATUSES:
            results.append({"assignment_id": entry["assignment_id"], "result_sha256": entry["result_sha256"]})
    state["last_observed_utc"] = now
    latest = state["entries"][-1]
    if results:
        status = "resolved"
    elif latest["status"] == "rejected":
        status = "needs_reconciliation"
    elif latest["first_unknown_utc"] is None:
        status = "needs_reconciliation"
    else:
        status = "eligible" if now >= latest["expires_utc"] else "waiting"
    selection = select_role(ctx["cfg"], scope["role"], stage=scope["stage"],
                            allowed_providers=scope["allowed_providers"], author_profiles=scope["author_profiles"],
                            author_invocations=scope["author_invocations"], invocation_id="uncertainty-status-observer",
                            _uncertainty_reserve=True)
    attempted = {tuple(entry["model_tuple"]) for entry in state["entries"]}
    remaining = [entry["profile"] for entry in selection["candidates"] if (entry["provider"], entry["model"]) not in attempted]
    if status == "eligible" and not remaining:
        status = "exhausted"
    ctx["frozen"]()
    protect_path(path, ctx["roots"])
    if persist:
        atomic_json(path, state)
    return state, {"status": status, "root_assignment_id": state["root_assignment_id"],
                   "current_assignment_id": latest["assignment_id"], "first_unknown_utc": latest["first_unknown_utc"],
                   "expires_utc": latest["expires_utc"], "uncertainty_basis": latest["uncertainty_basis"],
                   "remaining_profiles": remaining, "results": results, "inference_started": False,
                   "remote_termination_confirmed": False,
                   "clock_limitation": "Persisted UTC cannot detect an unobservable forward wall-clock jump.",
                   "next": "Independent evidence intake is required before applying any output."}


def uncertainty_status(config_path, *, source_id, workdir, task_sha256, stage, role,
                       parent_permissions=None, protection_context_file=None, allowed_providers=None,
                       author_profiles=(), author_invocations=(), outcome_uncertain=False, _now=None):
    now = uncertainty_time(time.time() if _now is None else _now)
    scope = uncertainty_scope(task_sha256=task_sha256, role=role, stage=stage, allowed_providers=allowed_providers,
                              author_profiles=author_profiles, author_invocations=author_invocations)
    ctx = uncertainty_context(config_path, workdir, parent_permissions, protection_context_file)
    path = uncertainty_chain_path(ctx, source_id)
    try:
        with UncertaintyLock(str(path) + ".lock", ctx["roots"]):
            _, result = uncertainty_reconcile(ctx, path, scope, now, outcome_uncertain, source_id)
            return result
    except WorkflowError as error:
        if error.code == "uncertainty_busy":
            return {"status": "busy", "inference_started": False}
        raise


def uncertainty_continue(config_path, *, source_id, workdir, task_sha256, stage, role,
                         purpose, profile_id, assignment_id, invocation_id, prompt, output_dir,
                         authorization_file, parent_permissions=None, protection_context_file=None,
                         allowed_providers=None, author_profiles=(), author_invocations=(),
                         external_blockers=(), needs_tools=False, outcome_uncertain=False,
                         http_opener=None, _now=None):
    now = uncertainty_time(time.time() if _now is None else _now)
    scope = uncertainty_scope(task_sha256=task_sha256, role=role, stage=stage, allowed_providers=allowed_providers,
                              author_profiles=author_profiles, author_invocations=author_invocations)
    if needs_tools or (role, purpose) not in {("external", "analysis"), ("reviewer", "review")}:
        fail("uncertainty_scope", "Only text analysis/review without tools or external effects is permitted.")
    identifier(assignment_id, "new assignment", assignment=True)
    identifier(invocation_id, "new invocation")
    ctx = uncertainty_context(config_path, workdir, parent_permissions, protection_context_file)
    model = ctx["cfg"]["models"].get(profile_id)
    if model is None:
        fail("missing_profile", "Selected continuation profile is not configured.")
    if model["transport"] != "text-api" or model["adapter"] is not None:
        fail("desktop_execution_required" if model["transport"] == "desktop" else "uncertainty_host_required",
             "Selected profile requires its qualified host; text continuation cannot execute Desktop/native/adapters.")
    path = uncertainty_chain_path(ctx, source_id)
    with UncertaintyLock(str(path) + ".lock", ctx["roots"]) as lock:
        # Validate without writing an observation on denied child preflight.
        if not path.exists():
            fail("uncertainty_observation_required", "Record the first protected uncertainty observation before continuation.")
        state = uncertainty_read_state(path)
        uncertainty_validate_state(ctx, state, scope, now)
        _, current = uncertainty_reconcile(ctx, path, scope, now, outcome_uncertain, source_id, persist=False)
        if current["status"] == "resolved":
            fail("uncertainty_resolved", "A matching completion already resolves this chain; use normal intake or new delta scope.")
        pair = list(model_tuple(model))
        if any(entry["model_tuple"] == pair or entry["assignment_id"] == assignment_id
               or entry["invocation_id"] == invocation_id for entry in state["entries"]):
            fail("uncertainty_attempted", "This model/assignment/invocation was already recorded; reconcile instead of replaying.")
        if current["status"] != "eligible":
            fail("uncertainty_" + current["status"], "Chain is not eligible for a fresh assignment; no request was sent.")
        # Reconciliation must not persist on a preflight failure. The callback
        # performs it after ordinary authorization/key/prompt/path validation.
        def commit(receipt, receipt_path, result_path, frozen):
            frozen(); ctx["frozen"]()
            state, result = uncertainty_reconcile(ctx, path, scope, now, outcome_uncertain, source_id)
            if result["status"] != "eligible":
                fail("uncertainty_" + result["status"], "Chain is not eligible for a fresh assignment; no request was sent.")
            identity = {field: receipt[field] for field in (
                "schema_version", "assignment_id", "invocation_id", "role", "profile", "provider", "model", "effort",
                "transport", "protocol", "config_sha256", "authorization_sha256", "parent_permissions_sha256",
                "prompt_sha256", "workdir", "output_dir", "author_invocations")}
            identity["expected_result"] = str(result_path)
            entry = uncertainty_entry({"identity": identity, "receipt_sha256": None, "status": "intent", "result_sha256": None})
            entry["intent"] = {"root_assignment_id": state["root_assignment_id"], "config_sha256": ctx["config_sha256"],
                               "task_sha256": scope["task_sha256"], "authorization_sha256": receipt["authorization_sha256"],
                               "permissions_sha256": receipt["parent_permissions_sha256"], "prompt_sha256": receipt["prompt_sha256"],
                               "purpose": purpose, "created_utc": now}
            state["entries"].append(entry)
            frozen(); ctx["frozen"](); protect_path(path, ctx["roots"])
            atomic_json(path, state)
            lock.release()
        try:
            dispatch_result = dispatch(config_path, role=role, profile_id=profile_id, assignment_id=assignment_id, workdir=workdir,
                     prompt=prompt, output_dir=output_dir, authorization_file=authorization_file,
                     parent_permissions=parent_permissions, protection_context_file=protection_context_file,
                     stage=stage, allowed_providers=allowed_providers, author_profiles=author_profiles,
                     author_invocations=author_invocations, invocation_id=invocation_id,
                     external_blockers=external_blockers, needs_tools=False, http_opener=http_opener,
                     _before_text_launch=commit, _uncertainty_reserve=True)
        except WorkflowError:
            if lock.handle is None:
                # Persist first observation of an actual unknown result, then
                # preserve the ordinary dispatch error. Never retry an intent.
                uncertainty_status(config_path, source_id=source_id, workdir=workdir, task_sha256=task_sha256,
                                   stage=stage, role=role, parent_permissions=parent_permissions,
                                   protection_context_file=protection_context_file, allowed_providers=allowed_providers,
                                   author_profiles=author_profiles, author_invocations=author_invocations, _now=_now)
            raise
    result = uncertainty_status(config_path, source_id=source_id, workdir=workdir, task_sha256=task_sha256,
                                stage=stage, role=role, parent_permissions=parent_permissions,
                                protection_context_file=protection_context_file, allowed_providers=allowed_providers,
                                author_profiles=author_profiles, author_invocations=author_invocations, _now=_now)
    # This success path has a returned text completion, unlike status-only
    # observation or a durable intent whose request outcome remains unknown.
    result.update(inference_started=True, dispatch=dispatch_result)
    return result


def hidden_process_options():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


class MetadataRPC:
    """Bounded metadata-only JSONL client; server content is never logged."""
    def __init__(self, argv, timeout=15):
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
            fail("invalid_timeout", "Metadata RPC timeout must be between 0 and 60 seconds.")
        self.argv = argv
        self.timeout = timeout
        self.process = None
        self.messages = queue.Queue(maxsize=32)
        self.reader_failed = threading.Event()
        self.sequence = 0

    def __enter__(self):
        try:
            self.process = subprocess.Popen(self.argv, shell=False, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                            **hidden_process_options())
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
            self.call("initialize", {"clientInfo": {"name": "workflow_metadata", "version": "1.0"}})
            self._send({"method": "initialized", "params": {}})
            return self
        except (OSError, WorkflowError):
            self.close()
            fail("metadata_handshake_blocked", "Pinned metadata server handshake failed or requested client action; no approval response or inference was sent.")

    def __exit__(self, *_):
        self.close()

    def _read(self):
        stream = self.process.stdout
        try:
            while True:
                raw = stream.readline(MAX_LINE + 1)
                if not raw:
                    self.messages.put_nowait(None)
                    return
                if len(raw) > MAX_LINE:
                    self.reader_failed.set()
                    return
                message = json.loads(raw.decode("utf-8"), object_pairs_hook=json_pairs)
                if not isinstance(message, dict):
                    self.reader_failed.set()
                    return
                self.messages.put_nowait(message)
        except (OSError, ValueError, UnicodeError, queue.Full, WorkflowError):
            self.reader_failed.set()

    def _send(self, message):
        try:
            self.process.stdin.write(json.dumps(message, ensure_ascii=True).encode("utf-8") + b"\n")
            self.process.stdin.flush()
        except (OSError, ValueError, AttributeError):
            fail("metadata_disconnected", "Metadata server disconnected; raw protocol and error bodies are suppressed.")

    def call(self, method, params):
        if method not in RPC_METHODS:
            fail("rpc_forbidden", "Only initialize and thread start/list/read metadata RPC are allowed.")
        self._validate_params(method, params)
        self.sequence += 1
        request_id = self.sequence
        self._send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self.reader_failed.is_set():
                fail("metadata_protocol_blocked", "Metadata server emitted malformed/oversized content; no raw data is logged.")
            try:
                message = self.messages.get(timeout=min(0.1, max(0.001, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if message is None:
                fail("metadata_disconnected", "Metadata server exited before a response; acceptance may be unknown.")
            if "method" in message and "id" in message:
                fail("metadata_client_action_blocked", "Metadata server requested approval or another client action; no response was synthesized.")
            if message.get("id") != request_id:
                continue
            if "error" in message or not isinstance(message.get("result"), dict):
                fail("metadata_rpc_error", "Metadata RPC failed; server error bodies are suppressed.")
            return message["result"]
        fail("metadata_timeout", "Metadata RPC timed out; this is not an overall model-work deadline. Ambiguous creation must not replay.")

    @staticmethod
    def _validate_params(method, params):
        if method == "initialize":
            if params != {"clientInfo": {"name": "workflow_metadata", "version": "1.0"}}:
                fail("rpc_forbidden", "Initialize parameters must be fixed metadata client information.")
        elif method == "thread/start":
            object_keys(params, {"cwd", "model", "modelProvider", "approvalPolicy", "approvalsReviewer", "sandbox", "ephemeral", "allowProviderModelFallback"}, "thread start metadata")
            if (params["approvalPolicy"] != "on-request" or params["approvalsReviewer"] != "auto_review"
                    or params["sandbox"] != "read-only" or params["ephemeral"] is not False
                    or params["allowProviderModelFallback"] is not False):
                fail("rpc_forbidden", "Thread metadata requires read-only/on-request/auto_review and no provider fallback.")
            absolute_path(params["cwd"], "Thread working root")
            identifier(params["model"], "requested model")
            identifier(params["modelProvider"], "requested provider")
        elif method == "thread/read":
            object_keys(params, {"threadId", "includeTurns"}, "thread read metadata")
            identifier(params["threadId"], "thread ID")
            if params["includeTurns"] is not False:
                fail("rpc_forbidden", "Thread read must exclude turns and messages.")
        else:
            object_keys(params, {"limit", "cwd", "modelProviders", "useStateDbOnly"}, "thread list metadata", {"cursor"})
            if type(params["limit"]) is not int or not 1 <= params["limit"] <= 100 or params["useStateDbOnly"] is not True:
                fail("rpc_forbidden", "Metadata listing must be bounded and avoid rollout repair.")
            absolute_path(params["cwd"], "Thread working root")
            string_list(params["modelProviders"], "provider filter")
            if "cursor" in params:
                bounded_text(params["cursor"], "pagination cursor", 2048)

    def close(self):
        process = self.process
        if process is None:
            return
        self.process = None
        try:
            if process.stdin:
                process.stdin.close()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()  # Only this owned metadata server, never an inference worker.
                    process.wait(timeout=2)
        finally:
            if process.stdout:
                process.stdout.close()


def thread_metadata(thread):
    if not isinstance(thread, dict):
        fail("invalid_metadata", "Missing thread metadata object.")
    result = {}
    for field in ("id", "sessionId"):
        if field in thread and thread[field] is not None:
            result[field] = identifier(thread[field], "returned thread identity")
    for field in ("createdAt", "updatedAt"):
        if type(thread.get(field)) is int and 0 <= thread[field] <= 2 ** 63 - 1:
            result[field] = thread[field]
    if type(thread.get("ephemeral")) is bool:
        result["ephemeral"] = thread["ephemeral"]
    if "id" not in result:
        fail("invalid_metadata", "Server did not return a bounded thread ID; creation remains unknown.")
    return result


@contextmanager
def state_lock(path):
    lock = Path(str(path) + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        fail("state_locked", "Folder state is locked. Do not steal ownership; reconcile the existing process/lock first.")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(str(os.getpid()).encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        lock.unlink()


def state_path_for(root):
    path = root / "docs" / "workflow-state.json"
    if path.is_symlink() or not is_within(path.resolve(), root):
        fail("unsafe_state", "Folder technical state must resolve inside its canonical working root and cannot be a symlink.")
    return path


def load_state(path, root):
    if not path.exists():
        return {"schema_version": 1, "root": str(root), "sprints": {}}
    state = read_json(path)
    object_keys(state, {"schema_version", "root", "sprints"}, "folder technical state")
    if type(state["schema_version"]) is not int or state["schema_version"] != 1 or state["root"] != str(root) or not isinstance(state["sprints"], dict):
        fail("root_mismatch", "Technical state belongs to another root or unsupported format; reconcile before creating a chat.")
    for sprint, record in state["sprints"].items():
        identifier(sprint, "sprint", assignment=True)
        object_keys(record, {"parent_chat_id", "status", "requested_profile", "platform", "authorization_sha256"}, "sprint record", {"thread_id"})
        identifier(record["parent_chat_id"], "managing chat")
        identifier(record["requested_profile"], "requested profile")
        digest_pin(record["authorization_sha256"])
        if (not isinstance(record["status"], str) or record["status"] not in {"pending", "confirmed", "unknown"}
                or not isinstance(record["platform"], str) or record["platform"] not in {"windows", "linux"}):
            fail("invalid_state", "Invalid sprint technical status/platform.")
        if record["status"] == "confirmed":
            identifier(record.get("thread_id"), "confirmed thread")
    return state


def metadata_factory(cfg, root, rpc_factory):
    if rpc_factory is not None:
        return rpc_factory()  # Python API injection is for local tests, never a CLI option.
    executable = server_executable(cfg, root)
    return MetadataRPC([str(executable), "app-server"])


def chat_create(config_path, workdir, sprint_id, parent_chat_id, authorization_file, *, rpc_factory=None):
    identifier(sprint_id, "sprint", assignment=True)
    identifier(parent_chat_id, "managing chat")
    root = absolute_path(workdir, "Working root", must_exist=True)
    if not root.is_dir():
        fail("invalid_path", "Working root must be a folder.")
    config_path = require_outside(config_path, root)
    cfg = load_config(config_path)
    doc = load_authorization(authorization_file, root)
    require_authorization(doc, "chat", root, sprint_id=sprint_id, parent_chat_id=parent_chat_id)
    selected = select_role(cfg, "orchestrator")["candidates"][0]
    if selected["provider"] not in cfg["primary_providers"]:
        fail("external_chat_creation_unavailable", "Persistent coordination chat allocation requires an internal provider.")
    path = state_path_for(root)
    with state_lock(path):
        state = load_state(path, root)
        existing = state["sprints"].get(sprint_id)
        if existing:
            if existing["parent_chat_id"] != parent_chat_id:
                fail("parent_mismatch", "Sprint belongs to another managing chat; reuse cannot cross parent scope.")
            if existing["status"] != "confirmed":
                fail("chat_creation_unknown", "Sprint has pending/unknown creation; reconcile with stored server metadata before another attempt. No retry was sent.")
            return {"status": "existing", "thread_id": existing["thread_id"], "desktop_visibility_confirmed": False}
        if selected["requires_consent"]:
            require_authorization(doc, "top", root, assignment_id=sprint_id, role="orchestrator", profile=selected["profile"])
        # Resolve prerequisite before reserving state; no RPC is sent here.
        if rpc_factory is None:
            server_executable(cfg, root)
        record = {"parent_chat_id": parent_chat_id, "status": "pending",
                  "requested_profile": selected["profile"], "platform": host_platform(),
                  "authorization_sha256": file_hash(authorization_file)}
        state["sprints"][sprint_id] = record
        atomic_json(path, state)
        params = {"cwd": str(root), "model": selected["model"], "modelProvider": native_provider(cfg, selected["provider"]),
                  "approvalPolicy": "on-request", "approvalsReviewer": "auto_review", "sandbox": "read-only",
                  "ephemeral": False, "allowProviderModelFallback": False}
        try:
            with metadata_factory(cfg, root, rpc_factory) as rpc:
                result = rpc.call("thread/start", params)
                meta = thread_metadata(result.get("thread"))
            record["thread_id"] = meta["id"]
            record["status"] = "confirmed"
            atomic_json(path, state)
        except (WorkflowError, OSError):
            record.pop("thread_id", None)
            record["status"] = "unknown"
            atomic_json(path, state)
            fail("chat_creation_unknown", "Sprint metadata creation is unknown; reconcile server records. No automatic recreation, raw messages or error bodies.")
    return {"status": "created_metadata_only", "thread_id": record["thread_id"],
            "desktop_visibility_confirmed": False, "inference_started": False}


def chat_list(config_path, workdir, *, limit=50, cursor=None):
    root = absolute_path(workdir, "Working root", must_exist=True)
    cfg = load_config(require_outside(config_path, root))
    # A provider filter respects mode while permitting all configured eligible profiles.
    providers = sorted({native_provider(cfg, model["provider"]) for model in cfg["models"].values()
                        if (cfg["mode"] != "primary-only" or model["provider"] in cfg["primary_providers"])
                        and (cfg["mode"] != "external-only" or model["provider"] not in cfg["primary_providers"])})
    if not providers:
        fail("no_eligible_role", "Configure eligible provider profiles before listing persistent metadata.")
    params = {"cwd": str(root), "limit": limit, "modelProviders": providers, "useStateDbOnly": True}
    if cursor is not None:
        params["cursor"] = cursor
    MetadataRPC._validate_params("thread/list", params)
    with metadata_factory(cfg, root, None) as rpc:
        result = rpc.call("thread/list", params)
    data = result.get("data")
    if not isinstance(data, list) or len(data) > limit:
        fail("invalid_metadata", "Server returned invalid/unbounded metadata list.")
    output = {"threads": [thread_metadata(thread) for thread in data]}
    if result.get("nextCursor") is not None:
        output["next_cursor"] = bounded_text(result["nextCursor"], "pagination cursor", 2048)
    return output


def chat_read(config_path, workdir, thread_id):
    identifier(thread_id, "thread ID")
    root = absolute_path(workdir, "Working root", must_exist=True)
    cfg = load_config(require_outside(config_path, root))
    with metadata_factory(cfg, root, None) as rpc:
        result = rpc.call("thread/read", {"threadId": thread_id, "includeTurns": False})
    return {"thread": thread_metadata(result.get("thread"))}


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, "Blocked: invalid CLI arguments; run --help. Untrusted argument values are not echoed.\n")


def parser():
    cli = SafeArgumentParser(description="Portable workflow: text assignments, protected native persistent sprint sessions and metadata inspection.")
    cli.add_argument("--config", type=Path, help="Protected user config (default WORKFLOW_HOME or ~/.tokenband).")
    commands = cli.add_subparsers(dest="command", required=True)
    for command in ("init", "validate", "doctor"):
        commands.add_parser(command)
    def selection_args(sub):
        sub.add_argument("--role", required=True, choices=sorted(ROLES | {"external", "reviewer"}))
        sub.add_argument("--stage", default="ordinary", choices=sorted(STAGES))
        sub.add_argument("--allowed-provider", action="append", dest="allowed_providers")
        sub.add_argument("--author-profile", action="append", default=[], dest="author_profiles")
        sub.add_argument("--author-invocation", action="append", default=[], dest="author_invocations")
        sub.add_argument("--invocation-id")
        sub.add_argument("--needs-tools", action="store_true", help="Require native file/shell/edit capability; exclude text-only transports.")
    selection_args(commands.add_parser("select"))
    sub = commands.add_parser("dispatch")
    selection_args(sub)
    for field in ("profile", "assignment-id", "workdir", "prompt", "output-dir", "authorization-file"):
        sub.add_argument("--" + field, required=True)
    sub.add_argument("--parent-permissions")
    sub.add_argument("--protection-context", dest="protection_context_file", help="Trusted neutral text protection-only envelope; no tools granted.")
    sub.add_argument("--external-blocker", action="append", default=[], dest="external_blockers", help="Profile ID with an assignment-specific recorded obstacle; no automatic fallback.")
    for command in ("uncertainty-status", "uncertainty-continue"):
        sub = commands.add_parser(command, help="Protected 900-second text uncertainty observation/continuation; no replay or tools.")
        if command == "uncertainty-continue":
            selection_args(sub)
            # An explicit legacy assertion must never silently default the stage.
            next(action for action in sub._actions if action.dest == "stage").required = True
            next(action for action in sub._actions if action.dest == "invocation_id").required = True
            for field in ("profile", "assignment-id", "prompt", "output-dir", "authorization-file"):
                sub.add_argument("--" + field, required=True)
            sub.add_argument("--purpose", required=True, choices=["analysis", "review"])
            sub.add_argument("--external-blocker", action="append", default=[], dest="external_blockers")
        else:
            sub.add_argument("--role", required=True, choices=["external", "reviewer"])
            sub.add_argument("--stage", required=True, choices=sorted(STAGES))
            sub.add_argument("--allowed-provider", action="append", dest="allowed_providers")
            sub.add_argument("--author-profile", action="append", default=[], dest="author_profiles")
            sub.add_argument("--author-invocation", action="append", default=[], dest="author_invocations")
        for field in ("source-id", "workdir", "task-sha256"):
            sub.add_argument("--" + field, required=True)
        context = sub.add_mutually_exclusive_group(required=True)
        context.add_argument("--parent-permissions")
        context.add_argument("--protection-context", dest="protection_context_file")
        sub.add_argument("--outcome-uncertain", action="store_true", help="Trusted lost-outcome assertion for this prepared/launch_started source; never proves termination.")
    sub = commands.add_parser("chat-metadata-create", aliases=["chat-create"], help="Internal metadata-only allocation; does not execute a sprint.")
    for field in ("workdir", "sprint-id", "parent-chat-id", "authorization-file"):
        sub.add_argument("--" + field, required=True)
    sub = commands.add_parser("chat-list")
    sub.add_argument("--workdir", required=True)
    sub.add_argument("--limit", type=int, default=50)
    sub.add_argument("--cursor")
    sub = commands.add_parser("chat-read")
    sub.add_argument("--workdir", required=True)
    sub.add_argument("--thread-id", required=True)
    sub = commands.add_parser("native-probe", help="Local native config/kernel/synthetic shell checks; no inference or chat.")
    sub.add_argument("--workdir", required=True)
    sub.add_argument("--parent-context", required=True)
    sub.add_argument("--linkage-file", help="Protected exact native-handler linkage; enables full qualification probe receipts.")
    sub.add_argument("--linkage-sha256")
    sub = commands.add_parser("native-qualify", help="Closed synthetic same-sprint native qualification; never sends a real brief.")
    for field in ("workdir", "sprint", "parent", "authorization-file", "parent-context", "local-probe-receipt"):
        sub.add_argument("--" + field, required=True)
    for operation in ("create", "send", "status", "reconcile", "steer", "interrupt"):
        help_text = "Unavailable for foreground owners; terminal same-ID follow-up is supported." if operation in {"steer", "interrupt"} else ("Read terminal/released-owner native status; live foreground CLI status is unavailable." if operation == "status" else None)
        sub = commands.add_parser("sprint-" + operation, help=help_text, description=help_text)
        sub.add_argument("--profile", dest="profile_id", help="Явный main_external либо eligible reserve_primary; выбор не является разрешением передачи записи.")
        for field in ("workdir", "sprint", "parent", "authorization-file"):
            sub.add_argument("--" + field, required=True)
        context = sub.add_mutually_exclusive_group(required=True)
        context.add_argument("--parent-context")
        context.add_argument("--protection-context")
        if operation in {"create", "send", "steer"}:
            sub.add_argument("--brief", required=True)
        sub.add_argument("--operation-id", default="create" if operation == "create" else None,
                         required=operation in {"send", "steer", "interrupt"})
        if operation in {"steer", "interrupt"}:
            sub.add_argument("--expected-turn-id", required=True)
    return cli


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = vars(parser().parse_args(argv))
    command = args.pop("command")
    config_path = args.pop("config")
    try:
        if config_path is None:
            config_path = default_config_path()
        if command == "init":
            result = init_config(config_path.resolve())
        elif command == "validate":
            load_config(config_path)
            result = {"status": "valid_structure", "inference_started": False}
        elif command == "doctor":
            result = doctor(config_path)
        elif command == "select":
            result = select_role(load_config(config_path), **args)
        elif command == "dispatch":
            args["profile_id"] = args.pop("profile")
            result = dispatch(config_path, **args)
        elif command == "uncertainty-status":
            result = uncertainty_status(config_path, **args)
        elif command == "uncertainty-continue":
            args["profile_id"] = args.pop("profile")
            result = uncertainty_continue(config_path, **args)
        elif command.startswith("sprint-"):
            operation = command[len("sprint-"):]
            args["needs_tools"] = args["parent_context"] is not None
            if args["protection_context"] is not None:
                args["parent_context"] = args["protection_context"]
            args.pop("protection_context")
            args["command"] = operation
            result = native_module().run(config_path, **args)
        elif command in {"chat-create", "chat-metadata-create"}:
            result = chat_create(config_path, **args)
            result.update(metadata_only=True, inference_started=False, deprecated_alias=command == "chat-create")
        elif command == "chat-list":
            result = chat_list(config_path, **args)
        elif command == "native-probe":
            result = native_module().probe(config_path, **args)
        elif command == "native-qualify":
            native_module()
            result = sys.modules["native_qualification"].run(config_path, **args)
        else:
            result = chat_read(config_path, **args)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    except WorkflowError as error:
        print(json.dumps({"status": "blocked", "code": error.code, "message": str(error)}, ensure_ascii=True), file=sys.stderr)
        return 2
    except OSError:
        print(json.dumps({"status": "blocked", "code": "local_io_error", "message": "Local file/process operation failed; raw errors are suppressed."}), file=sys.stderr)
        return 2
    except Exception:
        print(json.dumps({"status": "blocked", "code": "unexpected_local_error", "message": "Unexpected local failure; raw data is suppressed. Reconcile any pending receipt/state before another launch."}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    # Native modules share this exact WorkflowError class when invoked as a CLI.
    sys.modules.setdefault("worker", sys.modules[__name__])
    raise SystemExit(main())
