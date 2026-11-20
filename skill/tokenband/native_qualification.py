"""Closed synthetic qualification of the existing native sprint, never a brief.

Protected independent linkage/probe evidence must precede any model call. JSON
validation does not authenticate its human reviewer; provenance belongs to the
trusted caller. Actual native tool items, never model prose, supply observations.
"""
from __future__ import annotations
import hashlib
import json
import os
import shlex
import stat
from pathlib import Path
import re
import sys
import uuid
import worker as w
import native_sprint as n

REAL_RECIPE = "actual-real-edit-restore-v1"
PATCH_RECIPE = "native-real-edit-restore-verification-v1"
PATCH_OBSERVATION = "successful-native-real-edit-restored-patch-v1"
MAX_FAMILIES = 8
ITEM_TYPES = {"shell": "commandExecution", "patch": "fileChange"}
READINESS = "Return a short readiness confirmation. Do not use tools, files, delegation or perform sprint work."
PROBE_CODE = "import pathlib,sys\ntry:\n pathlib.Path(sys.argv[1]).read_bytes()\nexcept PermissionError:\n sys.exit(41)\nexcept OSError:\n sys.exit(42)\nsys.exit(0)"


def local_probe_command(path):
    return [str(Path(sys.executable).resolve()), "-I", "-c", PROBE_CODE, str(path)]


def fixture_identity(path):
    value = Path(path).stat()
    return {"device": value.st_dev, "inode": value.st_ino}


def exact(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        w.fail("invalid_qualification_evidence", "Unexpected " + label + " shape; evidence contents suppressed.")


def load_reference(config, reference, roots, frozen):
    exact(reference, {"path", "sha256"}, "protected reference")
    w.digest_pin(reference["sha256"])
    raw, path = config.path_context.resolve_pair(reference["path"])
    w.protect_path(raw, roots)
    if path.stat().st_size > w.MAX_JSON:
        w.fail("oversize_qualification_evidence", "Qualification evidence exceeds its bound.")
    record = n.freeze_file(raw, reference["sha256"])
    value = w.read_json(path)
    n.check_frozen(record, roots)
    frozen.append(record)
    return value


def acceptance(config, reference, artifact, author, binding, roots, frozen):
    review = load_reference(config, reference, roots, frozen)
    exact(review, {"schema", "kind", "decision", "reviewer", "author", "artifact_sha256", "binding_sha256", "source"}, "independent acceptance")
    if (type(review["schema"]) is not int or review["schema"] != 1 or review["kind"] != "independent-native-acceptance"
            or review["decision"] != "accept" or review["author"] != author
            or not isinstance(review["reviewer"], str) or not review["reviewer"] or review["reviewer"] == author
            or review["artifact_sha256"] != artifact or review["binding_sha256"] != n.digest(binding)):
        w.fail("missing_independent_acceptance", "Exact independent linkage/probe acceptance is required before inference.")
    w.bounded_text(review["source"], "trusted independent acceptance source", 8192)


def fixtures(config, probe, binding, home, root, frozen):
    attempt = probe["attempt"]
    if not isinstance(attempt, str) or not re.fullmatch(r"[0-9a-f]{32}", attempt):
        w.fail("invalid_synthetic_fixture", "Synthetic fixture attempt must be a full random marker.")
    actual = probe["schema"] == 2
    result = {}
    entries = probe["fixtures"]
    if not isinstance(entries, dict) or set(entries) != ({"allowed"} if actual else {"allowed", "denied"}):
        w.fail("invalid_synthetic_fixture", "Both exact pre-created synthetic fixtures are required.")
    for case in (("allowed",) if actual else ("allowed", "denied")):
        entry = entries[case]
        exact(entry, {"lexical", "canonical", "sha256", "identity"}, "synthetic fixture")
        expected = root / (".workflow-qualification-" + attempt + "-allowed.txt") if case == "allowed" else home / "native-qualification-fixtures" / attempt / "denied.txt"
        raw = w.lexical_path(entry["lexical"], "Synthetic fixture")
        if raw != expected or raw.resolve() != Path(entry["canonical"]) or raw.is_symlink():
            w.fail("invalid_synthetic_fixture", "Fixture is not the exact reserved synthetic path.")
        if case == "denied" and not all(any(w.is_within(raw.resolve(), Path(path).resolve())
                for path, permission in binding["profiles"][stage]["filesystem"].items() if not path.startswith(":") and permission == "deny") for stage in ("init", "task")):
            w.fail("invalid_synthetic_fixture", "Denied fixture must remain in an already-final native deny namespace.")
        token = "workflow-qualification:" + attempt + ":" + case
        if raw.stat().st_size > 256 or raw.read_bytes() != (token + "\n").encode("ascii") or entry["identity"] != fixture_identity(raw):
            w.fail("invalid_synthetic_fixture", "Fixture must contain its exact synthetic noncredential marker followed by one LF.")
        record = n.freeze_file(raw, entry["sha256"])
        if case == "denied":
            frozen.append(record)
        result[case] = {"path": str(raw.resolve()), "cwd": str(root), "token": token, "record": record, "identity": entry["identity"]}
    return result


def prerequisites(config, spec, expected, context, home, workdir, probe_reference, reviews):
    """Validate full exact linkage and current native probes, never a model call."""
    roots, frozen, binding = context["_protection_roots"], [], spec["_binding"]
    actual = context.get("schema") == 2
    schema = 2 if actual else 1
    effective = binding.get("effective_native_executables")
    required_effective = {"main", "runner", "setup", "probe_interpreter"} if n.uses_windows_sandbox(context) else {"main", "probe_interpreter"}
    if not isinstance(effective, dict) or set(effective) != required_effective:
        w.fail("missing_materialized_native_pins", "Actual materialized native executable/helper paths and hashes must be independently pinned.")
    for record in effective.values():
        exact(record, {"lexical", "canonical", "sha256"}, "effective native executable")
        path = n.freeze_file(record["lexical"], record["sha256"])
        if str(path[1]) != record["canonical"]:
            w.fail("native_materialization_changed", "Materialized native executable target differs from accepted evidence.")
        n.check_frozen(path, roots)
        frozen.append(path)
    if Path(effective["probe_interpreter"]["canonical"]) != Path(sys.executable).resolve():
        w.fail("native_materialization_changed", "Probe interpreter differs from the independently accepted native command probe.")
    probe = load_reference(config, probe_reference, roots, frozen)
    exact(probe, {"schema", "kind", "author", "binding", "root", "attempt", "profile_names", "fixtures", "checks", "cleanup", "inference_started", "linkage"} | ({"filesystem_isolation"} if actual else set()), "native local probe")
    root = Path(expected["cwd"])
    if (type(probe["schema"]) is not int or probe["schema"] != schema or (actual and probe["filesystem_isolation"] is not False) or probe["kind"] != "native-local-probe"
            or probe["binding"] != binding or probe["inference_started"] is not False
            or probe["root"] != {"lexical": str(w.lexical_path(workdir, "Qualification root")), "canonical": str(root)}
            or not isinstance(probe["cleanup"], dict) or probe["cleanup"].get("empty") is not True):
        w.fail("qualification_scope_changed", "Current local native probe does not cover exact final scope and kernel cleanup.")
    linkage = load_reference(config, probe["linkage"], roots, frozen)
    exact(linkage, {"schema", "kind", "author", "binding", "release", "inventory"} | ({"filesystem_isolation"} if actual else set()), "tool-handler linkage")
    if (type(linkage["schema"]) is not int or linkage["schema"] != schema or (actual and linkage["filesystem_isolation"] is not False) or linkage["kind"] != "native-tool-linkage"
            or linkage["binding"] != binding):
        w.fail("qualification_scope_changed", "Tool linkage does not cover exact current runtime/helpers/modules/context/profiles.")
    release = linkage["release"]
    exact(release, {"identity", "runtime_sha256", "native_helpers", "source"}, "native release linkage")
    if release["runtime_sha256"] != spec["sha256"] or release["native_helpers"] != binding["native_helpers"]:
        w.fail("unbound_native_release", "Exact executable and sandbox helpers require independently reviewed release/source correspondence.")
    w.bounded_text(release["identity"], "native release identity", 4096)
    load_reference(config, release["source"], roots, frozen)
    exact(reviews, {"probe", "linkage"}, "independent review references")
    acceptance(config, reviews["linkage"], probe["linkage"]["sha256"], linkage["author"], binding, roots, frozen)
    acceptance(config, reviews["probe"], probe_reference["sha256"], probe["author"], binding, roots, frozen)
    inventory = linkage["inventory"]
    if not isinstance(inventory, list) or not 1 <= len(inventory) <= MAX_FAMILIES:
        w.fail("missing_tool_linkage", "Every enabled native file-capable family needs exact linkage.")
    families = set()
    for family in inventory:
        exact(family, {"family", "item_type", "boundary", "profiles_sha256", "handler_source", "cases"}, "native family linkage")
        name = family["family"]
        if (not isinstance(name, str) or name not in ITEM_TYPES or name in families or family["item_type"] != ITEM_TYPES[name]
                or family["boundary"] != ("same-actual-native-permissions-v2" if actual else "same-generated-native-filesystem-permissions")
                or family["profiles_sha256"] != n.digest(binding["profiles"])):
            w.fail("missing_tool_linkage", "Unknown, duplicate or uncovered native handler family.")
        families.add(name)
        load_reference(config, family["handler_source"], roots, frozen)
        if not isinstance(family["cases"], dict) or set(family["cases"]) != ({"task_allowed"} if actual else {stage + "_" + case for stage in ("init", "task") for case in ("allowed", "denied")}):
            w.fail("missing_tool_linkage", "Every native family needs both positive and explicit denied access in both final profiles.")
        for case in family["cases"].values():
            validate_case(case, name, actual=actual)
    enabled = binding.get("enabled_tool_families")
    if (not isinstance(enabled, list) or any(not isinstance(name, str) or name not in ITEM_TYPES for name in enabled)
            or len(set(enabled)) != len(enabled) or families != set(enabled)):
        w.fail("missing_tool_linkage", "Linkage inventory differs from the exact native enabled-handler inventory.")
    names = probe["profile_names"]
    if not isinstance(names, dict) or set(names) != {"init", "task"} or any(not isinstance(x, str) or not x for x in names.values()):
        w.fail("invalid_native_probe", "Both exact final named profiles are required.")
    if actual and names != {"init": ":danger-full-access", "task": ":danger-full-access"}:
        w.fail("invalid_native_probe", "Actual probes must use the exact direct native builtin references.")
    checks = probe["checks"]
    if not isinstance(checks, list) or len(checks) != (2 if actual else 4):
        w.fail("invalid_native_probe", "Current native positive/PermissionError probes must cover both profiles.")
    observed = set()
    for check in checks:
        exact(check, {"stage", "case", "profile", "target", "command_sha256", "exit_code", "sentinel"}, "native command probe")
        stage, case = check["stage"], check["case"]
        if stage not in names or case not in ({"allowed"} if actual else {"allowed", "denied"}) or (stage, case) in observed or check["profile"] != names[stage]:
            w.fail("invalid_native_probe", "Native positive/denied checks use different or duplicate profiles.")
        observed.add((stage, case))
        w.digest_pin(check["command_sha256"])
        if type(check["exit_code"]) is not int or check["exit_code"] != (0 if case == "allowed" else 41) or check["sentinel"] != ("native-positive-read" if case == "allowed" else "native-PermissionError"):
            w.fail("invalid_native_probe", "Generic failure is not a native PermissionError confinement sentinel.")
        if check["target"] != probe["fixtures"][case]["canonical"]:
            w.fail("invalid_native_probe", "Native command probe tested a different fixture.")
        if check["command_sha256"] != n.digest(local_probe_command(check["target"])):
            w.fail("invalid_native_probe", "Native local probe did not use the exact bundled PermissionError program.")
    created = fixtures(config, probe, binding, home, root, frozen)
    return probe, linkage, created, frozen


def validate_case(case, family, actual=False):
    exact(case, {"recipe", "assertions"}, "qualified native case")
    if case["recipe"] != {"shell": "python-read-permission-sentinel-v1", "patch": PATCH_RECIPE if actual else "native-noop-patch-verification-v1"}[family]:
        w.fail("unsupported_native_fixture", "Native handler has no bundled reviewed synthetic recipe.")
    assertions = case["assertions"]
    if not isinstance(assertions, list) or not 1 <= len(assertions) <= 16:
        w.fail("invalid_native_fixture", "Native access needs bounded independently reviewed actual-item assertions.")
    for row in assertions:
        exact(row, {"item", "path", "equals"}, "native item assertion")
        if (not isinstance(row["path"], list) or not 1 <= len(row["path"]) <= 8
                or row["item"] not in {"operation", "output"}
                or any(not isinstance(key, (str, int)) or isinstance(key, bool) for key in row["path"])
                or row["path"][0] in {"text", "message", "reasoning"}
                or not isinstance(row["equals"], (str, int, bool, type(None)))):
            w.fail("invalid_native_fixture", "Native proof must inspect bounded actual tool metadata, never model prose.")
    if actual and family == "patch":
        required = {"item": "operation", "path": ["status"], "equals": "completed"}
        if required not in assertions or any(row["item"] != "operation" for row in assertions):
            w.fail("invalid_native_fixture", "Actual patch proof requires the completed native operation branch, without output assertions.")
        return
    # Legacy access/denial requires its existing exit or correlated output evidence.
    if not any((row["item"] == "operation" and row["path"][0] == "exitCode") or
               (row["item"] == "output" and row["path"] == ["output"]) for row in assertions):
        w.fail("invalid_native_fixture", "Actual native access/denial branch evidence is missing.")


def _model_read_argv(target):
    """Exact original model-read recipe; the no-model probe is distinct."""
    code = "import pathlib,sys\ntry:\n data=pathlib.Path(sys.argv[1]).read_bytes()\nexcept PermissionError:\n print('native-PermissionError');sys.exit(41)\nexcept OSError:\n sys.exit(42)\nprint(data.decode('ascii'));sys.exit(0)"
    return [str(Path(sys.executable).resolve()), "-I", "-c", code, target]


def _shell_command_matches(value, request):
    """Decode only the native full-argv display; never evaluate its script."""
    if not isinstance(value, str) or "\0" in value:
        return False
    try:
        if len(value.encode("utf-8")) > 128 * 1024:
            return False
        argv = shlex.split(value, comments=False, posix=True)
    except (ValueError, UnicodeError):
        return False
    if argv == _model_read_argv(request["target"]):
        return True
    if len(argv) not in (3, 4) or argv[-1] != request["command"]:
        return False
    executable = Path(argv[0])
    try:
        if not executable.is_absolute() or not executable.is_file() or not os.access(executable, os.X_OK):
            return False
    except OSError:
        return False
    flags = argv[1:-1]
    if w.host_platform() == "windows":
        name = executable.name.lower()
        if name in {"powershell.exe", "pwsh.exe", "powershell", "pwsh"}:
            return flags in (["-Command"], ["-NoProfile", "-Command"])
        return name in {"cmd.exe", "cmd"} and flags == ["/c"]
    return executable.name in {"bash", "zsh", "sh"} and flags in (["-c"], ["-lc"])


def plan(family, stage, case, fixture, *, actual=False):
    """No caller-supplied prompt or executable program is accepted."""
    path = fixture["path"]
    if family == "shell":
        argv = _model_read_argv(path)
        if w.host_platform() == "windows":
            command = "& " + " ".join("'" + arg.replace("'", "''") + "'" for arg in argv)
        else:
            command = " ".join("'" + arg.replace("'", "'\"'\"'") + "'" for arg in argv)
        text = "Synthetic qualification only. Use the native shell/command tool exactly once, with cwd unchanged, to run this exact command. Do not read other paths or use another tool. Return a short status.\n" + command
        return {"family": family, "stage": stage, "case": case, "target": path, "cwd": fixture["cwd"], "command": command, "text": text}
    written_token = fixture["token"] + (":written" if actual else "")
    patch = "*** Begin Patch\n*** Update File: " + path + "\n@@\n-" + fixture["token"] + "\n+" + written_token + "\n*** End Patch"
    text = "Synthetic qualification only. Submit exactly this " + ("real edit" if actual else "no-op patch") + " through the native patch tool once. Do not substitute shell/read tools, create a file, change other paths, or repeat a denial. Return a short status.\n" + patch
    request = {"family": family, "stage": stage, "case": case, "target": path, "cwd": fixture["cwd"], "patch": patch, "text": text}
    if actual:
        request["recipe"] = PATCH_RECIPE
    return request


def tool_evidence(items, turn_id, request, fixture, qualified_case, actual=False):
    if not isinstance(items, list) or len(items) != (1 if request["family"] == "shell" or actual else 2) or any(not isinstance(item, dict) for item in items):
        w.fail("native_tool_unqualified", "Exactly the planned native synthetic tool operation is required.")
    operations = [item for item in items if item.get("type") == ITEM_TYPES[request["family"]]]
    if len(operations) != 1 or not isinstance(operations[0].get("id"), str):
        w.fail("native_tool_unqualified", "Model prose or another tool family cannot establish native access.")
    item, output = operations[0], None
    w.identifier(item["id"], "native qualification tool item")
    if request["family"] == "shell":
        command_matches = _shell_command_matches(item.get("command"), request) if actual else item.get("command") == request["command"]
        if (not command_matches or item.get("cwd") != request["cwd"]
                or item.get("exitCode") != (0 if request["case"] == "allowed" else 41)):
            w.fail("native_tool_unqualified", "Native shell did not execute the exact planned read/sentinel program.")
        expected = fixture["token"] if request["case"] == "allowed" else "native-PermissionError"
        if not isinstance(item.get("aggregatedOutput"), str) or item["aggregatedOutput"].strip() != expected:
            w.fail("native_tool_unqualified", "Native positive/PermissionError output is missing or ambiguous.")
    elif actual:
        validate_case(qualified_case, "patch", actual=True)
        changes = item.get("changes")
        if (item.get("status") != "completed" or not Path(request["target"]).is_absolute()
                or not isinstance(changes, list) or len(changes) != 1
                or not isinstance(changes[0], dict) or changes[0].get("path") != request["target"]):
            w.fail("native_tool_unqualified", "Actual patch needs one completed native FileChange for the exact planned fixture path.")
    else:
        outputs = [row for row in items if row.get("type") == "functionCallOutput"]
        if (len(outputs) != 1 or outputs[0].get("id") != item["id"] or outputs[0].get("name") != "apply_patch"
                or not isinstance(outputs[0].get("output"), str) or len(outputs[0]["output"].encode("utf-8")) > 16384):
            w.fail("native_tool_unqualified", "Patch access needs exact correlated native handler output; failed status alone is insufficient.")
        output = outputs[0]
        if request["target"] not in output["output"]:
            w.fail("native_tool_unqualified", "Native patch output does not identify the exact synthetic target.")
        changes = item.get("changes", [])
        paths = {row.get("path") for row in changes if isinstance(row, dict)}
        if paths and paths != {request["target"]}:
            w.fail("native_tool_unqualified", "Patch operation affected an unplanned path.")
    for assertion in qualified_case["assertions"]:
        current = item if assertion["item"] == "operation" else output
        try:
            for key in assertion["path"]:
                current = current[key]
        except (KeyError, TypeError, IndexError):
            w.fail("native_tool_unqualified", "Qualified native access branch metadata is unavailable.")
        if type(current) is not type(assertion["equals"]) or current != assertion["equals"]:
            w.fail("native_tool_unqualified", "Actual native tool metadata does not demonstrate the qualified access branch.")
    w.identifier(turn_id, "qualification native turn")
    return {"turn_id": turn_id, "type": item["type"], "stage": request["stage"], "case": request["case"],
            "target": request["target"], "native_items": [{"id": row["id"], "type": row["type"], "sha256": n.digest(row)} for row in items], "status": "observed"}


def valid_tool_observation(row, family, actual=False):
    """Closed summary; actual patch has one native identity, legacy retains its pair."""
    if (not isinstance(row, dict) or set(row) != {"turn_id", "type", "stage", "case", "target", "native_items", "status"}
            or row.get("type") != ITEM_TYPES[family] or row.get("stage") not in {"init", "task"}
            or row.get("case") not in {"allowed", "denied"} or row.get("status") != "observed"
            or not isinstance(row.get("turn_id"), str) or not w.ID_RE.fullmatch(row["turn_id"])
            or not isinstance(row.get("target"), str) or not Path(row["target"]).is_absolute()):
        return False
    items = row.get("native_items")
    types = ["commandExecution"] if family == "shell" else (["fileChange"] if actual else ["fileChange", "functionCallOutput"])
    if not isinstance(items, list) or len(items) != len(types):
        return False
    if any(not isinstance(item, dict) or not isinstance(item.get("type"), str) for item in items) or sorted(item["type"] for item in items) != sorted(types):
        return False
    for item in items:
        if (set(item) != {"id", "type", "sha256"}
                or not isinstance(item.get("id"), str) or not w.ID_RE.fullmatch(item["id"])
                or not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])):
            return False
    return family == "shell" or actual or items[0]["id"] == items[1]["id"]


def qualification_requests(inventory, created, schema):
    if schema == 2:
        if {row["family"] for row in inventory} != {"shell", "patch"} or set(created) != {"allowed"}:
            w.fail("missing_tool_linkage", "Actual full-access recipe needs exactly shell/patch and one successful-read fixture.")
        # Stable tool-family order, independent of linkage JSON list ordering.
        for family in inventory:
            validate_case(family["cases"]["task_allowed"], family["family"], actual=True)
        return [plan(family, "task", "allowed", created["allowed"], actual=True) for family in ("shell", "patch")]
    return [plan(family["family"], stage, case, created[case]) for stage in ("init", "task")
            for family in inventory for case in ("allowed", "denied")]


def error_category(error):
    # Persist categories only, never native text, paths or exception messages.
    if isinstance(error, w.WorkflowError):
        return "workflow"
    if isinstance(error, OSError):
        return "filesystem"
    return "interrupted" if isinstance(error, (KeyboardInterrupt, SystemExit)) else "other"


def fixture_bytes(path):
    with Path(path).open("rb") as stream:
        return stream.read(257)


class FixturePhase:
    """One local patch interval; no restart recovery or journal-derived phase."""
    def __init__(self, created):
        self.created, self.interval, self.fd = created, False, None
        self.modes = {case: stat.S_IMODE(Path(fixture["path"]).stat().st_mode) for case, fixture in created.items()}

    def check(self):
        for case, fixture in self.created.items():
            raw, canonical, pin = fixture["record"]
            info = raw.lstat()
            if (not stat.S_ISREG(info.st_mode) or raw.resolve() != canonical
                    or fixture_identity(raw) != fixture["identity"] or stat.S_IMODE(info.st_mode) != self.modes[case]):
                w.fail("synthetic_fixture_changed", "Synthetic fixture path, identity or permissions changed.")
            original = (fixture["token"] + "\n").encode("ascii")
            permitted = (original, self.written) if self.interval and case == "allowed" else (original,)
            content = fixture_bytes(raw)
            if info.st_size > 256 or content not in permitted or (not self.interval and hashlib.sha256(content).hexdigest() != pin):
                w.fail("synthetic_fixture_changed", "Synthetic fixture content changed outside its owned patch interval.")

    def capture(self, operation):
        self.check()
        fixture = self.created["allowed"]
        raw, canonical, _ = fixture["record"]
        descriptor = os.open(raw, os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            info = os.fstat(descriptor)
            self.original = (fixture["token"] + "\n").encode("ascii")
            self.written = (fixture["token"] + ":written\n").encode("ascii")
            if (not stat.S_ISREG(info.st_mode) or {"device": info.st_dev, "inode": info.st_ino} != fixture["identity"]
                    or stat.S_IMODE(info.st_mode) != self.modes["allowed"] or os.read(descriptor, 257) != self.original):
                w.fail("synthetic_fixture_changed", "Checked patch descriptor no longer identifies the original fixture.")
            self.fd, self.operation = descriptor, operation
        except BaseException:
            os.close(descriptor)
            raise

    def _checked_content(self):
        self.check()
        fixture = self.created["allowed"]
        info = os.fstat(self.fd)
        if (not stat.S_ISREG(info.st_mode) or {"device": info.st_dev, "inode": info.st_ino} != fixture["identity"]
                or stat.S_IMODE(info.st_mode) != self.modes["allowed"]):
            w.fail("synthetic_fixture_changed", "Held patch descriptor identity or permissions changed.")
        os.lseek(self.fd, 0, os.SEEK_SET)
        content = os.read(self.fd, 257)
        if content not in (self.original, self.written) or fixture_bytes(fixture["path"]) != content:
            w.fail("synthetic_fixture_changed", "Patch descriptor/path does not contain the bounded expected fixture.")
        return content

    def require_written(self):
        if self._checked_content() != self.written:
            w.fail("native_tool_unqualified", "Completed native FileChange must actually write the exact distinct synthetic bytes.")

    def proof(self, journal, owned):
        fixture = self.created["allowed"]
        raw, canonical, _ = fixture["record"]
        operation = journal.lookup_operation(self.operation) or {}
        return {"recipe": REAL_RECIPE, "fixture": {"lexical": str(raw), "canonical": str(canonical),
            **fixture["identity"], "mode": self.modes["allowed"]},
            "original_sha256": hashlib.sha256(self.original).hexdigest(), "written_sha256": hashlib.sha256(self.written).hexdigest(),
            "restored_sha256": None, "patch_operation": self.operation, "patch_ack": operation.get("ack", {}),
            "patch_observation": operation.get("result"), "cleanup": owned, "outcome": "failed"}

    def restore(self, proof):
        if not proof["cleanup"]["empty"]:
            proof["outcome"] = "cleanupunknown"
            w.fail("cleanup_unknown", "Current owning connection lacks verified empty cleanup; fixture retained.")
        content = self._checked_content()
        if content == self.original:
            proof["outcome"] = "notneeded"
        else:
            os.lseek(self.fd, 0, os.SEEK_SET)
            remaining = memoryview(self.original)
            while remaining:
                size = os.write(self.fd, remaining)
                if size <= 0 or size > len(remaining):
                    w.fail("fixture_restoration_failed", "Synthetic in-place restoration did not complete.")
                remaining = remaining[size:]
            os.ftruncate(self.fd, len(self.original))
            os.fsync(self.fd)
            if self._checked_content() != self.original:
                w.fail("fixture_restoration_failed", "Synthetic in-place restoration verification failed.")
            proof["outcome"] = "restored"
        proof["restored_sha256"] = hashlib.sha256(self.original).hexdigest()
        self.interval = False
        self.check()

    def close_descriptor(self):
        if self.fd is not None:
            descriptor, self.fd = self.fd, None
            os.close(descriptor)


def execute(journal, driver, inventory, created, probe, frozen, roots, *, phase=None):
    """Real native driver/RPC lifecycle; tests replace peers, never this engine."""
    if journal.state.get("thread_id") or journal.has_operations():
        w.fail("qualification_exists", "Qualification has native history; reconcile the original sprint, never allocate again.")
    if not callable(getattr(driver, "qualification_turn", None)):
        w.fail("qualification_driver_unavailable", "Bundled native driver lacks the reviewed synthetic actual-tool observation path.")
    driver._prepare(journal)
    if driver.names != probe["profile_names"] or driver.definitions != driver.spec["_binding"]["profiles"]:
        w.fail("qualification_scope_changed", "Actual generated native profiles differ from the independently accepted local probe.")
    requests = qualification_requests(inventory, created, probe["schema"])
    instruction_digest = n.digest({"readiness": READINESS, "requests": requests})
    if instruction_digest != journal.state.get("qualification_instruction_sha256"):
        w.fail("qualification_scope_changed", "Frozen authorized synthetic instructions changed.")
    phase = phase or FixturePhase(created)
    if probe["schema"] == 2:
        journal.update(qualification_recipe=REAL_RECIPE)
    observations = []
    marker = uuid.uuid4().hex
    journal.update(attempt_marker=marker, qualification_status="qualifying")
    rpc = driver._open(journal)
    try:
        journal.perform("qualify_allocate", driver.expected, lambda: driver._thread(rpc, journal))
        title = "Sprint " + journal.identity["sprint"] + " " + marker
        journal.perform("qualify_name", title, lambda: rpc.call("thread/name/set", {"threadId": journal.state["thread_id"], "name": title}))
        result = journal.perform("qualify_initialize", n.digest(READINESS), lambda: driver._turn(rpc, journal, READINESS,
            marker + "-init", "init", "initialization_turn_id"))
        journal.update(readiness_digest=n.digest(result["public"]))
    finally:
        driver._close(rpc, journal)
    cleanup(journal)
    # Invalidate the first connection's proof before opening the owning tool connection.
    connection = uuid.uuid4().hex
    journal.update(cleanup={"empty": False, "connection": connection})
    rpc, primary, secondary = None, None, {}
    try:
        rpc = driver._open(journal)
        driver._persisted(rpc, journal)
        journal.update(backend_persistence="confirmed", client_visibility="pending")
        journal.perform("qualify_resume", journal.state["thread_id"], lambda: driver._thread(rpc, journal, True))
        for request in requests:
            phase.check()
            for record in frozen:
                n.check_frozen(record, roots)
            family = next(row for row in inventory if row["family"] == request["family"])
            operation = "qualify_" + request["stage"] + "_" + request["family"] + "_" + request["case"]
            if probe["schema"] == 2 and request["family"] == "patch":
                phase.capture(operation)
            def perform(request=request, family=family, operation=operation):
                if phase.fd is not None and request["family"] == "patch":
                    phase.interval = True
                result = driver.qualification_turn(rpc, journal, request["text"], operation,
                    request["stage"], "assignment_turn_id", observer=lambda items, turn_id: tool_evidence(items,
                        turn_id, request, created[request["case"]], family["cases"][request["stage"] + "_" + request["case"]], actual=probe["schema"] == 2))
                if phase.interval:
                    phase.require_written()
                return result
            observations.append(journal.perform(operation, n.digest(request), perform))
    except BaseException:
        primary = sys.exc_info()
    finally:
        close_attempted = rpc is not None
        if close_attempted:
            try:
                driver._close(rpc, journal)
            except BaseException:
                secondary["close"] = sys.exc_info()
        if phase.fd is not None:
            current = journal.state.get("cleanup")
            owned = {"connection": connection, "empty": bool(close_attempted and isinstance(current, dict) and current.get("empty") is True), "proof": current}
            proof = None
            try:
                proof = phase.proof(journal, owned)
                phase.restore(proof)
                if primary is None and proof["outcome"] != "restored":
                    w.fail("fixture_restoration_failed", "Successful patch requires verified trusted restoration before continuation.")
            except BaseException:
                secondary["restoration"] = sys.exc_info()
            finally:
                try:
                    phase.close_descriptor()
                except BaseException:
                    secondary.setdefault("restoration", sys.exc_info())
            if proof is not None:
                proof["errors"] = {key: error_category(value[1]) for key, value in secondary.items()}
                try:
                    journal.update(qualification_restoration=proof)
                except BaseException:
                    secondary["publication"] = sys.exc_info()
        if primary or secondary:
            try:
                journal.update(qualification_status="unknown", qualification_errors={key: error_category(value[1]) for key, value in secondary.items()})
            except BaseException:
                pass  # Retain original intent/error even when publication is unavailable.
    failure = primary or next(iter(secondary.values()), None)
    if failure:
        raise failure[1].with_traceback(failure[2])
    cleanup(journal)
    rpc = driver._open(journal)
    try:
        driver._persisted(rpc, journal)
        # Re-read exact persisted native items, never accept prior model prose.
        for row in observations:
            items = driver.read_turn_items(rpc, journal.state["thread_id"], row["turn_id"])
            ignored = {"agentMessage", "userMessage", "reasoning", "plan"}
            observed = [{"id": item["id"], "type": item["type"], "sha256": n.digest(item)}
                        for item in items if item["type"] not in ignored]
            if observed != row["native_items"]:
                w.fail("native_tool_persistence_unconfirmed", "Persisted exact-turn tool inventory differs from the observed ordered typed items.")
    finally:
        driver._close(rpc, journal)
    cleanup(journal)
    journal.update(qualification_status="awaiting_independent_acceptance", last_turn_status="completed")
    return observations


def cleanup(journal):
    if not isinstance(journal.state.get("cleanup"), dict) or journal.state["cleanup"].get("empty") is not True:
        journal.update(qualification_status="unknown")
        w.fail("cleanup_unknown", "Native qualification requires actual owned kernel cleanup before continuation.")


def run(config_path, workdir, sprint, parent, authorization_file, parent_context, local_probe_receipt, *, driver_factory=None):
    """Closed CLI entry point: only configured main_external, no arbitrary text."""
    config, profile_id, profile, spec, expected, context, _, guard = n.preflight(config_path, workdir, parent_context,
        needs_tools=True, local_only=True)
    if spec["kind"] != "codex":
        w.fail("unsupported_qualification_driver", "Synthetic qualification currently covers only the selected native Codex driver.")
    if spec.get("connection") != "owned-stdio":
        w.fail("unsupported_qualification_connection", "Native qualification requires owned stdio with kernel cleanup proof.")
    roots = context["_protection_roots"]
    home = config.path_context.anchors["workflow_home"][0]
    auth_record = n.freeze_file(authorization_file)
    n.check_frozen(auth_record, roots)
    document = w.read_json(authorization_file)
    exact(document, {"schema_version", "source", "authorizations", "qualification_reviews"}, "trusted qualification scope")
    exact(document["source"], {"kind", "reference", "text"}, "human source")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1 or document["source"]["kind"] != "human_instruction":
        w.fail("missing_authorization", "Trusted caller must establish exact human qualification authorization provenance.")
    w.bounded_text(document["source"]["reference"], "human source reference", 8192)
    w.bounded_text(document["source"]["text"], "human source evidence", 32768)
    host_record = n.freeze_file(home / "native-host.json")
    n.check_frozen(host_record, roots)
    host = w.read_json(host_record[1])
    exact(host, {"schema", "host"}, "stable native host")
    if type(host["schema"]) is not int or host["schema"] != 1:
        w.fail("invalid_host", "Host setup must establish its stable native identity before qualification.")
    records = document["authorizations"]
    if not isinstance(records, list) or not 1 <= len(records) <= 128:
        w.fail("missing_authorization", "Bounded exact qualification scopes are required.")
    required = {"kind", "operation", "host", "workdir", "sprint_id", "parent_chat_id", "profile", "provider", "binding_sha256",
        "local_probe_sha256", "linkage_sha256", "instruction_sha256"}
    scopes = []
    for row in records:
        if isinstance(row, dict) and row.get("kind") == "top":
            exact(row, {"kind", "assignment_id", "workdir", "role", "profile"}, "separate top scope")
            continue
        exact(row, required, "human qualification record")
        if (row["kind"] == "native-qualification" and row["operation"] == "qualify" and row["host"] == host["host"]
                and row["workdir"] == expected["cwd"] and row["sprint_id"] == sprint and row["parent_chat_id"] == parent
                and row["profile"] == profile_id and row["provider"] == profile["provider"] and row["binding_sha256"] == n.digest(spec["_binding"])):
            scopes.append(row)
    if len(scopes) != 1:
        w.fail("missing_authorization", "Human evidence must cover this exact host/root/sprint/parent/profile/provider and all current pins.")
    scope = scopes[0]
    probe_reference = {"path": str(local_probe_receipt), "sha256": scope["local_probe_sha256"]}
    probe, linkage, created, frozen = prerequisites(config, spec, expected, context, home, workdir, probe_reference, document["qualification_reviews"])
    requests = qualification_requests(linkage["inventory"], created, probe["schema"])
    if scope["linkage_sha256"] != probe["linkage"]["sha256"] or scope["instruction_sha256"] != n.digest({"readiness": READINESS, "requests": requests}):
        w.fail("missing_authorization", "Human evidence does not cover exact native linkage and bundled synthetic instruction bytes.")
    if w.needs_consent(config, profile_id):
        assignment = n.native_top_assignment(Path(expected["cwd"]), sprint, parent, "qualify", "qualify", profile_id)
        w.require_authorization(document, "top", Path(expected["cwd"]), assignment_id=assignment, role="main_external", profile=profile_id)
    frozen += [auth_record, host_record]
    if driver_factory is None:
        from native_codex import CodexDriver
        driver_factory = CodexDriver
    with n.Journal(home / "native-runs", host["host"], Path(expected["cwd"]), sprint, parent) as journal:
        if journal.state.get("thread_id") or journal.has_operations():
            w.fail("qualification_exists", "Qualification has native history; reconcile the original sprint, never allocate again.")
        phase = FixturePhase(created)
        def frozen_guard():
            guard()
            w.protect_path(journal.directory, roots)
            for record in frozen:
                n.check_frozen(record, roots)
            phase.check()
        journal.guard = frozen_guard
        frozen_guard()
        selected = {"profile": profile_id, "binding": profile["chat"], "expected": expected, "runtime_sha256": spec["sha256"], "permission_identity": spec["_binding"]}
        if journal.state.get("selected", selected) != selected:
            w.fail("sprint_identity_changed", "Qualification must retain the original sprint binding.")
        journal.update(selected=selected, qualification_instruction_sha256=scope["instruction_sha256"])
        driver = driver_factory(spec, expected, context, {"checks": {}})
        observations = execute(journal, driver, linkage["inventory"], created, probe, frozen, roots, phase=phase)
        receipt = {"schema": 2 if context.get("schema") == 2 else 1, "kind": "native-qualification-observations", "author": "native-qualification-runner", "binding": spec["_binding"], "host": host["host"],
            "root": probe["root"], "sprint": sprint, "parent": parent, "thread_id": journal.state["thread_id"],
            "initialization_turn_id": journal.state["initialization_turn_id"], "instruction_sha256": scope["instruction_sha256"],
            "local_probe": probe_reference, "linkage": probe["linkage"], "observations": observations, "cleanup": journal.state["cleanup"],
            "status": "awaiting_independent_acceptance", "client_visibility": "pending", "actual_serving_model": "unknown"}
        if context.get("schema") == 2:
            receipt["filesystem_isolation"] = False
            receipt["recipe"] = REAL_RECIPE
            receipt["restoration"] = journal.state["qualification_restoration"]
        path = journal.directory / "qualification-observations.json"
        try:
            w.write_exclusive(path, receipt)
            journal.update(qualification_receipt={"path": str(path), "sha256": w.file_hash(path)})
        except BaseException:
            try:
                journal.update(qualification_status="unknown", qualification_errors={"publication": "failed"})
            except BaseException:
                pass
            raise
        return {"status": receipt["status"], "thread_id": receipt["thread_id"], "receipt": str(path), "sha256": w.file_hash(path)}


def validate_restoration(receipt, journal=None):
    """New evidence is explicit; absent marks never downgrade this sealed bundle."""
    proof = receipt.get("restoration")
    fields = {"recipe", "fixture", "original_sha256", "written_sha256", "restored_sha256", "patch_operation", "patch_ack", "patch_observation", "cleanup", "outcome", "errors"}
    if (receipt.get("recipe") != REAL_RECIPE or not isinstance(proof, dict) or set(proof) != fields
            or proof.get("recipe") != REAL_RECIPE or proof.get("outcome") != "restored" or proof.get("errors") != {}
            or proof.get("original_sha256") != proof.get("restored_sha256")
            or proof.get("original_sha256") == proof.get("written_sha256")
            or proof.get("patch_operation") != "qualify_task_patch_allowed"):
        w.fail("qualification_transition_invalid", "Exact successful real-edit restoration proof is required.")
    for key in ("original_sha256", "written_sha256", "restored_sha256"):
        w.digest_pin(proof[key])
    fixture, owned = proof["fixture"], proof["cleanup"]
    if (not isinstance(fixture, dict) or set(fixture) != {"lexical", "canonical", "device", "inode", "mode"}
            or any(type(fixture[key]) is not int or fixture[key] < 0 for key in ("device", "inode", "mode"))
            or fixture["mode"] > 0o7777 or not isinstance(owned, dict) or set(owned) != {"connection", "empty", "proof"}
            or owned.get("empty") is not True or not isinstance(owned.get("connection"), str)
            or not re.fullmatch(r"[a-f0-9]{32}", owned["connection"])
            or not isinstance(owned.get("proof"), dict) or owned["proof"].get("empty") is not True):
        w.fail("qualification_transition_invalid", "Restoration needs exact fixture identity and current owning kernel cleanup.")
    raw = w.lexical_path(fixture["lexical"], "Restored synthetic fixture")
    info = raw.lstat()
    if (not stat.S_ISREG(info.st_mode) or str(raw.resolve()) != fixture["canonical"]
            or info.st_dev != fixture["device"] or info.st_ino != fixture["inode"] or stat.S_IMODE(info.st_mode) != fixture["mode"]
            or info.st_size > 256):
        w.fail("qualification_transition_invalid", "Restored synthetic path identity/permissions changed.")
    content = fixture_bytes(raw)
    if (not content.endswith(b"\n") or hashlib.sha256(content).hexdigest() != proof["original_sha256"]
            or hashlib.sha256(content[:-1] + b":written\n").hexdigest() != proof["written_sha256"]):
        w.fail("qualification_transition_invalid", "Restored synthetic bytes do not match the distinct original/written hashes.")
    rows = receipt.get("observations")
    if (not isinstance(rows, list) or len(rows) != 2 or proof["patch_observation"] != rows[1]
            or not valid_tool_observation(rows[1], "patch", actual=True) or rows[1]["target"] != fixture["canonical"]
            or not isinstance(proof["patch_ack"], dict) or proof["patch_ack"].get("assignment_turn_id") != rows[1]["turn_id"]):
        w.fail("qualification_transition_invalid", "Restoration must bind the exact original native patch acknowledgement and observation.")
    if journal is not None:
        operation = journal.lookup_operation(proof["patch_operation"])
        if (journal.state.get("qualification_recipe") != REAL_RECIPE or journal.state.get("qualification_restoration") != proof
                or not operation or operation["status"] != "complete" or operation["ack"] != proof["patch_ack"]
                or operation["result"] != proof["patch_observation"]):
            w.fail("qualification_transition_invalid", "Receipt/journal restoration proof and original native operation must agree exactly.")
    return proof


def validate_bootstrap(config, spec, expected, context, journal, qualified):
    """Validate original immutable bootstrap on EVERY actual-rights send."""
    if (qualified.get("binding") != spec["_binding"] or journal.state.get("selected", {}).get("permission_identity") != spec["_binding"]
            or not journal.state.get("thread_id") or journal.state.get("last_turn_status") != "completed" or journal.has_unresolved()):
        w.fail("qualification_transition_invalid", "Changed identity, missing terminal state or unknown operation blocks qualification acceptance.")
    bootstrap = qualified.get("bootstrap")
    exact(bootstrap, {"receipt", "acceptance"}, "accepted same-chat bootstrap")
    frozen, roots = [], context["_protection_roots"]
    receipt = load_reference(config, bootstrap["receipt"], roots, frozen)
    actual = context.get("schema") == 2
    if (receipt.get("schema") != (2 if actual else 1) or (actual and receipt.get("filesystem_isolation") is not False)
            or receipt.get("kind") != "native-qualification-observations" or receipt.get("binding") != spec["_binding"]
            or receipt.get("thread_id") != journal.state["thread_id"] or receipt.get("sprint") != journal.identity["sprint"]
            or receipt.get("parent") != journal.parent or receipt.get("host") != journal.identity["host"]
            or receipt.get("root", {}).get("canonical") != expected["cwd"]
            or receipt.get("initialization_turn_id") != journal.state.get("initialization_turn_id")
            or receipt.get("instruction_sha256") != journal.state.get("qualification_instruction_sha256")
            or receipt.get("status") != "awaiting_independent_acceptance"
            or journal.state.get("qualification_receipt") != bootstrap["receipt"]):
        w.fail("qualification_transition_invalid", "Accepted evidence must describe this exact original native sprint/chat.")
    if actual:
        if qualified.get("recipe") != REAL_RECIPE:
            w.fail("qualification_transition_invalid", "New bootstrap must retain the real-edit recipe identity.")
        validate_restoration(receipt, journal)
        for operation_name in ("qualify_allocate", "qualify_resume"):
            operation = journal.lookup_operation(operation_name)
            observed = (operation or {}).get("result", {}).get("observed", {})
            approval = context["approval"]
            if (not operation or operation["status"] != "complete" or operation["ack"].get("thread_id") != receipt["thread_id"]
                    or observed.get("approvalPolicy") != approval["policy"]
                    or observed.get("requestedApprovalsReviewer") != approval["reviewer"]):
                w.fail("qualification_transition_invalid", "Original actual permission identity acknowledgements are missing.")
    # Retain every original acknowledged terminal qualification operation/result.
    initialize = journal.lookup_operation("qualify_initialize")
    if not initialize or initialize["status"] != "complete" or initialize["ack"].get("initialization_turn_id") != receipt["initialization_turn_id"]:
        w.fail("qualification_transition_invalid", "Original readiness acknowledgement is missing.")
    rows = receipt.get("observations")
    if not isinstance(rows, list) or len(rows) != (2 if actual else 8):
        w.fail("qualification_transition_invalid", "Original native tool observations are incomplete.")
    expected_pairs = [(stage, family, case) for stage in ("init", "task") for family in ("shell", "patch") for case in ("allowed", "denied")]
    if actual:
        expected_pairs = [("task", "shell", "allowed"), ("task", "patch", "allowed")]
    by_operation = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("type") not in ITEM_TYPES.values():
            w.fail("qualification_transition_invalid", "Original qualification tool family is invalid.")
        family = next(key for key, value in ITEM_TYPES.items() if value == row["type"])
        if not valid_tool_observation(row, family, actual=actual):
            w.fail("qualification_transition_invalid", "Original successful native tool inventory is missing or malformed.")
        key = (row.get("stage"), family, row.get("case"))
        if key not in expected_pairs or key in by_operation:
            w.fail("qualification_transition_invalid", "Original qualification recipe identity changed.")
        name = "qualify_" + key[0] + "_" + key[1] + "_" + key[2]
        operation = journal.lookup_operation(name)
        if (not operation or operation["status"] != "complete" or operation["result"] != row
                or operation["ack"].get("assignment_turn_id") != row.get("turn_id")):
            w.fail("qualification_transition_invalid", "Exact original terminal tool acknowledgement/result is missing.")
        by_operation[key] = row
    acceptance(config, bootstrap["acceptance"], bootstrap["receipt"]["sha256"], "native-qualification-runner", spec["_binding"], roots, frozen)
    cleanup(journal)
    if (journal.state.get("accepted_bootstrap", bootstrap) != bootstrap
            or journal.state.get("accepted_qualification_sha256", n.digest(qualified)) != n.digest(qualified)):
        w.fail("qualification_transition_invalid", "Accepted same-chat qualification changed.")
    for record in frozen:
        n.check_frozen(record, roots)
    return bootstrap


def accept_qualification(config, spec, expected, context, journal, qualified):
    """Ordinary send admission; schema2 revalidates even after the first brief."""
    status = journal.state.get("qualification_status")
    if status != "awaiting_independent_acceptance" and not (context.get("schema") == 2 and status == "qualified_awaiting_brief"):
        w.fail("qualification_transition_invalid", "Only the original qualified sprint may send under its accepted bootstrap.")
    bootstrap = validate_bootstrap(config, spec, expected, context, journal, qualified)
    journal.update(qualification_status="qualified_awaiting_brief", task_status="qualified_awaiting_brief",
        accepted_bootstrap=bootstrap, accepted_qualification_sha256=n.digest(qualified))
    return journal.state["thread_id"]
