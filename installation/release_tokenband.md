# Releasing TokenBand

Use Git on PATH and Python 3.9 or later. Run from a Git checkout of the TokenBand publication repository with a single `origin` URL shared by fetch and push. Commit the candidate before running either command.

```sh
python installation/release_tokenband.py check
python installation/release_tokenband.py publish
```

`check` fetches `origin/main` and validates the committed `HEAD`. `publish` runs the same checks against a fresh fetch and verifies that the candidate descends from the fetched commit. It pushes the exact validated SHA with a lease requiring `origin/main` to still point to that fetched commit for the update. A concurrent advance rejects the update even when it would still be a fast-forward. A rejected validation or push exits with status 1.

Keep every previously published root `tokenband-<version>-skill.zip` byte-for-byte. Add a root release ZIP only for the version selected by `VERSION`. When changing files under `skill/tokenband/`, update `VERSION` and the skill's `metadata.version`, and commit a new versioned ZIP whose `tokenband/` files match the committed source. Documentation outside the skill can be released at the same version with the existing ZIPs.
