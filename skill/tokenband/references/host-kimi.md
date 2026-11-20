# Kimi Code: skill discovery and native boundary

Read this reference when the selected host is Kimi Code CLI. The configured
primary family, project owner and task identities remain user choices.
Loading TokenBand instructions is separate from operating persistent task chats.

## Load the complete skill

For an authorized skills installation, use directory form: a `tokenband` folder
containing `SKILL.md` and all bundled supporting files. Copying only `SKILL.md`
leaves its references and optional worker dependencies unavailable. Directory-form
frontmatter needs `name` and `description`, which TokenBand already supplies.

Kimi documents these discovery locations:

- User: `$KIMI_CODE_HOME/skills` (default `~/.kimi-code/skills`) and
  `~/.agents/skills`.
- Project: `.kimi-code/skills` and `.agents/skills`. Its documented project-root
  search uses the nearest ancestor containing `.git`; verify that resolved root
  rather than assuming it is TokenBand's canonical project root.
- Additional roots can be configured with `extra_skill_dirs`. This is an
  existing host option, not an instruction to change a working configuration.

Automatic discovery from `~/.codex/skills` is not promised. Select one intended
placement and verify the actual skill variant/path when several workspace roots
or same-name skills exist; avoid divergent copies. In Kimi, `/skill:tokenband`
is the documented explicit invocation form. Discovery or a successful textual
reply proves neither native task management nor tool access.

Keep installation files separate from workflow state. Follow [paths](paths.md)
to retain the original `WORKFLOW_HOME`, frozen config/home pairs, guard, receipts
and unknown operations. Skills placement does not initialize or migrate that
state, copy authentication, select new roles or change defaults. Use existing
authorization; ask only for genuinely uncovered actions under [setup](setup.md).

## Persistent tasks need a supported host mechanism

The bundled `sprint-*` CLI currently implements native driver kinds `codex` and
`claude-code`; it has no Kimi-native driver. Do not configure an invented `kimi`
kind or treat a Codex connection as Kimi's API. This is a limitation of the
bundled route, not a claim that Kimi lacks sessions or that ordinary answers
require that CLI. If the selected host exposes another supported mechanism,
verify its actual capabilities and controls before dependent work under
[chats](chats.md) and [qualification](qualification.md).

Kimi's documented server API is experimental. Its live authenticated
`/openapi.json` and `/asyncapi.json` describe the particular server. The published
repository schema below has `info.version: "0.0.0-fixture"`; it is source evidence,
not proof of an installed version or compatible runtime. Resolve an existing
trusted binding, version and permission boundary before an authorized host check.
Discovery does not authorize installing a CLI, starting a server or reading or
transferring token values. Loopback, authentication success and a permission-mode
name alone do not prove process identity or a mapping of the parent's controls;
do not translate Codex permission names or infer bypass authority from `yolo`.

For a future native route, separately verify exact-session creation and
continuation, project/work-directory binding, rename/readback, model and tool
access, result delivery, Stop and recovery. Kimi workspace IDs are not Codex
project IDs. Backend persistence and client visibility require separate evidence.
`prompt_id` idempotency does not establish exactly-once tool effects. A cancel
ACK is not terminal or descendant-cleanup proof; `idle` or a completed turn is
not file quiescence. Preserve intent, exact IDs and unknown outcomes and apply
the existing [operations](operations.md) rules, including any accepted scoped
local continuation policy. Do not automatically replay, create a replacement
chat or use takeover to seize another live owner.

State the concrete available capability and missing prerequisite in the human's
language. Continue independent authorized work. A loaded skill, source review
or mocked API is not full Kimi-native qualification or a reason to repeat an
already accepted development decision.

Sources: official [Skills documentation](https://github.com/MoonshotAI/kimi-code/blob/83e4dde93453dd22e89da03d2c96d84999e7d0c2/docs/en/customization/skills.md),
[server API documentation](https://www.kimi.com/code/docs/en/kimi-code-cli/reference/server-api.html)
and the pinned [repository schema](https://github.com/MoonshotAI/kimi-code/blob/83e4dde93453dd22e89da03d2c96d84999e7d0c2/packages/kap-server/schema/openapi.json).
