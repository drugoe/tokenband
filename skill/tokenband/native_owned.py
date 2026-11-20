"""Isolated native process owner. Used only through a protected launch specification.

No imports from workstation integrations. Stdout belongs to the native protocol.
Kernel proof is committed to a separate protected, nonce-bound receipt.
"""
from __future__ import annotations
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


class OwnershipError(RuntimeError):
    pass


class LinuxOwner:
    def __init__(self):
        if not all(hasattr(os, x) for x in ("waitid", "pidfd_open")) or not hasattr(signal, "pidfd_send_signal"):
            raise OwnershipError("Linux pidfd/waitid unavailable")
        self.pid = os.getpid()
        libc = ctypes.CDLL(None, use_errno=True)
        enabled = ctypes.c_int()
        if libc.prctl(36, 1, 0, 0, 0) or libc.prctl(37, ctypes.byref(enabled), 0, 0, 0) or enabled.value != 1:
            raise OwnershipError("Subreaper not verified")

    def empty(self):
        while True:
            try:
                if os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | 0x40000000) is None:
                    return False
            except ChildProcessError:
                return True

    def stop(self, process):
        # /proc identifies targets only; only ECHILD proves release.
        for sig in (signal.SIGTERM, signal.SIGKILL):
            until = time.monotonic() + 3
            while True:
                process.poll()
                if self.empty():
                    return {"kind": "linux_subreaper_waitid_wall", "empty": True}
                children = set()
                for path in Path(f"/proc/{self.pid}/task").glob("*/children"):
                    children.update(int(value) for value in path.read_text().split())
                for pid in children:
                    try:
                        fd = os.pidfd_open(pid)
                    except ProcessLookupError:
                        continue
                    try:
                        stat = Path(f"/proc/{pid}/stat").read_text()
                        if int(stat[stat.rfind(")") + 2:].split()[1]) != self.pid:
                            raise OwnershipError("Ownership changed")
                        signal.pidfd_send_signal(fd, sig)
                    except (ProcessLookupError, FileNotFoundError):
                        pass
                    finally:
                        os.close(fd)
                if time.monotonic() >= until:
                    break
                time.sleep(.02)
        raise OwnershipError("Descendant cleanup unconfirmed")


class WindowsOwner:
    def __init__(self):
        from ctypes import wintypes as w
        self.w, self.pid = w, os.getpid()
        self.k = k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateJobObjectW.argtypes, k.CreateJobObjectW.restype = [ctypes.c_void_p, w.LPCWSTR], w.HANDLE
        k.GetCurrentProcess.restype = w.HANDLE
        k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        k.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
        k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        k.IsProcessInJob.argtypes = [w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)]
        k.OpenProcess.argtypes, k.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
        k.TerminateProcess.argtypes, k.CloseHandle.argtypes = [w.HANDLE, w.UINT], [w.HANDLE]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ("r", "w", "o", "rb", "wb", "ob")]
        class Basic(ctypes.Structure):
            _fields_ = [("process", ctypes.c_longlong), ("job", ctypes.c_longlong),
                        ("flags", w.DWORD), ("minimum", ctypes.c_size_t), ("maximum", ctypes.c_size_t),
                        ("active", w.DWORD), ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO)] + [(n, ctypes.c_size_t) for n in ("pm", "jm", "pp", "pj")]
        self.handle = k.CreateJobObjectW(None, None)
        limits, checked = Extended(), Extended()
        limits.basic.flags = 0x2000  # kill-on-close, no breakaway
        if (not self.handle or not k.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
                or not k.QueryInformationJobObject(self.handle, 9, ctypes.byref(checked), ctypes.sizeof(checked), None)
                or checked.basic.flags != 0x2000
                or not k.AssignProcessToJobObject(self.handle, k.GetCurrentProcess())):
            raise OwnershipError("Private Job could not be enforced")
        member = w.BOOL()
        if not k.IsProcessInJob(k.GetCurrentProcess(), self.handle, ctypes.byref(member)) or not member.value:
            raise OwnershipError("Job membership unavailable")
        # Do not close the handle early: this owner itself is a member.

    def members(self):
        for capacity in (64, 256, 1024, 4096, 16384):
            class Pids(ctypes.Structure):
                _fields_ = [("assigned", self.w.DWORD), ("listed", self.w.DWORD), ("pids", ctypes.c_size_t * capacity)]
            data = Pids()
            if self.k.QueryInformationJobObject(self.handle, 3, ctypes.byref(data), ctypes.sizeof(data), None):
                if data.assigned != data.listed or data.listed > capacity:
                    continue
                found = set(data.pids[:data.listed])
                if self.pid not in found:
                    raise OwnershipError("Owner absent from Job")
                return found
            if ctypes.get_last_error() != 234:
                break
        raise OwnershipError("Complete Job membership unavailable")

    def stop(self, process):
        until = time.monotonic() + 6
        while self.members() != {self.pid}:
            for pid in self.members() - {self.pid}:
                handle = self.k.OpenProcess(0x0001 | 0x1000, False, pid)
                if not handle:
                    if ctypes.get_last_error() == 87:
                        continue
                    raise OwnershipError("Cannot open Job member")
                try:
                    member = self.w.BOOL()
                    if not self.k.IsProcessInJob(handle, self.handle, ctypes.byref(member)) or not member.value:
                        raise OwnershipError("Handle outside owned Job")
                    if not self.k.TerminateProcess(handle, 1) and ctypes.get_last_error() != 5:
                        raise OwnershipError("Owned termination failed")
                finally:
                    self.k.CloseHandle(handle)
            if time.monotonic() >= until:
                raise OwnershipError("Job cleanup unconfirmed")
            time.sleep(.02)
        process.poll()
        return {"kind": "windows_job_only_launcher", "empty": True}


def main():
    spec_path = Path(sys.argv[1])
    raw = spec_path.read_bytes()
    if len(raw) > 1024 * 1024:
        return 70
    spec = json.loads(raw)
    if set(spec) != {"argv", "cwd", "receipt", "nonce"}:
        return 70
    owner = WindowsOwner() if os.name == "nt" else LinuxOwner()
    process = None
    try:
        if os.name != "nt":
            def stopped(signum, frame):
                raise InterruptedError()
            signal.signal(signal.SIGTERM, stopped)
        process = subprocess.Popen(spec["argv"], cwd=spec["cwd"], stdin=sys.stdin.buffer,
                                   stdout=sys.stdout.buffer, stderr=subprocess.DEVNULL,
                                   shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        process.wait()
    except (OSError, InterruptedError):
        pass
    finally:
        if process is not None:
            proof = owner.stop(process)
            receipt = {"nonce": spec["nonce"], "owner_pid": os.getpid(), "proof": proof}
            target = Path(spec["receipt"])
            # Parent reserves this exact location before launch. Never follow an alias.
            if target.is_symlink() or target.exists():
                raise OwnershipError("Receipt already exists")
            with target.open("x", encoding="utf-8") as stream:
                json.dump(receipt, stream)
                stream.flush()
                os.fsync(stream.fileno())
    return 0 if process is not None else 70


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # No argv/environment/secret-bearing native exception output.
        raise SystemExit(70)
