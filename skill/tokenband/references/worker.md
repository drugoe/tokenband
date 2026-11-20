# Bundled worker

This optional CLI needs Python 3.10+ and its standard library on Windows/Linux;
ordinary text/file coordination needs no CLI. Run `python worker.py --help` from
the skill folder when using it. Keep the root worker, `text_responses.py`, native modules/manifest,
template and references together: current verified/imported bundle dependencies
still apply. Put `--config PATH` before the subcommand; see [paths](paths.md).

For upgrade state preservation, default guard behavior and explicit home selection,
follow [the canonical path contract](paths.md) before optional commands.

## Setup and ordinary assignments

- `init` creates the empty template in WORKFLOW_HOME, otherwise ~/.tokenband;
  it preserves existing configuration.
- `validate` checks structure; `doctor` inspects connection credential references,
  external adapter paths/host/pins and optional legacy metadata app_server only.
  It does not inspect native drivers, their qualification or native readiness.
  Missing unused legacy app_server is not evidence against a native driver.
  Neither command reads credential values, executes candidates or starts inference;
  use the [manual native setup checklist](setup.md) for native prerequisites.
- `select --role ...` proposes eligible profiles and required review counts.
  It never starts fallback or accepts a review.
- `dispatch` executes a compatible text connection or configured reviewed tool
  adapter using assignment ID, trusted scoped evidence, prompt and protected
  results; no arbitrary flags/environment are accepted.

Before EVERY delegated send apply [lifecycle admission](lifecycle.md#allocate-and-reserve-before-dispatch),
including sole-TODO reservation. This manager policy check is not a worker TODO parser.
For review supply actual `--author-profile`, `--author-invocation` (also coauthors)
and fresh `--invocation-id`; stateless review needs no fabricated chat/turn.
`--allowed-provider` narrows eligibility; `--needs-tools` excludes text transports.
Reserve dispatch needs each eligible external's recorded assignment-specific
`--external-blocker`; a proposal is not failure evidence.

Connections declare HTTPS base_url, native_provider, supported protocol and exactly
one protected api_key_file or api_key_env reference under the canonical
[portable setup chain](setup.md#portable-setup-chain). Built-in text supports
literal `responses` and legacy `openai-chat`; omitted protocol stays `openai-chat`.
Other protocols need an implemented reviewed adapter. Text profiles use
`transport: "text-api"`, `adapter: null` and no `chat` metadata. A connection's
native_provider names metadata; it neither registers a native provider nor grants
tools. No credential values belong in role configuration, chat, argv or logs.
No redirects or arbitrary headers are exposed. Keep public text separate from
hidden reasoning and raw errors.

Text dispatch accepts a trusted `--protection-context`, or an applicable native
`--parent-permissions` envelope. The neutral context contains schema=1,
writable_roots, temp_roots and protected_names. It protects configuration,
credentials, evidence, receipts and results against every actual caller writable
and temporary root; it grants no tools or vendor permissions. The caller establishes
provenance. Schema validation cannot authenticate a human or permission source.
Outer network approval remains necessary when required by the actual host.

The built-in text dispatch and uncertainty context also accept the actual schema2
context described in [actual context and control integrity](qualification.md#actual-context-and-control-integrity).
It retains all actual roots, approval and network settings, including a full-access
caller with writable root `/`. This is integrity-only protection, not filesystem
exclusion or a tool/vendor permission grant. Neutral schema1 and the legacy
`--parent-permissions` envelope keep their existing exclusion checks. Native
tool-free callers do not inherit the text-only schema2 opt-in.

Actual text freezes lexical/canonical config, authorization, context, brief and
credential references and worker/selected Responses helper source bytes. Context
is sealed before parsing and checked afterwards; the helper is sealed before
import and checked after loading. The existing guard runs before credential use,
every physical POST (including proven-unaccepted 429 recovery) and publication.
Alias/reference/byte drift blocks further requests. After possible acceptance the
original receipt fence remains unknown; it never permits replay. A fully authorized
process can still write these paths; seals do not prevent hostile replacement and
restoration between checks. Trusted provenance and authorization remain separate
from structural validation.

Rejected, unaccepted 429 recovery is bounded; ambiguous acceptance never replays.
Protected assignment receipts remain stable beside configuration regardless of
the requested output directory. A wrapper exit does not prove remote termination
or native descendant cleanup. Read [operations](operations.md).

For the separately delivered corrected Step Responses adapter, see
[Step text recovery](step-recovery.md); it is distinct from this CLI's built-in
text transports and native chat drivers.

## Built-in text protocols

The bundle includes `text_responses.py`; selecting built-in Responses needs no
personal host companion. For a NEW authorized task-local binding choose explicit
`connections.<provider>.protocol: "responses"` only from trusted supported
connection data. Installation does not promote legacy profiles or change an
existing operation's protocol/config. `"openai-responses"` is not an accepted
protocol value. `openai-chat` keeps its Chat Completions request/receipt behavior.

For `responses`, compose the endpoint exactly as
`base_url.rstrip('/') + '/responses'`. The HTTPS base URL has no userinfo, query,
fragment or credential value; there is no request-time destination override.
Each attempt sends one POST with exactly this body shape, resolving model, brief
STRING and effort from the frozen assignment/profile:

```json
{"model":"demo-model","input":"demo brief","stream":true,"reasoning":{"effort":"high"}}
```

No `store`, `max_output_tokens`, `tools` or `tool_choice` is sent. The headers are
`Authorization: Bearer <protected credential>`, `Content-Type: application/json`,
`Accept: text/event-stream` and `User-Agent: tokenband/1`; values are never logged.
The no-proxy opener (`ProxyHandler({})`) and no-redirect handler are mandatory;
3xx and a final URL different from the composed endpoint are rejected. Before
EACH physical POST, including a permitted retry, the worker rechecks the frozen
config, brief, authorization, controls and credential reference/identity.

SSE parsing bounds each raw line and the aggregate raw event, including framing,
to 2 MiB BEFORE append/join/decode; only an actual event delimiter resets the
event bound. UTF-8 decoding is strict. Public text has a 1,000,000-character
buffer guard; these are safety bounds, not a forced output-token budget.
Reasoning is counted then discarded, never persisted or published. Tool/function
events, refusal or a public reasoning marker produce a known failed outcome;
the text route executes no tools and is not a native/file route. Unsafe public
content is purged, including when later parsing/EOF fails; observed known failure
is not downgraded to unknown. Raw errors, headers and arbitrary metadata have no
public sink.

Only proven **unaccepted transient HTTP 429** permits at most three retries,
four attempts total. Delays are max(15/30/60 seconds, valid Retry-After); an
invalid present hint blocks retry. One shared 180-second recovery budget bounds
waits and requests across client layers, including HTTP status/header and body
reads. If a hint exceeds the remaining budget, no early retry is sent. Quota
body classifications take precedence over transient 429; quota/access failures
create no account cooldown or automatic same-request fallback. Accepted or
possibly accepted work is never replayed. Apply [operations](operations.md) for
reconciliation/recovery and [routing](routing.md#apply-routing-to-every-assignment)
for the next genuinely new assignment's fresh role selection; an earlier failure
does not permanently exclude its configured executor.

## Public text result contract

Built-in text dispatch preserves the canonical assignment receipt namespace and
exclusive duplicate barrier across output-directory changes. The result JSON is
now a small schema2 descriptor of `<assignment>.public.txt` with exact path,
UTF-8 byte count/body SHA256, completeness and availability. Receipt result_sha256
hashes the descriptor; it is distinct from content_sha256. Use read_public with
the expected protected path to verify/read a bounded body; ordinary file reads
can stream larger inspection without loading a sprint history. External inline
`content` readers must be migrated before integration. No optional old-format
export or control daemon is provided.

`text_completed` is nonempty with `completeness: "complete"` and
`public_availability: "available"`; `text_incomplete` preserves filtered
incomplete public text, with nonempty Responses text marked `partial`;
`text_empty` is terminal but unusable. Responses `text_failed` retains a known
failed/cancelled/refusal/tools/reasoning-marker outcome with an unavailable
descriptor and unknown completeness. `text_content_unavailable` retains observed
termination/completeness without a safely published body when its small receipt
can still be committed. After a known Responses terminal, final redacted UTF-8
text over the 2 MiB public-file bound is not truncated or downgraded to unknown:
content_file/content_bytes/content_sha256 are null, availability is `unavailable`.
The character guard alone does not guarantee Unicode text fits that byte bound.
Use read_public only for a descriptor with an actual body (`available`, `partial`
or `empty`); an unavailable descriptor has no body to read. Its saved receipt and
descriptor retain the observed terminal/completeness for reconciliation.

For Responses, accepted EOF without a terminal, malformed/oversize accepted SSE
or ambiguous connection/ACK stays receipt status `unknown`, terminal `unknown`
when observed, with no terminal result descriptor and the original dispatch fence.
Known failed evidence remains known even after a later parse/transport error.
Legacy `text_terminal_unknown` and inline text_completed remain readable under
their existing rules, with unknown completeness where applicable. Terminal result
descriptors resolve dispatch uncertainty, not task acceptance/review or replay
eligibility. If durable publication fails, preserve actual saved evidence and
the launch fence; do not claim a descriptor was committed.

Credential redaction precedes every body/temp sink. Only assistant public content
is retained; structured reasoning/arbitrary metadata/errors/headers are discarded.
Optional usage includes bounded nonnegative numeric counts (not booleans), cached
input/reasoning subsets and fixed reason enums. Invalid optional fields cannot
change valid public bytes/completeness. Optional provider model/request/response
strings are deferred (null/deferred), including identifier-looking values and
credential echoes; requested profile remains distinct and serving attestation is
not inferred. Native stronger secret/marker filtering remains route-specific;
this package does not invent an unavailable native scanner.

Responses incomplete metadata reads only response.incomplete_details.reason and
response.usage. incomplete_reason records reported/missing/invalid/unknown;
only max_output_tokens and content_filter are known reported values. Missing
reason does not prove token exhaustion; strict integer usage and sanitized reason
observations never include raw errors, IDs or private reasoning.

Linux uses same-file flock and directory fsync; Windows uses byte-zero msvcrt
locking and file fsync/replace, without claiming POSIX directory/power-loss
semantics. Private protected parent permissions/ACLs are a prerequisite, not
established by path checks. Alias/reparse/multi-link/special/device control paths
fail closed. UNC/network/cloud filesystem support and actual Windows behavior
require separate evidence; Linux tests or mocks do not qualify them.

## Persistent sprint sessions

Use the native sprint commands for an authorized external worker assignment
linked to the task’s internal coordination chat. The historical
command and journal names remain the native API for one persistent execution unit:
`--sprint`/sprint_id binds the unique TASK execution unit ID, linked to its
sprint and stage in the existing TODO, not one aggregate journal for all stages
or tasks:

- `sprint-create` verifies the selected main external profile, initializes one
  persistent chat, checks identity and persistence, then sends the real brief.
- `sprint-send` continues the same chat after a confirmed terminal prior turn.
- `sprint-status` and `sprint-reconcile` inspect the existing protected identity;
  use them after the foreground owner releases the journal. They do not allocate
  a replacement or replay an uncertain operation.
- Concurrent live status, `sprint-steer` and `sprint-interrupt` are unavailable in
  the bundled foreground drivers. Their owner holds the journal through the turn.
  Do not promise delivery, stop another process or create a replacement chat.

Без `--profile` native команды по-прежнему выбирают execution config's
main_external. Явный `--profile ID` ограничен main_external и настроенным eligible
reserve_primary; mode/tools/native binding и exact authorization проверяются для
выбранного профиля. Произвольный профиль, primary reserve в external-only и любые
native sprint в primary-only запрещены. Это не смена defaults/global config.
Для main_external сохранена прежняя возможность optional `chat` binding наряду
с другой external transport surface: native driver выбирается по binding;
нового запрета такого main-профиля нет. Для reserve сохраняются `select_role`
eligibility и требование действующего native-chat маршрута.
На send/status/reconcile передавайте исходный explicit profile, если он отличался
от main_external: frozen selected не мигрирует и несовпадение блокирует driver.
Retain its reviewed execution binding and prefer the original
protected config path; use a separate config for future role choices. Config bytes
are frozen within an operation. Across completed operations the same-binding
qualification-record/pin promotion is retained only for its explicit legacy/diagnostic workflow; ordinary schema2 does not require it. See [ordinary execution](qualification.md#ordinary-codex-schema2-execution).
Read [existing-session configuration](chats.md#existing-session-configuration)
before changing defaults; no automatic stored-profile migration is implemented.

Supply `--workdir`, `--sprint`, `--parent`, and `--authorization-file`.
Creation/send take `--brief`; mutations need a unique `--operation-id`.
Supply either the native tools
`--parent-context` or tool-free `--protection-context`, matching the driver.
Use generated help for the complete current command syntax.

Для уже разрешённого native continuation существующий caller теперь доступен
как `sprint-create ... --profile RESERVE_ID`; это прежний execution unit API,
не новый dispatcher. Сначала менеджер классифицирует exact outcome/пригодность
partial и разрешает передачу записи по [operations](operations.md), фиксирует
в sole TODO текущие assignment grounds и причины пропуска eligible внешних
альтернатив, выбирает reserve через `select --role reserve_primary --needs-tools`,
выдаёт exact authority и brief только оставшегося scope. Main external назначение
само по себе не отменяет standing reserve, но выбор профиля не создаёт grant.
После этого новая разрешённая операция запускается через прежние main/run/
preflight/driver. Для supporting actor сохраняется исходный task coordinator;
это не разрешение заводить новый task chat вместо существующего.

CLI не обнаруживает прежнего writer другой операции и не проверяет cleanup
автоматически. Допустимость нового linked native назначения на оставшуюся
обратимую локальную работу определяет default policy в [operations](operations.md):
после uncertainty deadline отдельные project opt-in, exact terminal и cleanup
не требуются; исходные разрешения, текущий scope и actual controls сохраняются.
Для непокрытых эффектов нужна прежняя граница; ACK/новая папка её не создают. Флаги подтверждения cleanup не
введены. Для fresh text-only после конечного ожидания уже существует
`uncertainty-continue --profile`; его finite chain/consent/independence не меняются,
а native review с shell/report write не становится text-only. Отсутствующий binding
резерва — конкретный missing capability, не автоматическая смена transport.
Отдельная top-авторизация native scope сохраняет технический `role=main_external`
и exact profile в `native_top_assignment`; старый top grant другого profile или
operation не подходит. Live control, denial/Stop и UNKNOWN не ослабляются.

Bind model.chat={driver,native_provider} in user configuration. Named drivers
retain kind, runtime, sha256, version, protocol, connection, native_home,
and, for legacy/diagnostic use, the paired qualification and qualification_sha256.
For ordinary Codex schema2 that pair is optional and no historical record is loaded.
For a selected native route read [chat coordination](chats.md) and ONLY its host:
[Codex](host-codex.md) or [Claude](host-claude.md), with distinct actual controls.
The [portable chain](setup.md#portable-setup-chain) owns registration, protected
references, `@runtime:ID`, actual native home and task-local profile/role binding;
[Codex route selection](host-codex.md#bundled-codex-route-selection) owns
pre-allocation choice, retry 0 and retained-operation/no-new-owner limits.
Stateless dispatch alone does not trigger either host's setup.

Ordinary Codex schema2 follows [ordinary execution](qualification.md#ordinary-codex-schema2-execution),
with current compatibility, actual controls and operation-scoped integrity checks.
It needs no historical qualification, recipe or synthetic bootstrap. Optional
diagnostics and legacy schema1/Claude retain their own evidence requirements;
mocks/help/success flags establish no observed native file capability.
The optional native_helpers mapping pins the platform's required native sandbox
helpers; Windows schema1 Codex requires both supported sandbox helpers; schema2 full access
uses its main executable without an unused sandbox. Linux and
Claude do not inherit Windows helper requirements.
Codex's optional disabled_mcp_servers lists native server names to disable only
for this launch. Setup inspects names and enabled flags without copying their
arguments, environment or credentials. Any remaining enabled integration blocks
the driver; neither disabling plugins nor an empty merged table proves MCP off.
Claude instead uses its protected, strictly empty MCP declaration.
Codex drivers also pin native_base_url and native_wire_api independently of the
worker's text protocol. The selected native provider must already be registered
in the protected native home with its own authorized authentication mechanism;
the worker does not inject text-connection credentials into native processes.
The exact native config.toml bytes join the session binding. Changing that file,
its path or the endpoint/wire pins invalidates subsequent mutations until the
affected configuration and stored session binding have been reconciled. Ordinary
schema2 does not add a historical requalification requirement.
For a separate Codex native home, launch the worker with that same CODEX_HOME
value in its owned process environment; it must match the configured native_home.
The optional Codex-only `native_model_catalog` record is defined by the
[pinned catalog contract](host-codex.md#optional-pinned-model-catalog); it is not
a text transport, credential field or model-registration command.
This optional host adapter setting does not change WORKFLOW_HOME or core path
resolution. Freeze the reviewed native configuration and authentication references
in that protected home before probing. Do not copy session history or credentials
as a substitute for setup. On Windows, establish elevated native sandbox readiness
through the host's legitimate setup flow before attempting tool qualification.
Tool confinement must cover initialization and substantive execution, including
actual file/shell paths and denied secret reads. An unrestricted host file API
cannot prove that model tools enforce a permission profile.

`native-probe --workdir ... --parent-context ...` checks the pinned native Codex
runtime and selected profiles with synthetic local commands, without model
inference or creating a chat. its optional diagnostic receipt does not replace current ordinary startup checks.
It is not a prerequisite to ordinary schema2 execution. Keep the final root/profiles
unchanged when collecting optional qualification.

Native control state is keyed by host, canonical folder and sprint, with immutable
managing-chat ownership. Every mutation records pending state before its call.
Preserve unknown acknowledgement for reconciliation; never silently create another
chat, provider, fork or background copy. Backend persistence and client visibility
remain separate; a headless caller may record visibility pending.
Managing-chat ownership is immutable; transferring it requires an explicit
reviewed migration. The bundled commands do not implement automatic adoption.
Schema2 keeps small current control state and ordinary immutable per-operation
intent/ack/terminal receipts under the SAME guard/key/parent/chat. Public answers
live in one UTF-8 file per operation, referenced by path/byte count/SHA256; bounded
transient callback public/text returns remain compatible. Operation/turn/Claude
logical maps no longer grow in control state and have no 128/4096 lifetime caps.
Actual producer/read/disk bounds remain; JSON writers enforce the existing 2 MiB
reader bound. Preparing/sending/unknown reservations block replay, even after
crash, short write, ENOSPC or failed fsync. Failed control publication poisons the
current owner until release/reopen. No database/index/chunks/transaction service.

Legacy journals do not implicitly upgrade. An authorized offline controller may
call Journal.migrate_legacy with the exact approved source SHA256 and finite read
bound (default MAX_JSON), under original writer quiescence/exclusion. It preserves
old bytes, fences the old writer with schema2 lacking operations, and imports
ordinary receipts. Resume only the same pinned pending import. Completed imports
cannot overwrite newer state. Corrupt/partial or multiple-unresolved imports need
trusted reconciliation; never delete evidence/recreate the chat to recover.
Codex history verification follows at most 32 pages of 100 turns. Missing required
history, repeated cursors, malformed pages or this safety bound block continuation
for reconciliation; they never authorize another chat or a replay.

The Claude driver provides owned restricted-print text sessions with exact UUID
resume and foreground lifetime. It does not provide file/shell tools, background
survival or live steering. Codex uses its qualified native protocol and permissions;
shared daemon and owned process ownership are different. Never stop a shared daemon.

Metadata list/read operations expose bounded metadata, not conversation contents.
Legacy metadata creation is not sprint execution; it cannot satisfy the native
identity/persistence/brief gates above.

## Trusted evidence

Apply [assigned-task authority and approval evidence](routing.md#equal-authority-within-the-assigned-task) before dispatch: reuse applicable standing/scoped consent, present the actual provider/task/package/categories and trusted grant to the host reviewer, and bind required exact records without inventing a new human-consent requirement. This does not expand provider scope, grant tools or override an actual denial.

Ordinary authorization schema_version=1 contains source={kind:human_instruction,
reference,text} and authorizations. Each record binds an absolute workdir.
External records bind assignment_id, providers and task_scope; top records bind
exact assignment_id, role and profile. Preserve the original human quotation.

Native authorization records use kind=native-sprint with workdir, sprint_id,
parent_chat_id, profile, provider, brief_sha256, operation and operation_id.
Consent must cover the exact request. Store evidence outside task-writable roots.
For a top-tier native profile, a separate ordinary kind=top record must use role
main_external and the native assignment ID emitted by missing_authorization.
That ID is `native-` followed by SHA256 of the UTF-8 canonical JSON object with
keys workdir, sprint_id, parent_chat_id, operation, operation_id and profile.
workdir is the absolute canonical folder path. Serialization sorts keys, keeps
Unicode unescaped, rejects non-finite numbers and uses separators `,` and `:`
without spaces. This binds consent to one exact sprint operation; another sprint,
brief operation or profile cannot reuse it.
Evidence records are not grants; the caller establishes the trusted source, and
the real host's approval system still decides. Changed settings/evidence/pins block
the next mutation. No automatic runtime download, pin upgrade, secret discovery,
provider fallback, benchmark or global model change is part of doctor/setup.

## Explicit text uncertainty commands

`uncertainty-status` observes a protected schema1 text receipt without inference.
Supply `--source-id`, `--workdir`, `--task-sha256`, explicit `--role external|reviewer`
and `--stage`, preserved `--author-profile`, `--author-invocation` and optional
`--allowed-provider` restrictions, plus exactly one real `--parent-permissions`
or neutral `--protection-context`. The first observation freezes these legacy
scope assertions, config and caller identities in `<root-id>.uncertainty.json`
beside existing receipts. It does not rewrite the original receipt. An abandoned
`prepared`/`launch_started` receipt requires `--outcome-uncertain` on that exact
source ID; known running work never expires merely because it is unfinished.

The UTC wait is 900 seconds from the first coordinator uncertainty observation,
explicitly identified as such when no transport event time exists. Polls and
restart do not reset it. Status reports `waiting`, `eligible`, `resolved`, `busy`,
`exhausted` or `needs_reconciliation`. Invalid/regressing/future clock state,
changed source identity, config, task, caller or scope blocks for trusted operator
reconciliation and preserves evidence. A forward wall-clock jump cannot be
detected reliably; expiry does not prove remote termination or nonacceptance.

`uncertainty-continue` adds NEW `--assignment-id` and `--invocation-id`, ordinary
dispatch arguments (`--profile`, `--prompt`, `--output-dir`,
`--authorization-file`, applicable `--external-blocker` evidence), and explicit
`--purpose analysis|review`. It permits only `external` analysis or independent
`reviewer` text with no tools/effects; it requires exact child-scoped authorization
and preserves review stage, actual authors, task/provider restrictions, top
consent and actual host approval. Desktop/native/adapters require their qualified
host instead; this command never executes them or changes the selected model.

Full ordinary text preflight runs before durable child intent. A stable kernel
lock protects local chain mutation and is released before network I/O. Intent
survives crashes and is never replayed: reconcile the exact receipt/result. An
intent without a receipt starts its own 900-second ambiguity wait on observation.
An observed prepared child needs its own explicit lost-outcome assertion.
Child-as-root and profile aliases cannot reset the finite chain: each distinct
configured provider/model tuple, including the original, is used at most once.
An eligible reserve still needs all ordinary blockers and host capability.

Late results are inspected only through frozen protected paths and matching
identity/hash. A completion resolves the chain and awaits ordinary independent
intake; another alternative cannot be launched to shop for a preferred verdict.
Possible overlapping inference/cost remains within the authorized read-only
policy. Covered native local continuation/integration follows the default policy in
[operations](operations.md) through a separate compatible native assignment; this
text CLI does not implement it. Uncertain external effects and non-covered writes
retain their ownership/quiescence rules.
