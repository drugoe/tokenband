"""Validate and optionally publish a committed TokenBand release."""

import argparse
import io
import lzma
import re
import stat
import subprocess
import sys
import uuid
import zipfile
import zlib


MAIN = "refs/heads/main"
ARCHIVE_NAME = re.compile(r"tokenband-.+-skill\.zip")
VERSION_NUMBER = re.compile(
    r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){2}"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
METADATA_FIELD = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]+(.*))?")
REGULAR_MODES = (b"100644", b"100755")


class ReleaseError(Exception):
    pass


def git(*arguments, allowed=(0,), options=()):
    result = subprocess.run(
        ["git", "--no-replace-objects", *options, *arguments], capture_output=True
    )
    if result.returncode not in allowed:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReleaseError(f"git {arguments[0]} failed (exit {result.returncode}): {detail}")
    return result


def revision(ref):
    return git("rev-parse", "--verify", f"{ref}^{{commit}}").stdout.decode().strip()


def fetch_main():
    fetch_urls = git("remote", "get-url", "--all", "origin").stdout.splitlines()
    push_urls = git("remote", "get-url", "--push", "--all", "origin").stdout.splitlines()
    if len(fetch_urls) != 1 or fetch_urls != push_urls:
        raise ReleaseError("origin must use one URL for both fetching and publishing")

    # A private ref binds the result to this invocation even during another fetch.
    ref = f"refs/tokenband-release/{uuid.uuid4().hex}"
    try:
        git(
            "fetch", "--no-tags", "--no-recurse-submodules", "--no-write-fetch-head",
            "--refmap=", "origin", f"{MAIN}:{ref}",
        )
        return revision(ref)
    finally:
        git("update-ref", "-d", ref)


def tree(commit, *paths):
    flags = ("-r",) if paths else ()
    entries = git("ls-tree", "-z", "--full-tree", *flags, commit, "--", *paths).stdout
    result = {}
    for entry in entries.split(b"\0"):
        if entry:
            descriptor, name = entry.split(b"\t", 1)
            mode, _, object_id = descriptor.split()
            result[name.decode("utf-8", errors="surrogateescape")] = (mode, object_id)
    return result


def regular_blob(entries, name):
    entry = entries.get(name)
    if entry is None or entry[0] not in REGULAR_MODES:
        raise ReleaseError(f"Expected a committed regular file at {name!r}")
    return entry[1]


def blob(object_id):
    return git("cat-file", "blob", object_id.decode("ascii")).stdout


def repository_version(contents):
    fields = [line.partition("=") for line in contents.decode("utf-8").splitlines()]
    versions = [value.strip() for key, _, value in fields if key.strip() == "version"]
    if len(versions) != 1 or not VERSION_NUMBER.fullmatch(versions[0]):
        raise ReleaseError("VERSION must contain exactly one valid version= entry")
    return versions[0]


def skill_version(contents):
    # The skill uses a front matter mapping with a two-space metadata mapping.
    lines = contents.decode("utf-8").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise ReleaseError("SKILL.md must contain a front matter block")
    main_fields = {}
    metadata = {}
    section = None
    for line in lines[1:lines.index("---", 1)]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            fields, field = main_fields, line
        elif section == "metadata":
            fields, field = metadata, line.removeprefix("  ")
        else:
            continue
        match = METADATA_FIELD.fullmatch(field.rstrip())
        if match is None or match[1] in fields:
            raise ReleaseError("SKILL.md has unsupported or duplicate front matter fields")
        fields[match[1]] = match[2]
        if fields is main_fields:
            section = match[1]
    value = metadata.get("version") or ""
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        value = value[1:-1]
    if main_fields.get("metadata") is not None or not VERSION_NUMBER.fullmatch(value):
        raise ReleaseError("SKILL.md must contain exactly one valid metadata.version")
    return value


def zip_payload(contents, archive_name):
    files = {}
    directories = set()
    spellings = {}
    parent_paths = set()
    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as archive:
            for member in archive.infolist():
                raw_name = member.orig_filename
                directory = raw_name.endswith("/")
                path = raw_name.removesuffix("/")
                parts = path.split("/")
                if (
                    parts[0] != "tokenband"
                    or (len(parts) == 1 and not directory)
                    or any(
                        not part or part.endswith((" ", "."))
                        or re.search(r'[\x00-\x1f\\:]', part)
                        for part in parts
                    )
                ):
                    raise ReleaseError(f"Invalid ZIP member name {raw_name!r}")
                if path in files or path in directories:
                    raise ReleaseError(f"Duplicate ZIP member {raw_name!r}")
                for length in range(1, len(parts) + 1):
                    prefix = "/".join(parts[:length])
                    if spellings.setdefault(prefix.casefold(), prefix) != prefix:
                        raise ReleaseError(f"Ambiguous ZIP member {raw_name!r}")
                    if length < len(parts):
                        parent_paths.add(prefix)
                expected_type = stat.S_IFDIR if directory else stat.S_IFREG
                if (
                    member.create_system == 3
                    and stat.S_IFMT(member.external_attr >> 16) not in (0, expected_type)
                ):
                    raise ReleaseError(f"Unsupported ZIP member type {raw_name!r}")
                data = archive.read(member)
                if directory:
                    if data:
                        raise ReleaseError(f"ZIP directory contains data {raw_name!r}")
                    directories.add(path)
                else:
                    files[path] = data
    except (
        EOFError, RuntimeError, ValueError, OSError, zipfile.BadZipFile,
        lzma.LZMAError, zlib.error,
    ) as error:
        raise ReleaseError(f"Invalid ZIP {archive_name!r}: {error}") from error
    ambiguous = files.keys() & parent_paths
    if ambiguous:
        raise ReleaseError(f"ZIP path is both a file and a directory: {min(ambiguous)!r}")
    empty = directories - parent_paths
    if empty:
        raise ReleaseError(f"Unexpected empty ZIP directory: {min(empty)!r}")
    return files


def validate(base, head):
    if git("merge-base", "--is-ancestor", base, head, allowed=(0, 1)).returncode:
        raise ReleaseError(f"HEAD {head} is not a fast-forward of origin/main {base}")

    base_root = tree(base)
    head_root = tree(head)
    for name in base_root:
        if ARCHIVE_NAME.fullmatch(name):
            published = regular_blob(base_root, name)
            proposed = head_root.get(name)
            if proposed is None or proposed[0] not in REGULAR_MODES or proposed[1] != published:
                raise ReleaseError(f"Published archive {name!r} must remain byte-for-byte unchanged")

    version = repository_version(blob(regular_blob(head_root, "VERSION")))
    archive_name = f"tokenband-{version}-skill.zip"
    archive_id = regular_blob(head_root, archive_name)
    for name in sorted(head_root.keys() - base_root.keys()):
        if name != archive_name and ARCHIVE_NAME.fullmatch(name):
            raise ReleaseError(
                f"Unexpected new release archive {name!r}; VERSION selects {archive_name!r}"
            )

    source_tree = tree(head, "skill/tokenband")
    skill_path = "skill/tokenband/SKILL.md"
    skill = blob(regular_blob(source_tree, skill_path))
    if skill_version(skill) != version:
        raise ReleaseError(f"SKILL.md metadata.version must match VERSION ({version})")
    source = {
        name.removeprefix("skill/"): skill if name == skill_path
        else blob(regular_blob(source_tree, name))
        for name in source_tree
    }
    packaged = zip_payload(blob(archive_id), archive_name)
    for name in sorted(source.keys() | packaged.keys()):
        if source.get(name) != packaged.get(name):
            raise ReleaseError(f"{archive_name} differs from skill/tokenband/ at {name!r}")
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "publish"))
    args = parser.parse_args()
    try:
        head = revision("HEAD")
        base = fetch_main()
        version = validate(base, head)
        if args.action == "publish":
            # Validation proved ancestry. Require the same base for the ref update.
            git(
                "push", "--no-force", "--no-follow-tags",
                f"--force-with-lease={MAIN}:{base}",
                "--recurse-submodules=no", "origin", f"{head}:{MAIN}",
                options=("-c", "remote.origin.mirror=false"),
            )
            print(f"Published TokenBand {version} at {head} to origin/main")
        else:
            print(f"Validated TokenBand {version} at {head} against origin/main {base}")
    except (ReleaseError, OSError, UnicodeError) as error:
        print(f"Release refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
