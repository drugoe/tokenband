"""Apply one exact, cooperating writer's edit to a local Markdown TODO."""

import argparse
from contextlib import contextmanager
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


LOCK_NAME = ".TODO.md.lock"
BOM = b"\xef\xbb\xbf"
REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
HEADING = re.compile(rb"^( {0,3})(#{1,6})[ \t]+\S")
LIST_ITEM = re.compile(rb"^([ \t]*)([-+*]|[0-9]+[.)])[ \t]+\S")


class TransitionError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def fail(status, message):
    raise TransitionError(status, message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def is_reparse(info):
    return bool(getattr(info, "st_file_attributes", 0) & REPARSE_POINT)


def local_root(root):
    if not root.is_absolute() or ".." in root.parts or str(root).startswith("\\\\"):
        fail("unsafe_path", "Use the absolute canonical local project directory.")
    if os.name == "nt":
        tail = str(root)[len(root.drive):]
        if ":" in tail or any(part.endswith((" ", ".")) for part in root.parts[1:]):
            fail("unsafe_path", "Windows path aliases and alternate streams are unsupported.")
        import ctypes

        if ctypes.windll.kernel32.GetDriveTypeW(str(root.anchor)) != 3:
            fail("unsupported", "Windows TODO transitions require a local fixed drive.")
    for directory in (root, *root.parents):
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or is_reparse(info):
            fail("unsafe_path", "Project directory ancestry must be plain and local.")
    if root.resolve(strict=True) != root:
        fail("unsafe_path", "Use the resolved project directory.")
    return root


def plain_file(info):
    if not stat.S_ISREG(info.st_mode) or is_reparse(info) or info.st_nlink != 1:
        fail("unsafe_path", "TODO and guard must be regular, single-link local files.")
    return info


def same_file(path, info):
    return os.path.samestat(plain_file(path.lstat()), info)


def acquire(stream):
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        elif sys.platform.startswith("linux"):
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            fail("unsupported", "No supported local TODO lock on this host.")
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, errno.EDEADLK):
            fail("busy", "Another writer holds the queue guard.")
        fail("io_error", "Cannot acquire the local queue guard.")


@contextmanager
def queue_guard(path):
    try:
        plain_file(path.lstat())
    except FileNotFoundError:
        pass
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags, 0o600), "r+b", buffering=0) as stream:
        info = plain_file(os.fstat(stream.fileno()))
        if not same_file(path, info):
            fail("unsafe_path", "The guard path changed while opening it.")
        acquire(stream)
        if not same_file(path, info):
            fail("unsafe_path", "The stable queue guard was replaced.")
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b"0")
        yield info


def read_todo(path, *, for_write=False):
    info = plain_file(path.lstat())
    mode = os.O_RDWR if for_write else os.O_RDONLY
    flags = mode | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        if not os.path.samestat(info, plain_file(os.fstat(stream.fileno()))):
            fail("unsafe_path", "The TODO path changed while opening it.")
        data = stream.read()
    return data, info


def fragment(value, name):
    if not isinstance(value, str) or "\0" in value:
        fail("invalid_edit", f"{name} must be UTF-8 text.")
    try:
        data = value.encode("utf-8")
    except UnicodeError:
        fail("invalid_edit", f"{name} must be UTF-8 text.")
    if b"\r" in data.replace(b"\r\n", b""):
        fail("invalid_edit", f"{name} must use LF or CRLF.")
    return data


def row_shape(line):
    heading = HEADING.match(line)
    if heading:
        return "heading", len(heading[1]), heading[2]
    item = LIST_ITEM.match(line)
    if item:
        return "list", len(item[1].expandtabs(4)), item[2]
    return None


def entry_end(lines, start, shape):
    kind, depth, _ = shape
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        if kind == "heading":
            if HEADING.match(line):
                return index
        else:
            expanded = line.expandtabs(4)
            if len(expanded) - len(expanded.lstrip(b" ")) <= depth:
                return index
    return len(lines)


def end_marker(line):
    if line.endswith(b"\r\n"):
        return b"\r\n"
    return b"\n" if line.endswith(b"\n") else b""


def verify_endings(old, new, reference):
    if not new:
        return
    old_marks = [end_marker(line) for line in old]
    new_marks = [end_marker(line) for line in new]
    if old_marks == new_marks:
        return
    styles = set(old_marks) - {b""}
    if not styles:
        styles = {end_marker(reference)} - {b""}
    if len(styles) != 1 or new_marks[-1] != old_marks[-1] or set(new_marks) - {b""} != styles:
        fail("invalid_edit", "Replacement must preserve line-ending style and the passage boundary.")


def modify(snapshot, edit):
    try:
        snapshot.decode("utf-8")
    except UnicodeError:
        fail("invalid_edit", "TODO must be UTF-8.")
    if not isinstance(edit, dict) or set(edit) != {"task_row", "task_key", "before", "after"}:
        fail("invalid_edit", "Supply task_row, task_key, before and after.")
    row, key, before, after = (fragment(edit[name], name) for name in ("task_row", "task_key", "before", "after"))
    shape = row_shape(row)
    if not shape or not key or key not in row or b"\n" in row or b"\n" in key or not before:
        fail("invalid_edit", "Supply an exact Markdown task row, its stable key and a nonempty old passage.")

    bom = BOM if snapshot.startswith(BOM) else b""
    lines = snapshot[len(bom):].splitlines(keepends=True)
    entries = [index for index, line in enumerate(lines) if line.rstrip(b"\r\n") == row]
    if len(entries) != 1:
        fail("invalid_edit", "The exact task row must occur once.")
    first = entries[0]
    last = entry_end(lines, first, shape)
    old, new = before.splitlines(keepends=True), after.splitlines(keepends=True)
    matches = [i for i in range(first, last - len(old) + 1) if lines[i:i + len(old)] == old]
    if len(matches) != 1:
        fail("invalid_edit", "The exact whole-line passage must occur once within the task entry.")
    start = matches[0]
    if start == first and (not new or row_shape(new[0]) != shape or key not in new[0]):
        fail("invalid_edit", "The replacement must retain the task row shape and stable key.")
    verify_endings(old, new, lines[first])
    updated = lines[:start] + new + lines[start + len(old):]
    if entry_end(updated, first, shape) != last + len(new) - len(old):
        fail("invalid_edit", "Replacement would change the task-entry boundary.")
    return bom + b"".join(updated)


def fsync_parent(path):
    if os.name != "nt":
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def access_identity(path, info):
    if os.name != "nt":
        return info.st_uid, info.st_gid

    import ctypes
    from ctypes import wintypes

    get_security = ctypes.WinDLL("advapi32", use_last_error=True).GetFileSecurityW
    get_security.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    get_security.restype = wintypes.BOOL
    required = wintypes.DWORD()
    owner_group_dacl = 0x07
    get_security(str(path), owner_group_dacl, None, 0, ctypes.byref(required))
    if ctypes.get_last_error() != 122 or not required.value:
        raise ctypes.WinError(ctypes.get_last_error())
    descriptor = ctypes.create_string_buffer(required.value)
    if not get_security(str(path), owner_group_dacl, descriptor, required.value, ctypes.byref(required)):
        raise ctypes.WinError(ctypes.get_last_error())
    return descriptor.raw


def verify_writable_snapshot(path, snapshot, info, security):
    current, current_info = read_todo(path, for_write=True)
    if (current != snapshot or not os.path.samestat(info, current_info)
            or info.st_mode != current_info.st_mode or access_identity(path, current_info) != security):
        fail("conflict", "TODO changed before commit. Reconcile the current record first.")


def publish(path, lock, lock_info, snapshot, info, data):
    security = access_identity(path, info)
    verify_writable_snapshot(path, snapshot, info, security)
    fd, filename = tempfile.mkstemp(prefix=".TODO.md.", suffix=".tmp", dir=path.parent)
    temporary = Path(filename)
    published = False
    try:
        with os.fdopen(fd, "wb") as stream:
            if access_identity(temporary, os.fstat(stream.fileno())) != security:
                fail("unsupported", "Replacement cannot preserve the queue's owner and access metadata.")
            if stream.write(data) != len(data):
                raise OSError("Short temporary write.")
            stream.flush()
            os.chmod(temporary, stat.S_IMODE(info.st_mode))
            os.fsync(stream.fileno())
        local_root(path.parent)
        if not same_file(lock, lock_info):
            fail("unsafe_path", "The queue guard was replaced before commit.")
        verify_writable_snapshot(path, snapshot, info, security)
        try:
            os.replace(temporary, path)
            published = True
            fsync_parent(path)
            actual, actual_info = read_todo(path)
            if (actual != data or stat.S_IMODE(actual_info.st_mode) != stat.S_IMODE(info.st_mode)
                    or access_identity(path, actual_info) != security):
                fail("effect_unconfirmed", "Replacement readback differed. Reconcile the exact local TODO.")
        except (OSError, TransitionError):
            fail("effect_unconfirmed", "Replacement outcome is unconfirmed. Read the exact TODO before any further write.")
    finally:
        if not published:
            temporary.unlink(missing_ok=True)


def transition(root, expected, edit):
    if not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
        fail("invalid_edit", "Supply the SHA-256 of the entire exact TODO.")
    root = local_root(root)
    path = root / "TODO.md"
    plain_file(path.lstat())
    lock = root / LOCK_NAME
    with queue_guard(lock) as lock_info:
        snapshot, info = read_todo(path)
        if digest(snapshot) != expected.lower():
            fail("conflict", "TODO no longer matches the expected whole-file SHA-256.")
        data = modify(snapshot, edit)
        if data == snapshot:
            return {"status": "no_change", "sha256": digest(snapshot)}
        publish(path, lock, lock_info, snapshot, info, data)
    return {"status": "updated", "sha256": digest(data)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args()
    try:
        edit = json.load(sys.stdin.buffer)
    except (ValueError, UnicodeError):
        result = {"status": "invalid_edit", "detail": "Read a UTF-8 edit JSON object from stdin."}
    else:
        try:
            result = transition(args.project_root, args.expect_sha256, edit)
        except TransitionError as exc:
            result = {"status": exc.status, "detail": str(exc)}
        except OSError:
            result = {"status": "io_error", "detail": "Local operation failed. Verify exact state before another attempt."}
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["status"] in ("updated", "no_change") else 1


if __name__ == "__main__":
    raise SystemExit(main())
