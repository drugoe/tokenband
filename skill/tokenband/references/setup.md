# Initial setup and configuration

For an existing installation, follow [upgrade state preservation](paths.md) before
changing the installed skill; installing a new identity does not migrate state.

## Essential setup

Text/file coordination needs no bundled CLI. Using `worker.py` requires Python
3.10+/stdlib and its complete bundled worker/native/manifest/template/reference
set; selected native operations also need their actual runtime and credentials.
No particular primary family or agent platform is required for core routing.
Reuse trusted configuration. Only when missing and setup is authorized, `python
worker.py init` creates an empty template in `WORKFLOW_HOME`, otherwise
`Path.home() / '.tokenband'`; no private paths/model assignments ship in it.
Use the [portable setup chain](#portable-setup-chain), [modes](#modes-and-model-pool)
and [paths](paths.md) for role choices, anchored references and pinned runtime discovery.

The orchestrator resolves from trusted current settings: primary provider family, ordinary orchestrator, top primary, reserve primary, main external executor, eligible external alternatives, exact model/effort, supported transport and mode. Infer only known capabilities; catalogs do not prove access. Ask about missing material choices during ordinary first use. Honor a scoped instruction to decide autonomously by recording assumptions instead of waiting for questions. On later use, ask only about missing/changed choices or requested reconfiguration. Resolve the human's language from conversation or an explicit preference; all workflow communication follows that resolved language per [communication](communication.md). Set human_language to "auto" to follow the conversation's detected human language, or to an explicit human language code (for example a BCP-47 tag such as "en", "ru", "zh-Hans", "ar" or "pt-BR"); an explicit human preference wins over detection, and no language is privileged. Human-facing text (including mode labels) is shown in the human's language; internal instructions, briefs, handoffs and reports use the same resolved language per [communication](communication.md). The optional legacy internal_language field remains accepted for configuration compatibility and does not impose a workflow language; omit it in new configurations.

Keep every trusted named role choice and authorized external candidate in the setup record, including alternatives whose connection details are still pending; do not silently reduce the pool to its main executor. Materialize validated profiles only when their required metadata is known. Recording a user-identified top model in settings is not invoking it; scoped consent gates every actual top-model launch, not the storage of that role choice. Setup records are not a consent store: discover and bind the applicable trusted grant from protected user evidence before dispatch per [routing](routing.md#discover-and-bind-trusted-consent-before-dispatch).

User configuration is shared across folders. Host adapters are user-specific records with dynamically resolved interpreter/script references, pinned script SHA256 and platform identity. Each adapter must preserve actual parent permissions and owned kernel cleanup. Never store keys, key values, prompts, project names or project task queues in role configuration. Existing native registries retain provider authorization and protected key resolution. Adding a provider to an eligible pool requires its actual authorization; having a key is insufficient.

For each missing connection, ask for the provider ID, exact model/effort, API
base URL and supported protocol, registered native provider ID, and a protected
credential reference. Ask where the key is stored or which environment variable
contains it; never ask the human to paste a key into this chat. Reuse trusted
existing connection declarations. Keep connection metadata outside the skill.
An API endpoint cannot be inferred from a model's display name. Record text and
tool capabilities separately: API access does not establish file/shell support.
Setup questions use the human's language and can be grouped into one short form.
Missing credentials on a second host remain a setup prerequisite; do not report
them installed merely because the same model works on the first host.

## Portable setup chain

The neutral template deliberately has empty models/connections/runtimes and null
roles. It is not dispatch-ready; structural validation cannot select an executor
from null. Complete only the selected task's missing binding from trusted current
mode, provider/model/effort, named roles, eligible pool and actual grant. Preserve
choices still awaiting connection data; do not choose package defaults or rewrite
shared roles to make an example dispatchable. Apply [routing and consent](routing.md#discover-and-bind-trusted-consent-before-dispatch)
to the actual assignment.

Follow this chain once per selected provider/route. Reuse each resolved input:

1. **Native registration, native route only.** Reuse the selected host's actual
   registered provider ID, endpoint, wire API and protected native authentication
   mechanism. If fresh-client resolution needs missing durable registration,
   finish the supported add-only registration within existing setup authority;
   per-thread overrides alone do not establish fresh-client resolution. A text
   connection's `native_provider` is metadata, not registration. Keep the host's
   existing registry; a key or model catalog does not grant access.
2. **One credential reference.** A text connection declares exactly one
   `api_key_env` variable NAME or protected `api_key_file` anchored reference,
   such as `@workflow_home/credentials/demo-token`. Use [path anchors](paths.md),
   never values in chat/examples/argv/logs. Native routes use the host's own
   protected auth mechanism and any pinned auth dependencies; text credentials
   are not injected into native processes. There is no second credential registry.
3. **Native runtime binding, when selected.** Resolve `runtimes.<ID>.candidates`
   and `.commands` through protected current settings, bind the driver's
   `runtime: "@runtime:ID"`, reviewed executable `sha256`, actual compatible
   `version`/`protocol`, connection and native home. Inspect bytes without
   executing discovery candidates; a package installer does not upgrade a runtime
   or accept a newer pin. For Codex the resolved `native_home` must match the
   actual inherited `CODEX_HOME` in both lexical and physical identity, or the
   driver blocks with `native_home_mismatch`. A separately selected home needs
   that same process-scoped `CODEX_HOME`; it does not select `WORKFLOW_HOME`.
4. **Profile, connection and role.** Bind the selected profile using the route
   table below, then resolve the named role and all eligible alternatives from
   trusted choices. A null role stays null until such a choice exists. Materialize
   a missing task-local binding under existing authority, preserving shared
   defaults and other tasks. The native CLI selects `roles.main_external` from
   its execution config even for status/reconcile; retain that execution binding.
5. **Select before allocation, then verify the actual route.** For Codex use
   [pre-allocation selection](host-codex.md#bundled-codex-route-selection) with
   effective native request/stream retries both `0`. Verify structure and only
   the affected connection/binding, then perform the authorized real assignment
   under current controls. Ordinary schema2 needs no historical qualification
   ceremony; use [actual file evidence](host-codex.md#file-capability-and-exact-tool-evidence)
   if tools are required. Text, persistence, tools, GUI visibility and serving
   identity remain separate observations.

| Selected route | Task-local binding and boundary |
| --- | --- |
| Built-in text | `models.demo-text`: trusted provider/model/effort, `transport: "text-api"`, `adapter: null`, applicable `requires_consent`, no `chat` key. `connections.<provider>`: HTTPS `base_url`, `native_provider`, exactly one credential reference, explicit `protocol: "responses"` for the new Responses route or `"openai-chat"` for legacy Chat Completions. Omitted protocol remains legacy; do not auto-promote. See [worker transport](worker.md#built-in-text-protocols). |
| Codex native | `transport: "native-chat"`, `adapter: null`, `chat: {"driver": "demo-codex", "native_provider": "demo-native"}` with the ACTUAL selected native ID. `drivers.demo-codex` supplies the reviewed runtime binding above, `kind: "codex"`, separate `native_base_url`/`native_wire_api` pins and actual integration/auth/executable dependencies. The implemented binding currently accepts `version: "0.160.0"` / `protocol: "codex-0.160"`, native wire `"responses"`, and `connection: "auto"`, `"shared-unix"` or `"owned-stdio"`; a version label alone proves no compatibility. See [Codex](host-codex.md). |
| Claude native | The same native profile shape selects a reviewed `kind: "claude-code"` driver, compatible pinned runtime, `protocol: "claude-restricted-print"`, `connection: "owned-stdio"` and protected `settings`/`settings_sha256`. This implemented route is persistent restricted-print text, without file/shell tools, live steering or background survival. Its evidence rules remain in [Claude](host-claude.md); Codex evidence does not qualify it. |
| Separate corrected companion | Select only its reviewed external adapter/config pair and separately delivered inventory under [Step recovery](step-recovery.md#selecting-the-installed-correction). It is an optional alternative mechanism, not a dependency of built-in Responses or a native driver. |

These are field relationships with fictional demo IDs, not a complete runnable
config or authorization. Resolve actual endpoints and references outside the
package. For every optional invocation preserve the original process-scoped
`WORKFLOW_HOME`, any frozen `WORKFLOW_HOME`/`--config` pair, config path, guard,
receipts, current owners and unknown operations per [paths](paths.md). Do not
copy a config into a new default or remove `PRESERVE-EXISTING-STATE`. Reconcile
accepted/unknown work before changing a binding; no new route or owner recovers
it by replay.

The package supplies instructions, templates, `worker.py`, `text_responses.py`
and the bundled native modules/manifest. Python 3.10+/stdlib is required only for
the optional CLI, including built-in text. Native runtime/registration/auth and
an optional selected companion are host prerequisites, not shipped credentials
or automatic installer upgrades. Unsupported OS mechanisms are concrete route
limits, not a blanket verdict about text/file coordination on that OS.

## Byesu with the existing text and Codex routes

For an authorized Byesu binding, select `connections.<provider>.protocol:
"responses"`, `base_url: "https://byesu.com/v1"`, a protected credential reference
and the chosen ordinary model/effort (for example `gpt-6.1-sol` / `high`). Use the
[built-in text profile shape](#portable-setup-chain); no new adapter is needed.
For FILE and persistent native chat/reconnect, use that chain's existing Codex
driver with separately pinned native endpoint/wire, registered provider and
protected native authentication/home. Text credentials are not injected into it.
Normalized auth readback can omit reference details or add defaults; it does not
replace the pinned host setup or justify comparing whole auth dictionaries.

If the selected host's full model entry needs `code_mode_only` changed to `direct`,
prepare the protected host-local catalog under the [optional catalog contract](host-codex.md#optional-pinned-model-catalog).
Use a reviewed bundle implementing that field; unchanged 0.5.7 rejects it.
Linux and Windows each need their own runtime/full-entry provenance, native home,
credential/helper references and filesystem protection/cleanup evidence; do not
copy another host's paths or hashes. Preserve actual inherited controls (including
never/user/full access/network when those are the real parent settings).
TEXT success, native persistence, actual FILE use and GUI visibility are separate
observations. This recipe supplies no Desktop registration, serving attestation,
universal OS/runtime guarantee or standalone FILE service outside Codex.

## Optional CLI checks

`validate` checks structure and role eligibility. `doctor` checks credential-reference
availability, external adapter paths/host/pins and optional legacy metadata
app_server; it neither inspects drivers nor qualifies native readiness. Unused
legacy missing_app_server is not a native prerequisite. Neither command reads
credential values or starts inference, candidate runtime, chat or benchmark.
Setup changes no global provider/default model, active chat model or running agent.

## Selected native session setup

For persistent chats resolve the session host/driver separately from primary
family: connection, pinned runtime, supported model/tool protocol, actual
permission context, persistence and exact-session continuation. Ask only for
missing choices. Tool work needs a compatible implemented binding under actual controls; persistent text-only work
cannot edit/run tests. Read the selected [host guidance](chats.md). Runtime
installation or pin upgrade is a separate scoped action, never automatic doctor repair.

For Codex inspect integration names/enabled flags and populate disabled_mcp_servers
for worker launches; preserve globals/other sessions. Missing or newly enabled
integrations need setup reconciliation, not weaker checking. Before native tools,
[ordinary execution](qualification.md#ordinary-codex-schema2-execution) checks
effective executable copies, auth dependencies, final profiles and current controls.
Ordinary Codex schema2 does not require historical diagnostic receipts; schema1
and Claude retain their evidence rules. Mocks/version strings prove no file result.

For a file-development task, discover the existing supported native file/tool
route and repair an unsuitable TASK-local text-only/null-adapter profile promptly
within standing setup authority. Reconcile active/unknown operations first; reuse
configured provider choices and credential references. Preserve roles, global
defaults and other tasks. Then run the affected validation/doctor, bounded local
compatibility check and actual bounded task. Optional diagnostic qualification is
not an ordinary schema2 prerequisite. Report concrete remaining access,
protocol or quota limits and continue disjoint authorized work. No repair service,
new driver or extra global grants are introduced.

Bind the actual command path as well as the model name. For an existing bundled
Codex native-chat route, the TASK-local model uses `transport: "native-chat"`,
`adapter: null` and its reviewed `chat.driver` binding; native commands resolve
that sealed driver. Ordinary Codex schema2 uses `sprint-create` then exact-chat
`sprint-send`; do not require `native-qualify` or adopt its old journal.
Normal `dispatch` deliberately returns `native_sprint_required` for this profile.
These historical command and journal names remain the native API for one persistent
task execution unit: `sprint-create`/`sprint-send` bind a unique TASK execution
unit ID (historical `--sprint`/sprint_id) linked to its sprint and stage in the
existing TODO, not one aggregate journal for all stages or tasks.
Do not leave file work bound to an incompatible legacy app-server adapter or
call a text-only profile a file route. Record the resolved executable/module
hashes, task profile and actual file read/write results; validation alone is not
qualification. An unchanged, separately qualified adapter route remains valid.

Keep an existing native sprint's reviewed execution binding. All bundled native
commands, even status/reconcile, select the execution config's current main_external
and reject primary-only mode. Prepare its protected config at the intended stable
path before first operation; review resolved references and preserve profile/model/
effort, driver/runtime, context/environment. Use --config throughout; future choices
may use another reviewed config. Bytes freeze within an operation; across completed
operations checks compare stored binding, not the entire prior config hash.

Optional diagnostic qualification starts with the pending record and separately authorized synthetic
operation, then independent evidence acceptance and promotion of the matching
qualification record/config pin BETWEEN completed operations for the SAME binding.
These diagnostic journals are not ordinary sessions; preserve and reconcile their
original records. Do not promote one into an ordinary send. Do not change
unrelated bound settings or imply snapshots/migration; see
[existing-session configuration](chats.md#existing-session-configuration).

Inspect selected kind/platform/protocol, runtime/helper paths/reviewed hashes,
protected home/settings/auth references and exact binding/final-profile evidence.
Do not read credential values or execute runtime discovery merely to fill this
checklist. Codex local probe/synthetic tool bootstrap follow the actual rights
and conditional sandbox requirements in [qualification](qualification.md); this optional bootstrap is
Codex-only. Claude needs independently established compatible restricted-print
session evidence; presence/help is insufficient. This is manual guidance, not
another doctor command.

## Complete selected chat setup

Use this section for an explicit internal coordination-chat request on a new
account/host or to complete the selected session setup. Installation supplies reusable instructions
and bundled code, not another account's authentication, provider registry or
qualified runtime binding. Resolve the [requested outcome](chats.md#requested-chat-outcome)
and inspect the selected host before concluding that creation is unavailable.

Maintain the distinction between these existing inputs; do not add another
registry, readiness service or task queue:

| Input | What to inspect and finish within existing authority |
| --- | --- |
| Role/model choice | Requested managing or task role, exact authorized identity/effort and mode; reuse known choices, do not substitute a model or redefine roles globally. |
| Workflow text connection | Follow the [portable chain](#portable-setup-chain): explicit built-in `responses` or legacy `openai-chat`, known endpoint and one protected credential reference. Do not repeat a successful text probe to establish persistence/tools. |
| Native host provider | Actual registered provider ID, supported native endpoint/wire/auth mechanism and selected runtime schema. Text aliases can differ; openai-chat does not establish Responses or native tool protocol compatibility. |
| Host/driver binding | Real OS, verified runtime/protocol, current permissions, persistence and supported lifecycle. Check available native tools or documented host transport; doctor/validate do not replace this. |
| Tools, if requested | Ordinary Codex schema2: current compatible runtime and actual controls, then actual file-result evidence; no historical qualification ceremony. Legacy schema1/Claude retain evidence checks. Text creation alone proves no file capability. |

Resolve project and folder binding for the requested chat under
[chats](chats.md#project-and-folder-binding) and the selected host's supported
mechanism (for Codex, its [host surface](host-codex.md#project-and-folder-binding-on-the-codex-host)):
extra task, sprint or worktree folders are created inside the canonical
project root and stay in the existing project, and an unverified `projectId`
remains omitted with its concrete pending recorded in the existing
TODO/evidence.

Inspect nonsecret declarations and credential-reference availability without
printing whole credential-bearing settings, environment or connection strings.
If existing data already resolves a field, reuse it. A missing workflow chat
binding is not proof the host's native provider/route is missing: inspect both.
Conversely a registry entry or existing API key is not proof of access or consent.

Perform supported minimal task-scoped connection/binding preparation when already
authorized, preserving existing configurations and running sessions. Record
changed settings and source evidence outside task-writable roots where required.
When fresh-client reopening requires durable native provider registration,
perform the supported add-only registration under existing setup authority;
per-thread overrides alone do not establish fresh-client resolution. Reconcile
unknown operations before changing bindings. If a change exceeds that authority,
needs new provider/data authorization, runtime installation/pin upgrade or another
ungranted action, prepare its exact scope and ask only for that material decision. Do not merely tell the human to
"connect a host" or hand back a generic setup checklist. Unsupported native wire
or a missing protected credential reference stays a concrete missing input; do
not guess an endpoint/protocol or request a secret pasted into chat.

After setup, recheck only the affected route/binding and continue the original
create-chat request using its existing reservation; do not require the human to
repeat it, create a second intent or replay an unknown send. Creation/persistence,
visibility and tool qualification keep their separate evidence requirements.
Keep a small result: actual selected route/checks, known/missing setup, completed
changes, resulting chat/turn IDs or exact blocker and prepared next action.

### Built-in schedule setup

To establish the active manager's single built-in same-chat hourly schedule
([host-codex](host-codex.md#built-in-same-chat-hourly-manager-schedule)), first discover
the actual supported automation/schedule tool on the selected host (including
`automation_update` where exposed); an empty result is a concrete finding, not proof of server
incapability, and a Pages/Sites schedule tool is a different target that must not
register this native manager chat. Reconcile any existing schedule and pending creation
intent for the exact manager chat ID before acting; create or update idempotently so
exactly one hourly same-chat schedule exists with the exact manager ID, cadence and
timezone configured, never a per-task schedule and never one on an inactive chat.
Before the first create/update, durably save its exact intent in the existing task evidence: manager chat and host, operation and known schedule ID for an update, cadence/timezone, and prompt identity. A prepared intent is not registration. After interruption, reconcile that intent, any ACK and the actual schedule without replay.
After create/update, save the ACK before any later operation, then read back
the exact chat ID, cadence, timezone and target before treating it as configured; an unknown create/turn outcome requires
reconciliation, never replay.

A schedule is LIVE only after that supported create, ACK, readback and an observed hourly
run and effect. If no supported tool is exposed, skip automation setup, briefly record
that actual reason in the existing task evidence and continue authorized work without
waiting for the tool or creating a required pending follow-up solely for this absence.
Do not treat unavailable automation as a prerequisite to task execution or acceptance;
preserve any existing unknown operation and actual task constraints. Do not register the schedule
through files, TOML, raw RPC, cron or any other product, and do not claim a live or timed
run from a manual check.

## Modes and model pool

Supported modes: **primary-budget-saving**, **primary-only** and explicit
**external-only**. Configure and record these canonical identifiers; present them
to the human in the human's language (translated labels are fine, and no
language is privileged). The last is a strict provider restriction; it is
distinct from conserving primary limits. `primary-only` excludes external
providers even for review. A task-specific restriction takes precedence over a
broader configured pool. Missing mandatory capability or review is a blocker,
not permission to weaken a gate. No separate application-specific mode belongs
in this skill. Provider/model IDs identify connections, never mode names.

The model pool is configurable; it is not a fixed three-provider list. Add
authorized model profiles and connections through user settings without editing
this skill. Keep provider-specific API protocols and adapters separate from
roles and fallbacks. A compatible text API can support many providers; a
different protocol or tool capability requires its supported reviewed adapter.

## Fictional first use with ordinary files

OPTIONAL: use this section for an explicit offline onboarding/structural-file
exercise, not each first use or missing connection. Essential setup above is
sufficient for the chosen route; reuse existing choices/configuration. This
complete specimen uses fictitious models, `.invalid` endpoints and dummy credential
REFERENCES. It demonstrates structure, not ready access or host/tool qualification.
Never set real tokens or call these endpoints; effort labels are illustrative.
Keep actual authentication/host settings outside this reusable package.

```json
{
  "schema_version": 1,
  "mode": "primary-budget-saving",
  "human_language": "auto",
  "primary_providers": [
    "demo-primary"
  ],
  "models": {
    "manager": {
      "provider": "demo-primary",
      "model": "demo-primary-model",
      "effort": "high",
      "transport": "desktop",
      "adapter": null,
      "requires_consent": false
    },
    "reserve": {
      "provider": "demo-primary",
      "model": "demo-reserve-model",
      "effort": "high",
      "transport": "desktop",
      "adapter": null,
      "requires_consent": false
    },
    "executor": {
      "provider": "demo-external",
      "model": "demo-external-model",
      "effort": "high",
      "transport": "text-api",
      "adapter": null,
      "requires_consent": true
    },
    "reviewer": {
      "provider": "demo-review",
      "model": "demo-review-model",
      "effort": "high",
      "transport": "text-api",
      "adapter": null,
      "requires_consent": true
    }
  },
  "roles": {
    "orchestrator": "manager",
    "top_primary": null,
    "reserve_primary": "reserve",
    "main_external": "executor"
  },
  "external_order": [
    "executor",
    "reviewer"
  ],
  "adapters": {},
  "connections": {
    "demo-external": {
      "base_url": "https://executor.example.invalid/v1",
      "native_provider": "demo-external",
      "api_key_env": "TB_DEMO_EXECUTOR_TOKEN",
      "protocol": "openai-chat"
    },
    "demo-review": {
      "base_url": "https://reviewer.example.invalid/v1",
      "native_provider": "demo-review",
      "api_key_env": "TB_DEMO_REVIEW_TOKEN",
      "protocol": "openai-chat"
    }
  },
  "runtimes": {},
  "app_server": null
}
```

Save it as `fictional-config.json` in an owned offline fixture. If exercising the
bundled validator, use actual resolved paths and native quoted arguments:

```text
python "<resolved-skill>/worker.py" --config "<fixture>/fictional-config.json" validate
```

Use the available Python command on Windows. `valid_structure` /
`inference_started=false` establishes schema only. This exercise does not require
init/doctor/native setup, dispatch, paid requests or a second Codex installation.

For an optional ordinary-file walkthrough, use fake IDs and Unicode/space paths
in an owned fixture. Apply [lifecycle admission](lifecycle.md#allocate-and-reserve-before-dispatch)
and existing [assignment](../assets/assignment-template.md),
[result](../assets/result-template.md) and [resume](../assets/resume-template.md)
fields once: record allocation/reservation before any hypothetical send, retain
manager launch ownership/proposed executor until a clearly SYNTHETIC ACK, and
match that ACK within unchanged scope. Stateless identity is assignment/invocation;
persistent examples additionally bind exact fake chat/turn. Reopen actual inputs,
create/check the requested artifact, save result/checkpoint and resume from files.
Try missing/stale/conflicting/unknown ownership or outcome, pause/Stop, unaccepted
dependency and wrong ACK; preserve originals and record zero real sends.

Keep actual inputs/actions/outputs and byte/hash evidence. A hand/synthetic ACK
exercise is not software admission enforcement, real dispatch/GUI visibility,
independent acceptance or native/scheduler qualification. Report unrun cases.
Linux/Windows file workflow needs actual per-OS path/lock/crash evidence; Linux
results do not qualify Windows. Actual native delivery, tools, scheduler and
cleanup need their selected host's independent evidence under [qualification](qualification.md).
Native persistence/read-only selection does not suppress tools; see [chats](chats.md#managing-titles-and-intake).
Use existing worker body/reference/filter checks; file examples establish neither
native filtering, power-loss/network-filesystem behavior nor serving model identity.
