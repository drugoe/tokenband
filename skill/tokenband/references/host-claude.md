# Claude native session integration

Read this reference only when the selected session host is Claude Code. The
primary model family remains a user choice; a Claude managing chat can also use
a separately qualified host driver. Resolve the selected native executable and
configuration from user settings and runtime discovery, then verify its pin and
supported protocol. No fixed personal path is part of this package.

Claude exposes the Agent SDK through Python, TypeScript and the programmable
claude -p CLI. Persistent sessions can resume by exact session ID. Track the
returned ID and verify that continuation retains it; avoid latest-session
selection when several sprints exist. Do not enable fork or suppress persistence.
See [programmatic CLI](https://code.claude.com/docs/en/headless) and
[SDK sessions](https://code.claude.com/docs/en/agent-sdk/sessions).

The bundled native_claude.py implements this persistent programmatic analogue
using the CLI's restricted print/stream-json protocol. It uses an exact UUID,
checks native initialization before the task brief, reconnects with --resume,
and sends later briefs to the same session after a terminal prior turn. Its
implemented scope is foreground text work with native tools disabled. It does
not implement Agent SDK dependencies, live steering, background ownership or
desktop registration; those require a separately supported integration.

Claude Code also has supervised --bg sessions and agents --json --all,
attach, logs and scoped stop. Background and print modes are distinct.
Resuming an active background session can copy it; never accept a changed ID as
same-chat continuation. An agent-view record does not prove desktop visibility.
Check the installed version before choosing a route. See the
[CLI reference](https://code.claude.com/docs/en/cli-reference).

Use native permission handling and qualified tool restrictions, not invented
Codex RPC or approval fields. allowedTools auto-approves matching tools;
tools controls availability. Preserve managed policy, prohibit bypass modes,
and deny unattended requests that have no authorized handler. A native permission
mode alone does not prove an OS sandbox. If the caller requires a specific
approval system or boundary, qualify that mapping or report the missing
capability before work. See [SDK permission flow](https://code.claude.com/docs/en/agent-sdk/permissions).

Select only capabilities actually implemented and qualified on that OS. Report
backend persistence, confirmed model identity, tool access, same-chat management,
execution lifetime and client visibility separately. Installed CLI/help evidence
does not prove provider access or successful model execution.
