← [Back to README](../README.md)

# Quick start

## 1. Download the package

Download the public installation archive:

- [tokenband-0.6.13-skill.zip](https://github.com/drugoe/tokenband/raw/refs/heads/main/tokenband-0.6.13-skill.zip)
- SHA-256: `f3c08962d805484f767b89cf4260c96d4a89b1b8afc0f809522d35652180f36a`

The ZIP contains the plain skill package: `SKILL.md`, reference documents, templates and an optional Python worker. It is an instruction set, not a finished configured environment.

## 2. Place the skill for your host

TokenBand is host-agnostic in its core rules, but it depends on the host to execute the workflow. Place the extracted `tokenband` folder into your agent's supported skills directory, then confirm the host can load the skill and map required capabilities:

- Read and write files in the project folder.
- Create, resume and title persistent task sessions.
- Report permissions, stops and completion back to the manager.

After placement, ask the agent to list or describe the skill to verify it is discovered. If your agent does not expose these operations, verify its integration before relying on the full task lifecycle. If TokenBand is already installed, back up the current copy and preserve existing TODO and task state before replacing files.

## Host compatibility

The instructions do not require a particular model family. The full workflow still needs a compatible application integration. The package has a Codex native route and a restricted-text Claude driver; the latter does not provide a complete Claude Code task lifecycle. Kimi Code discovery and state-preservation notes are included in [the host guide](../skill/tokenband/references/host-kimi.md); a bundled Kimi native driver and a full TokenBand lifecycle in Kimi Code are not established by this package. Check the actual integration rather than assuming that support for `SKILL.md` provides every operation.

## 3. One host-specific installation example

The following is one explicitly host-specific example for a known working setup, not a universal requirement:

1. Copy the extracted `tokenband` folder into `~/.codex/skills/tokenband`.
2. Start or resume a Codex session in your project directory.
3. Ask the agent: ‘Apply TokenBand to this project. First check the available host operations, reuse the existing setup and ask about any missing model-role choices.’

For other agent applications, use the host's supported skill discovery mechanism and check the same required capabilities. Copying files alone does not start tasks.

## 4. Confirm roles and the execution route

Before delegation, confirm the manager, executor, eligible reviewers, chosen mode and their actual execution routes. Reuse an existing trusted setup; otherwise the agent should ask for the missing choices. The empty configuration template does not select models or make a route ready to run.

API access and model usage costs depend on the chosen routes and are separate from the package. Keep credentials in the host’s supported protected storage. The optional bundled CLI requires Python 3.10+; ordinary coordination does not require that CLI.

## 5. Try a task

See [example.md](example.md) for a short illustrative walkthrough.

← [Back to README](../README.md)