import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile


TASK = Path(__file__).resolve().parents[1]
CLI = TASK / "installation" / "release_tokenband.py"
OLD_ZIP = "tokenband-0.6.13-skill.zip"
CURRENT_ZIP = "tokenband-0.6.14-skill.zip"
NEW_ZIP = "tokenband-0.6.15-skill.zip"


def payload(version, worker=b"original\n"):
    return {
        "tokenband/SKILL.md": (
            f'---\nname: tokenband\nmetadata:\n  version: "{version}"\n---\n'
        ).encode(),
        "tokenband/worker.py": worker,
    }


def zip_bytes(files, timestamp=(2026, 11, 25, 0, 0, 0)):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive, warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        members = files.items() if isinstance(files, dict) else files
        for name, contents in members:
            archive.writestr(zipfile.ZipInfo(name, timestamp), contents)
    return output.getvalue()


class ReleaseCommandTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="release-test-", dir=TASK)
        self.addCleanup(temp.cleanup)
        self.workspace = Path(temp.name)
        self.remote = self.workspace / "origin.git"
        self.checkout = self.workspace / "checkout"
        self.checkout.mkdir()
        self.env = {
            key: value for key, value in os.environ.items() if not key.startswith("GIT_")
        }
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "--bare", "--initial-branch=main", str(self.remote))
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "TokenBand Release Test")
        self.git("config", "user.email", "release@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git("remote", "add", "origin", str(self.remote))
        self.old = zip_bytes(payload("0.6.13"))
        self.current = zip_bytes(payload("0.6.14"))
        self.write(OLD_ZIP, self.old)
        self.write(CURRENT_ZIP, self.current)
        self.write_source("0.6.14")
        self.base = self.commit()
        self.git("push", "origin", "main")

    def git(self, *arguments, cwd=None):
        result = subprocess.run(
            ["git", *arguments], cwd=cwd or self.checkout, env=self.env,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        return result.stdout

    def release(self, *arguments):
        return subprocess.run(
            [sys.executable, "-I", "-X", "utf8", str(CLI), *arguments],
            cwd=self.checkout, env=self.env, capture_output=True, encoding="utf-8",
        )

    def write(self, path, contents):
        target = self.checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)

    def write_source(self, version, worker=b"original\n"):
        self.write("VERSION", f"version={version}\nmaturity=experimental\n".encode())
        for name, contents in payload(version, worker).items():
            self.write(f"skill/{name}", contents)

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-m", "Release test fixture")
        return self.git("rev-parse", "HEAD").decode().strip()

    def remote_git(self, *arguments):
        return self.git("--git-dir", str(self.remote), *arguments)

    def assert_remote(self, expected):
        self.assertEqual(
            self.remote_git("rev-parse", "refs/heads/main").decode().strip(),
            expected,
        )
        for path, contents in ((OLD_ZIP, self.old), (CURRENT_ZIP, self.current)):
            self.assertEqual(
                self.remote_git("cat-file", "blob", f"refs/heads/main:{path}"),
                contents,
            )

    def assert_refused(self, diagnostic, expected=None):
        result = self.release("publish")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(diagnostic, result.stderr)
        self.assert_remote(expected or self.base)

    def test_same_version_source_change_with_untouched_archive_is_refused(self):
        self.write_source("0.6.14", b"changed\n")
        self.commit()
        self.assert_refused("tokenband/worker.py")

    def test_repacking_published_current_archive_with_same_payload_is_refused(self):
        self.write(CURRENT_ZIP, zip_bytes(payload("0.6.14"), (2026, 11, 26, 0, 0, 0)))
        self.commit()
        self.assert_refused(CURRENT_ZIP)

    def test_replacing_published_current_archive_contents_is_refused(self):
        self.write_source("0.6.14", b"changed\n")
        self.write(CURRENT_ZIP, zip_bytes(payload("0.6.14", b"changed\n")))
        self.commit()
        self.assert_refused(CURRENT_ZIP)

    def test_deleting_an_older_archive_is_refused_even_with_a_new_version(self):
        (self.checkout / OLD_ZIP).unlink()
        self.write_source("0.6.15")
        self.write(NEW_ZIP, zip_bytes(payload("0.6.15")))
        self.commit()
        self.assert_refused(OLD_ZIP)

    def test_mutating_an_older_archive_is_refused(self):
        self.write(OLD_ZIP, zip_bytes(payload("0.6.13", b"changed\n")))
        self.commit()
        self.assert_refused(OLD_ZIP)

    def test_docs_only_check_and_publish_ignore_dirty_worktree(self):
        self.write("docs/README.md", b"docs change\n")
        head = self.commit()
        self.write("skill/tokenband/worker.py", b"not committed\n")
        result = self.release("check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_remote(self.base)

        result = self.release("publish")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_remote(head)
        self.assertEqual(
            self.remote_git("cat-file", "blob", "refs/heads/main:docs/README.md"),
            b"docs change\n",
        )
        self.assertEqual(
            (self.checkout / "skill/tokenband/worker.py").read_bytes(),
            b"not committed\n",
        )

    def test_same_version_cannot_publish_an_extra_release_archive(self):
        self.write("docs/README.md", b"docs change\n")
        self.write(NEW_ZIP, zip_bytes(payload("0.6.14", b"changed payload\n")))
        self.commit()

        result = self.release("publish")
        with self.subTest("archive refusal"):
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(NEW_ZIP, result.stderr)
        with self.subTest("published ref and archives"):
            self.assert_remote(self.base)
        with self.subTest("extra archive remains absent"):
            self.assertEqual(
                self.remote_git("ls-tree", "refs/heads/main", "--", NEW_ZIP), b""
            )

    def test_new_version_with_matching_archive_can_publish(self):
        files = payload("0.6.15", b"new version\n")
        self.write_source("0.6.15", b"new version\n")
        archive = zip_bytes({"tokenband/": b"", **files})
        self.write(NEW_ZIP, archive)
        head = self.commit()

        result = self.release("publish")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_remote(head)
        self.assertEqual(
            self.remote_git("cat-file", "blob", f"refs/heads/main:{NEW_ZIP}"), archive
        )

    def test_malformed_or_mismatching_new_archive_is_refused(self):
        files = payload("0.6.15")
        self.write_source("0.6.15")
        cases = {
            "not a ZIP": (b"not a ZIP", NEW_ZIP),
            "duplicate": (
                zip_bytes([*files.items(), ("tokenband/worker.py", b"original\n")]),
                "tokenband/worker.py",
            ),
            "dot path": (
                zip_bytes({**files, "tokenband/../worker.py": b"original\n"}),
                "tokenband/../worker.py",
            ),
            "case collision": (
                zip_bytes({**files, "tokenband/WORKER.py": b"original\n"}),
                "tokenband/WORKER.py",
            ),
            "extra file": (
                zip_bytes({**files, "tokenband/extra.py": b"extra\n"}),
                "tokenband/extra.py",
            ),
            "missing file": (
                zip_bytes({"tokenband/SKILL.md": files["tokenband/SKILL.md"]}),
                "tokenband/worker.py",
            ),
        }
        for name, (archive, diagnostic) in cases.items():
            with self.subTest(name=name):
                self.write(NEW_ZIP, archive)
                self.commit()
                self.assert_refused(diagnostic)

    def test_root_version_requires_the_correspondingly_named_archive(self):
        self.write_source("0.6.15")
        self.write("tokenband-0.6.16-skill.zip", zip_bytes(payload("0.6.15")))
        self.commit()
        self.assert_refused(NEW_ZIP)

    def test_bundled_skill_version_must_match_root_version(self):
        self.write_source("0.6.14")
        self.write("VERSION", b"version=0.6.15\n")
        self.write(NEW_ZIP, zip_bytes(payload("0.6.14")))
        self.commit()
        self.assert_refused("SKILL.md")

    def test_ambiguous_root_version_is_refused(self):
        self.write("VERSION", b"version=0.6.14\nversion=0.6.14\n")
        self.commit()
        self.assert_refused("VERSION")

    def test_fresh_remote_tip_rejects_divergent_candidate(self):
        other = self.workspace / "other"
        self.git("clone", str(self.remote), str(other))
        self.git("config", "user.name", "Concurrent Publisher", cwd=other)
        self.git("config", "user.email", "concurrent@example.invalid", cwd=other)
        self.git("config", "core.autocrlf", "false", cwd=other)
        (other / "README.md").write_bytes(b"new upstream\n")
        self.git("add", "README.md", cwd=other)
        self.git("commit", "-m", "Advance remote", cwd=other)
        advanced = self.git("rev-parse", "HEAD", cwd=other).decode().strip()
        self.git("push", "origin", "main", cwd=other)
        self.write("README.md", b"divergent local\n")
        self.commit()

        self.assert_refused("fast-forward", expected=advanced)

    def test_publish_uses_the_validated_head_when_local_main_moves_during_fetch(self):
        self.write("README.md", b"validated candidate\n")
        candidate = self.commit()
        self.write_source("0.6.14", b"unvalidated change\n")
        changed = self.commit()
        self.git("reset", "--hard", candidate)
        upload_pack = (
            "#!/bin/sh\n"
            f"git update-ref refs/heads/main {changed} {candidate} || exit $?\n"
            'exec git upload-pack "$@"\n'
        )
        self.write(".git/hooks/release-test-upload-pack", upload_pack.encode())
        self.git("config", "remote.origin.uploadpack", "sh .git/hooks/release-test-upload-pack")

        result = self.release("publish")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_remote(candidate)
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), changed)

    def test_publish_updates_only_main_even_if_git_is_configured_for_mirroring(self):
        self.write("README.md", b"validated candidate\n")
        candidate = self.commit()
        self.git("config", "remote.origin.mirror", "true")
        self.git("config", "push.followTags", "true")
        self.git("branch", "other-fixture")
        self.git("tag", "-a", "-m", "Tag fixture", "fixture")

        result = self.release("publish")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_remote(candidate)
        self.assertEqual(
            self.remote_git("for-each-ref", "--format=%(refname)"),
            b"refs/heads/main\n",
        )

    def test_concurrent_remote_advance_during_push_is_not_overwritten(self):
        self.write("README.md", b"new upstream\n")
        advanced = self.commit()
        self.git("push", "origin", f"{advanced}:refs/heads/advance")
        self.git("reset", "--hard", self.base)
        self.write("README.md", b"divergent local\n")
        self.commit()
        hook = (
            "#!/bin/sh\n"
            f'git --git-dir="$2" update-ref refs/heads/main {advanced} {self.base}\n'
        )
        self.write(".git/hooks/pre-push", hook.encode())
        (self.checkout / ".git/hooks/pre-push").chmod(0o755)

        self.assert_refused("push", expected=advanced)

    def test_concurrent_fast_forward_publication_keeps_newly_published_archive(self):
        published_files = payload("0.6.15", b"first published payload\n")
        published_zip = zip_bytes(published_files)
        self.write_source("0.6.15", b"first published payload\n")
        self.write(NEW_ZIP, published_zip)
        published = self.commit()
        self.git("push", "origin", f"{published}:refs/heads/advance")

        self.write_source("0.6.15", b"replacement payload\n")
        self.write(NEW_ZIP, zip_bytes(payload("0.6.15", b"replacement payload\n")))
        self.commit()
        receive_pack = (
            "#!/bin/sh\n"
            f'git --git-dir="$1" update-ref refs/heads/main {published} {self.base} || exit $?\n'
            'exec git receive-pack "$@"\n'
        )
        self.write(".git/hooks/release-test-receive-pack", receive_pack.encode())
        self.git("config", "remote.origin.receivepack", "sh .git/hooks/release-test-receive-pack")

        result = self.release("publish")
        with self.subTest("remote ref"):
            self.assert_remote(published)
        with self.subTest("published ZIP bytes"):
            self.assertEqual(
                self.remote_git("cat-file", "blob", f"refs/heads/main:{NEW_ZIP}"),
                published_zip,
            )
        with self.subTest("lease refusal"):
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("stale info", result.stderr)


if __name__ == "__main__":
    unittest.main()
