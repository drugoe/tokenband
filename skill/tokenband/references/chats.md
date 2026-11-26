# Managing chats and task chats

A project may have several authorized managing chats for distinct recorded
management scopes, and one manager may own several sprints or directions.
Record each manager's exact ID, scope, assigned tasks and integration authority
in the existing sole TODO/evidence. Do not create a per-manager queue or require
a Director, a new registry or a manager for every sprint. A scope may be a sprint,
a disjoint group of tasks within a sprint, standalone tasks or a named direction;
its authority and boundaries must be established, not invented. Each task and
conflicting write/integration scope has one responsible owner. Preserve existing
shared-file owners, serialize shared TODO/number reservations and integrations
through their authorized update path, and reconcile the current base before
writing; several managers do not authorize concurrent overwrites. Very small simple tasks are performed directly by the manager; any change in the behavior of the application, project, skill or process requires a dedicated persistent task chat, even for a one-line or allegedly easy change, and other substantive work also uses a task chat. Apply [one task, one persistent chat](#one-task-one-persistent-chat) to distinguish a new task from its supporting substeps. A sprint is a plan/group of tasks in the sole TODO, not a chat: the manager divides it into logical stages by outcome and dependencies, and every substantive task in a stage gets its own dedicated persistent chat, so no aggregate sprint or stage execution chat exists. There is no one-chat-per-sprint, no shared sprint chat and no hidden hub or TODO parser/controller; stage order, the documented concurrency exception and task-chat titles follow [task chats inside a sprint](#task-chats-inside-a-sprint). Preserve existing
running work, ownership and pauses; inspect the folder and known chats first.

The session host, persistent coordination chat model and external executor model
are separate. Start new standalone coordination, manager and task chats on the
configured internal ordinary-primary identity. TokenBand does not create external
coordination chats. Use an eligible external executor or reviewer for the bounded
assignment under [routing](routing.md), with its own invocation and controls.

This chat-model default does not disable budget-saving external execution:
external executor, API and file-adapter assignments still follow [routing](routing.md),
with their own model binding, consent, capability and independent gates. Resolve
the chat choice from trusted current human settings using existing fields; no new
required setting/schema or global/account default change is introduced. Apply the
default only to new chats; preserve existing exact IDs and frozen provider/model/
effort, including historical external chats and the current managing owner.

Explicitly select and confirm the intended chat identity through a supported
host route. A requested or inherited model identity alone, stateless text request,
empty metadata draft or proposed configuration does not establish an executing
task chat. If the selected identity cannot run on a permitted supported route,
report the concrete capability or authorization blocker under
[requested-chat outcome](#requested-chat-outcome); do not silently substitute an
external model or weaken actual controls.

Use the [assignment fields](../assets/assignment-template.md) once, binding the
actual task and managing-chat IDs. [Communication](communication.md) governs
internal/human language; independent task scopes may proceed with disjoint ownership.

Use the configured host driver and its real protocol: [Codex native
sessions](host-codex.md) or [Claude native sessions](host-claude.md). For Kimi Code,
read [skill discovery and the native boundary](host-kimi.md); there is no bundled
Kimi-native driver. Other native routes need an implemented, qualified driver.
A manager in one framework may invoke
another host's qualified driver; this does not make their APIs interchangeable.
Check persistence, tools, exact-session continuation, permissions and execution
lifetime separately. Runtime presence and requested model flags are insufficient.

Before creation, save a protected pending record keyed by host, canonical folder
and task. Bind the managing-chat ID as an attribute; a changed manager must
reconcile ownership rather than allocate another chat. Keep authoritative control
state under the actual context control mode in [qualification](qualification.md#actual-context-and-control-integrity); a folder copy is a readable
mirror, never authority. Bind the native ID after acknowledgement. Unknown
acknowledgement or a crash never triggers automatic recreation. Changing output
path or resuming the manager does not authorize duplicate work. Technical receipts
do not replace TODO task status or ownership.

When the manager creates a task chat, begin its first visible message with a
short task description in the human's language: the task's display number/title,
what must be done and the expected result, drawn from the existing TODO scope.
The task chat's first public reply must also state that description before any
technical readiness marker; a bare READY is insufficient. In a readiness-only
initializer this is descriptive text, not permission to use tools or start work.
Preserve the host's identity, exact-marker and persistence checks; include the
expected description and marker in the initializer's known public response.
If a supported host fixes an initializer that cannot carry this text, record
that precise limitation and put the description in the first permitted visible
message; do not claim first-message compliance. Do not recreate an existing chat
or rewrite its history to retrofit an introduction.

Confirm native identity and persistence before sending the substantive brief.
Record each accepted turn and its expected ID. Continue the exact same chat;
steering delivery is not a model response. Do not automatically fork, copy,
change providers or start a competing turn to recover an uncertain outcome.
Respect native permission requests and the actual parent boundary. Missing
approval capabilities remain blocked; no permissive answers are synthesized.

## One task, one persistent chat

One substantive task has one persistent task chat. Review, recheck, reassessment,
supporting analysis and fixes for that same task are substeps of the existing
task, not standalone tasks or additional task execution units. Perform supporting
assignments through agents within the originating task chat, using a genuinely
supported in-chat or stateless mechanism. A separate independent agent session
does not mean a separate persistent project/UI chat. Do not create separate
persistent chats or standalone tasks for these substeps. Return their reports,
decisions and findings to the originating task chat and bind them to the same
sole-TODO item and evidence; no second queue is created. A genuinely different
substantive task gets its own persistent chat.

Use [routing and review gates](routing.md#review-gates) for actual independence,
fresh reviewer briefs without the author conversation, roles and consent. Every
supporting assignment still passes [EVERY-send admission](lifecycle.md#allocate-and-reserve-before-dispatch)
in that same TODO item and preserves its applicable frozen execution/state
bindings, including WORKFLOW_HOME/--config where used, and actual host controls.

Do not assume every host supports the needed agent mechanism. Use only a
supported, authorized in-chat or stateless route; if unavailable, record the
concrete missing capability for the affected step in the same TODO/evidence.
Do not invent or skip mandatory review, create a separate persistent review chat
as a workaround, or introduce a new permission flow merely because a mechanism
is missing. The unmet gate blocks acceptance and its dependent actions; continue
other useful authorized work.

Continuations and corrections reuse the exact task chat. The sole recovery
exception is the permitted linked internal replacement of a known-stopped
external task chat under [lifecycle](lifecycle.md#continuing-a-stopped-external-task-chat),
for the same task without competing writes or replay of unknown work. Preserve
existing allocated, running and unknown-owner chats, operations, ownership and
pauses; do not delete or archive existing chats or retrofit their allocation.

## Task chats inside a sprint

A sprint is a plan of logical stages recorded in the sole TODO; the stage
structure itself creates no chat. Inside each stage the manager creates a
separate persistent task chat FOR EACH substantive task, and no aggregate
sprint or stage execution chat exists. The very small simple manager-direct
exception stays available, with its no-chat rationale recorded in the TODO.

Stages execute in order by default: a later stage starts only after the
previous stage is accepted-complete under the normal gates. Exception: the
manager may run several stages concurrently when the sprint has few stages
and each stage has few tasks, with the current rationale documented in the
TODO, independent accepted dependencies and disjoint ownership/write-sets.
This remains a judgment call, not an invented numeric threshold, and there is
no broad all-stages parallel exception. Inside one stage, tasks with
independent scopes and disjoint ownership/write-sets may run concurrently;
conflicting tasks are serialized under
[lifecycle](lifecycle.md#allocate-and-reserve-before-dispatch).

Each task title includes its sprint code and sprint/task number, for
example `🟡 8.13 / AUS — API` and `🟡 8.14 / AUS — Tests` for queued tasks.
Use the canonical formats under [managing titles and intake](#managing-titles-and-intake).
Keep the stage in the sole TODO and opening task description, not in the title;
stage execution order is unchanged. The manager title remains reserved for
authorized managing chats for their recorded scopes; a task title grants no managing role.

Task boundaries, supporting substeps, continuation and preservation of existing
chats follow [one task, one persistent chat](#one-task-one-persistent-chat).

## Project and folder binding

All necessary working folders for a project, including sprint, task and Git
worktree folders, belong to ONE existing project,
never separate projects. When the manager creates additional folders for a
sprint, a task or a git worktree, every new chat and folder stays bound to the
current project identity so the interface does not show several projects for
one piece of work. This rule creates no new project, queue, registry or
setting, and it changes no role, permission, task status or ownership.

Keep four things distinct: the original project identity (`projectId` on
supporting Codex hosts), the
canonical project root (the project's main folder), the new chat's `cwd`, and
the actual task or worktree directory where the work happens. A different
working directory never implies a different project, and neither a similar
folder name nor a lookalike Git remote identifies a project.

New working folders the manager creates — for a task, a sprint or a git
worktree — are proper descendants of the canonical project root: inside that
root, never beside it. Before use, resolve the intended path and confirm that
the resolved location is strictly under the canonical project root. A sibling
of the root, a lookalike path that merely shares the root's prefix, an absolute
path outside the root and any `../` escape are rejected, and a symlink whose
resolved target leaves the root counts as outside.

If a selected supported host or worktree operation requires a path outside the
root, do not create or use it silently: use the supported inside variant, or
record the concrete limitation in the existing TODO/evidence and stop only that
outside-folder operation; continue other authorized work.

This placement rule governs newly created project working folders only; it
migrates nothing. Existing folders, roots, live owners and unknown receipts
stay as they are, and protected host state or credential stores are not
project working folders and are never migrated.

Resolve the host's project identity only from a verified current binding — trusted thread
metadata/readback or a client-visible project reached through a supported
operation — and only through a mechanism the selected host actually supports.
An unverified or unknown binding stays omitted and is recorded as pending in
the existing TODO/evidence; never guess an ID from a name, a lookalike Git
remote or an unrelated Desktop UUID. Reuse an existing verified binding for the
same project; a title or folder match alone is insufficient. Correct a known
mapping/read rejection before creation; a generic creation failure or unknown
ACK never authorizes replay.

Include every necessary working folder, whether newly created or reused, in
the existing project's supported folder/root association; preserve its other
existing roots. A shared chat project ID alone does not bind additional folders.

The Codex host surfaces and their observed limits are in
[host-codex](host-codex.md#project-and-folder-binding-on-the-codex-host):
starting a thread with `projectId` and `cwd`, assigning an existing project ID
to an existing thread, and setting an existing project's roots. When the
selected mechanism cannot express explicit grouping, use the conservative
fallback: keep the canonical project root as the new chat's `cwd` and state the
actual task/worktree directory explicitly in the brief, the command `workdir`
and absolute paths, without writing into the main checkout by accident. The
fallback is a permitted operating variant, not an attested GUI outcome.

`cwd`, backend persistence and pins are not evidence of UI grouping or project
membership; GUI visibility and project grouping stay separate observations
confirmed with the human. This rule cannot be fully confirmed on every host:
record the concrete residual limit — unverified binding, unsupported route,
unavailable GUI check — in the existing TODO/evidence instead of silently
weakening the requirement or promising all platforms. Apply the existing
[reservation/ACK/unknown checks](lifecycle.md#allocate-and-reserve-before-dispatch)
before any binding-related creation or send; binding adds no duplicate queue.

## Requested-chat outcome

A request to create a managing or task chat is an end-to-end outcome, including
supported-route discovery and completion of setup already covered by that request
and standing grants. Do not stop at an empty template, successful text API call,
READY, setup plan or absence of a dedicated chat-creation tool. Use existing
[setup](setup.md#complete-selected-chat-setup) and the selected host guidance.
This adds no permission, capability or exception to independent/native gates.

Resolve the requested role, model/effort, folder and persistence from the human
and trusted current settings; ask only for genuinely missing material choices.
Check that the request is for an internal coordination chat before preparing creation.
An external execution role does not choose the chat model. Preserve the assigned scope's
current managing owner until an explicit verified handoff. Creation alone does
not transfer TODO ownership.

Inspect available native creation tools AND the documented supported server/host
route when shell or another authorized local channel is available. Follow the
actual host/version; an absent direct tool says nothing about an uninspected
server route. If local inspection itself is unavailable, name that exact missing
access and mark server capability unknown, not absent. Do not write a new driver,
start another daemon or infer unsupported protocols to avoid a real limitation.

Distinguish role settings, a stateless text connection, a registered native
provider and a qualified tool driver. Reuse known endpoint/model/credential
references; a text-only declaration neither supplies native readiness nor proves
native creation impossible. Complete supported task-scoped setup within existing
authority, including repair of an unsuitable task-local execution profile under
[setup](setup.md#selected-native-session-setup), and continue this SAME request without a redundant human start. For a
necessary ungranted change, first prepare its exact scope/settings and explain
why it is needed; ask only for that decision or missing datum, never key values.
Do not change global/default settings, active sessions or actual controls.

Before creation retain lifecycle's reservation and protected intent. Save ACK IDs
before later calls, finish the initializer and verify reconnect/persistence.
Report exact requested/observed identity, real completion and client visibility
separately. No serving-model or tool-qualification claim follows from metadata,
READY or GUI. A previous unknown creation/turn blocks duplicate sends.

A blocked result must identify the last actual check, the specific unmet
prerequisite or denial, what remains unknown, and the prepared smallest next
setup action. "No chat tool" or "only text API configured" alone is not that
result when the supported host path has not been inspected. A verified lack of
access/protocol/transport or an actual denial is a valid boundary: do not promise
success everywhere, cycle providers or weaken permissions to remove it.

## Existing-session configuration

All bundled native commands currently preflight the selected configuration's main_external role and mode before reading the sprint journal. Retain the sprint's reviewed selected profile/model/effort, driver/runtime, context, environment and resolved binding. Primary-only mode blocks these native commands, including status/reconcile. Use a protected execution configuration with --config from creation through management; stage future role choices in a separate reviewed configuration instead of changing the old session's selected profile.

This bundled-command constraint is not the ordinary chat-model default above and
does not establish that a distinct supported authorized host route is unavailable.
If no permitted route supports the selected internal chat identity, retain that
concrete blocker; the new default changes no driver capability or mode check.

Keeping the original configuration path is the conservative operating procedure. A copied file alone does not establish binding equivalence, especially for @config references; an alternate configuration route needs independently reviewed binding equivalence and current authorization. The worker freezes config bytes within an operation, while cross-operation checks compare the stored execution binding, not the whole previous file hash/path. It does not automatically snapshot, adopt or migrate configurations.

Ordinary Codex schema-2 work continues its exact original chat with authorized sprint-send under the current selected execution binding, actual permissions, idle/history and unresolved-operation checks. It does not require historical qualification evidence or a synthetic bootstrap. Diagnostic journals retain their original owner and evidence and remain separate; do not promote a diagnostic chat or its qualification pins into ordinary sprint-send. For lost or changed execution configuration, use only an authorized independently reviewed restoration/equivalence route; otherwise retain the blocker. Do not erase the journal, replay an accepted or unknown operation, create a replacement chat or select a new default model as recovery. Current human/provider/mode restrictions govern every operation: old settings never override a new prohibition or grant access. No automatic multi-profile lifecycle migration is implemented.

## Client and headless operation

Record backend persistence and client visibility independently. For authorized
server CLI work, verify native read after reconnect and supported discovery;
continue with backend persistence confirmed and client visibility pending if no
client is available. Verify the exact ID and intended folder/project/host in the
client when it connects. Native metadata alone never confirms UI visibility.
The absence of a GUI does not require a duplicate chat or prevent headless work.

An owned foreground launcher must remain alive while its turn runs. A qualified
native supervisor/shared daemon may retain accepted work after the caller exits.
Advertise only the lifetime actually supported. Close your own connection and
clean up only owned processes; never stop a shared daemon or another assignment.

Creation and management stay within explicit human-authorized coordination.
This workflow gives no permission for unrelated chats, schedules, publication
or messages to other people. Use each client tool's actual creation/registration
requirements when choosing that route, and verify it honors the selected model.

## Shared-host creation and exact-chat delivery

When the selected host supports the actual shared route, use the existing native
transport and RPC from the installed skill as described in
[Codex shared-daemon operations](host-codex.md#existing-shared-daemon-route).
This method describes observed host operations and existing controls; it creates
no new worker, driver contract, script, queue, database or control framework.
Prefer available native client tools when they support the selected chat
identity and actual controls. Check the supported server route before asking the
human to relay text.

Keep the selected chat identity separate from the external MAIN executor's binding.
Provider/model/effort select the authorized binding on the same supported host;
they do not require another daemon. For executor routing, a scoped temporary
ordinary-primary grant covers only its assignment, without changing external roles,
defaults, consent or review independence under [routing](routing.md). A source-side failure concerns
that route/request, not general provider incapability. Creation/short text does
not qualify tools or attest the serving model/effort.

Apply [EVERY-send admission](lifecycle.md#allocate-and-reserve-before-dispatch)
before shared-route dispatch. Client close does not justify another chat/worker.
Disjoint preparation can proceed; dependent implementation needs accepted interfaces.

For a new authorized internal coordination chat, retain protected creation intent and save the native
acknowledged ID before naming or any later call. Complete the no-tools initializer,
verify persistence after reconnect, and confirm GUI visibility separately with
the human. For an existing exact chat, reconcile before delivering a newly
authorized message. After client close, `notLoaded` may require `thread/resume`
on that SAME ID followed by `turn/start` on the SAME connection. Preserve the
frozen provider/model/effort and apply current authorized task controls; do not
restore a legacy restricted initializer profile for substantive work. Native tools
still require their separate qualification and actual approval bridge.

Unknown acknowledgement remains unknown and must never be replayed. A later
explicit human command can authorize a new, separately identified follow-up to
the same chat after reconciliation; retain the original intent/outcome and do
not present the follow-up as a retry or resolution of that unknown request.
For an active turn, use supported steering with its expected turn ID. Deliberate
`turn/start` steering of an active chat is permitted only for the exact host's
supported, qualified semantics; availability in a schema is insufficient.

Minimal human command (any human language; English shown only as one neutral canonical example): “In this task's existing chat, add the method to the documentation candidate; do not repeat the old uncertain request.” Resolve
the exact native ID from trusted records; the natural-language command is not
a substitute for identity, ownership or authorization checks.

## Managing titles and intake

Before the first actual project workflow action, including a human-requested project task/discussion chat, run owner/title intake for the instruction's scope before applying any mechanical chat-create exception. Its completed outcome is confirmed manager identity/authority for that scope plus an actually applied canonical title; otherwise it remains truthfully incomplete with the concrete limitation or the one missing decision. Reuse the existing sole TODO/evidence and exact manager/scope/task bindings; do not create a second ownership registry. Resolve the project/folder, the scope, the current chat's role and known exact identities. Perform a bounded, project/cwd-scoped check of trusted current owner/adoption/handoff records and relevant project chats, including the selected host listing's actual filters and pagination limits; no whole-home hunt or exhaustive history is required. A missing owner record or manager title, unfiltered first pages, age, a different model or missing rollout does not establish that the scope is free. An uncalled rename proves neither a host capability failure nor absence of management.

- If trusted reconciliation establishes that the instruction's scope is free and the current chat is an eligible coordinating chat, adopt management of that scope in the same chat, record its exact owner ID and scope in the existing TODO/evidence, and self-rename as below before its first management assignment. This ordinary trusted free-scope first adoption is automatic and requires no manual preassignment or additional generic start question. Another manager for a confirmed disjoint scope neither blocks adoption nor forces succession. A known worker does not self-promote. Creating another manager for an occupied scope requires an authorized division or the existing scoped succession rules, not a duplicate owner.
- If a manager for the scope is confirmed, preserve that exact owner. If its title needs updating, that manager must self-rename its own exact ID on continuation; a different requesting chat uses the existing authorized handoff/delivery path, without renaming another owner's ID or claiming an unperformed update. Do not silently drop the title step merely because ownership is already known. An explicit project-wide managing appointment remains valid for its full scope until an authorized division or transfer; permission for several managers alone does not perform that division.
- If an owner candidate for possibly overlapping scope remains unresolved, preserve UNKNOWN and perform the available bounded project/cwd reconciliation before asking the user only the single missing decision. Distinguish a historical task-local “current managing chat” or task-owner mention from an explicit project-wide managing appointment. A task-local role alone is not a current project-manager claim. An explicit human appointment or other trusted ownership evidence still matters even without a dedicated TODO owner field; resolve its actual scope and status rather than discarding it for lacking a formal binding. Absence of evidence is not permission for takeover. Do not arbitrarily narrow an unknown owner to manufacture a free scope. Independently authorized work with established disjoint scope may continue; a genuine uncertainty blocks only the possibly conflicting assignment. A requested discussion chat may proceed under its own existing admission/creation rules without an invented manager binding. Its human-visible result must report actual creation/ID/visibility separately, unresolved manager status, the concrete found limitation or one missing decision, and that manager intake remains incomplete. A separately completed creation may retain its own result, but is not completion of manager appearance. A pending note only in TODO/evidence is insufficient: before ending the turn, perform the available narrow check or ask the genuinely missing ownership decision directly in the human's language. Do not add a generic “start?” confirmation to already authorized adoption/self-rename.

Keep three separate outcomes: confirmed manager identity/authority, title ACK/readback, and GUI visibility. A pending or unknown title/rename is an incomplete title operation, not a missing owner, and it does not revoke a confirmed owner; retain the existing identity/rename limitation and unknown/non-replay rules below. A real denial, missing capability or unresolved owner keeps first-use incomplete and must be reported as that blocker; successful independent chat creation does not mask it. An unavailable hourly-check mechanism does not block intake or independently authorized work. Honor an explicit human no-manager exception only within its stated scope. Greetings, ordinary factual conversation and installation/discovery alone do not activate management. Stop remains immediate. This intake changes no model, permission or global setting and bypasses none of the existing succession, quiescence, reservation or current-control requirements.

On first activation for a trusted free management scope, the current eligible coordinating chat adopting the workflow becomes that scope's manager. Record that adoption, exact owner and scope in the project's sole existing TODO/evidence and keep using that same current chat. When a chat legitimately adopts active management, or on continuation recognizes that it is an active manager for its recorded scope (not a historical inactive chat), it MUST rename ITSELF through the host's supported exact-rename operation to the canonical manager title below, without waiting for a separate human rename request. A new manager does this after verified scope adoption or transfer and before its first management assignment; a standby or unconfirmed successor must not present itself as the active manager. For an existing manager starting a sprint, first record the sprint as active in the sole TODO, then update its own title before creating or assigning that sprint's first task. Refresh the title after verified completion, cancellation or other active-set changes; on continuation reconcile it with the current TODO. Keep the descriptive suffix in the human's language, replace the old leading role icon/prefix rather than stacking it, and treat an already-correct title as a no-op. Verify ACK/readback where available. Preserve identity, project/history and ownership. An existing manager retains its recorded scope unless an authorized division or explicit verified transfer changes that scope. A standalone greeting or ordinary conversation is not workflow activation, and skill installation or discovery alone executes nothing, does not take over a global/account first chat, and grants no new chat, model, default or permission merely for adoption. If native identity or rename is unavailable, keep it unknown/pending with the concrete supported-route finding and continue only independent authorized preparation; never claim a fake title, visibility or owner.

Use `🧭 <sprint> / MANAGER — <sprint description>` for one active sprint, for example `🧭 8 / MANAGER — Авторизация`. With several active sprints use one title, for example `🧭 8,9 / MANAGER — Вход и оплата`: list all of this manager's current active sprint numbers in numeric ascending order, separated by commas, then a slash, the uppercase literal `MANAGER`, a dash and a common description. Do not include sprint codes in a manager title. Draw only this manager's active sprint set from the sole TODO, not another manager's sprints or the historical plan; remove completed or cancelled sprints from the title while retaining their records. Unknown active state requires reconciliation, not an invented empty set. Standalone tasks never add `0` to a manager title, whether alone, several at once or alongside real sprints. If no real sprint is active in this manager's scope, use `🧭 MANAGER — <scope description>` without a number or slash, even when standalone tasks are active. When real sprints are active, show only their numbers; for example `🧭 2,8 / MANAGER — Текущая работа`. Sort numerically rather than lexically (for example `2,8,13`). A real legacy sprint labelled `00` remains visible as that exact string: it is distinct from the hidden standalone `0`, and is never normalized or removed by this display rule.

Each authorized manager uses a manager title for its own recorded scope. Several managers may coexist; this does not require an extra manager for every sprint or task. One manager may handle several sprints, and different managers may handle explicitly disjoint task groups within one sprint. Use the description to distinguish their scopes. Rename only its own known exact ID through the supported operation. A title grants no role or permission. If the full title exceeds a host limit, shorten the common description while preserving all active sprint numbers; if it still cannot be applied, record the concrete host limitation and do not claim an unapplied title. Unknown rename outcome requires reconciliation, never recreation or blind resend. Apply lifecycle's [reservation/ACK/unknown checks](lifecycle.md#allocate-and-reserve-before-dispatch).

At creation/adoption of an active manager that controls project tasks, arrange
its [hourly manager recovery check](lifecycle.md#hourly-manager-recovery-check).
That section owns setup, unavailable-host handling, continuation and handoff;
an inactive chat receives no schedule.

A newly created task chat uses `🟡` for its queued or reserved start. Title each sprint task chat `<state icon> <sprint>.<task> / <CODE> — <task description>`, for example `🟡 8.13 / AUS — Восстановление пароля`. Put the dot-separated number first, then a slash, the sprint code (at most five characters, uppercase), a dash and the description in the human's language. Do not append a role word to the code. Outside any sprint show only the task number: `<state icon> <task> / <task description>`, for example `🟡 13 / Обновить справку API`. Hide the leading `0.` in the title; after the slash comes only the description, with no code, `TASK`, placeholder or extra dash. Retain the existing `0.<task>` accounting number and its mapping in the sole TODO and receipts; this is a display change, not renumbering. Keep the sprint stage in the sole TODO and opening task description, not in the title; stage execution order remains unchanged. Manager and task-coordinator roles remain unchanged.

Sprint numbers are positive integers in one namespace across the whole project, not per manager, chat or stage. Honor an explicitly human-selected unused number; otherwise allocate one above the highest ever allocated sprint number (start at 1). Gaps are allowed; numbers do not determine execution order or override dependencies. Task numbers are positive integers within each sprint, continuing across its stages; allocate one above that sprint's highest ever allocated task number (start at 1). Outside any sprint, retain `0.<task>` as the accounting number in the sole TODO and receipts, while the chat title displays only `<task>`, for example `🟡 13 / Update API reference` for accounting number `0.13`. The accounting `0` means outside a sprint and creates no sprint or chat group; these tasks have their own project-wide task sequence starting at 1. A genuine one-task sprint keeps a positive sprint number, for example `9.1`.

Each sprint also has one meaningful uppercase code of at most five characters: a word or abbreviation for the sprint goal in the human's language, not a random generator. Assign it in the existing TODO when the sprint is planned, before the first chat for that sprint is created. Check codes already used by this project in the existing TODO/evidence, including case-insensitive collisions, and take an unused code without the title delimiters comma, dot or slash; do not create a new registry or canonical ID. Preserve an explicitly human-selected code unless it conflicts with an existing code. Outside-sprint work has no sprint code. If a legacy sprint has no code, assign one once before its first new chat; do not bulk-rename old history. After use, the code is stable; changing it requires an explicit decision, agreed old-to-new mapping and a known owned rename. When an explicitly authorized format change shortens an existing longer code, choose a unique code within the five-character limit and record the mapping before using it; do not blindly truncate into collisions or rewrite historical records.

Before creating a task chat, the manager responsible for that task reserves its number and mapping to the existing task ID in the sole TODO through the established serialized shared-write path; after ACK, attach the exact returned chat ID to that same reservation. Allocation stays project-wide, not per manager or scope; reconcile shared reservations before assigning, without racing independent read-max/write-new updates. Reconcile current and retained historical allocations before assigning a number; unknown or conflicting allocations block only the affected allocation. Preserve existing numbers, task/native IDs and history. Never reuse cancelled or archived numbers or reset sequences on stage changes or manager handoff. If a legacy project already uses real sprint 0, obtain an explicit human relabeling decision before reserving `0` for standalone tasks. A human-selected legacy label such as `00` is distinct from `0`: preserve it as an exact string in the TODO, titles and comparisons, never normalize it to integer zero. For example, `00.1` is task 1 of that legacy sprint and remains visible in its title; standalone accounting number `0.1` is shown as `1` in its chat title. Record the old-to-new display mapping while preserving original task/sprint IDs and receipts. Resolve other incompatible legacy numbering explicitly; do not silently renumber it. No second registry, mass migration of historical/foreign/unknown-owner chats or duplicate task is authorized.

For an authorized title update, rename only the exact known owned task chat through its supported operation and verify ACK/readback where available. An already-correct title is a no-op; replace the old leading role icon/prefix rather than stacking it. Preserve the meaningful task/outcome suffix. Apply lifecycle's reservation/ACK/unknown checks: an unknown outcome requires reconciliation, not recreation or blind resend. Renaming alone changes no sprint membership, role, permission, task status, ownership, dependencies or work state.

For a task-title change under [engineering and acceptance](lifecycle.md#engineering-and-acceptance), the owning manager replaces only the leading state icon. Preserve every character after the leading icon, including the displayed task number, any sprint code, and the description. Preserve the exact task chat ID from the sole TODO. Read the exact title first and treat an already-correct title as a no-op. Require a recognized leading state icon before attempting a change. Recognize a legacy leading `✓` (U+2713) only during a legitimate transition for that exact owned chat. Do not sweep or bulk-update old titles. Use the supported exact title operation for that chat ID (`set_thread_title` on Codex Desktop where available, or the existing supported host-native operation), and verify the ACK and exact title readback for the same ID wherever supported. Reconcile an uncertain prior rename against that exact ID before any further title mutation. Never recreate the chat or blindly retry a rename with an uncertain effect.

For ordinary Codex schema2 use [ordinary execution](qualification.md#ordinary-codex-schema2-execution):
no historical qualification/bootstrap before create/send, no adoption of diagnostic
journals and no resume with an unresolved intent. Other host contracts remain.

Native persistence is not tool-free transport. Behavioral no-tools instruction,
observed absence of tool items on a checked turn, actual catalog suppression and
a qualified tools route are separate claims. Read-only can allow reads and deny
writes; it does not disable tools. Keep initializer observations within their
scope; reconcile unexpected use under [operations](operations.md).

## Manager succession and handoff

First adoption does not allocate a backup chat. On an explicit authorized succession,
use an eligible existing internal chat or complete [internal chat setup](setup.md#complete-selected-chat-setup)
for one separately bound successor; keep the original project, sole TODO and
evidence. An existing historical reserve retains its ID, binding and receipts.
Its inactive title establishes no ownership; preserve unknown earlier operations
and do not recreate it. Before the successor adopts, preserve protected intent,
exact ACK and persistence for any new internal chat.

Taking over an occupied scope requires an explicit authorized, verified handoff
of that scope's management, recorded in the existing TODO/evidence with the exact
old and new managing-chat IDs and transferred scope. A human-authorized division
must likewise establish each resulting scope and owner before conflicting action.
Before the new manager acts, reconcile that scope's current TODO ownership,
dependencies, pauses/Stop and unfinished or unknown operations and receipts.
Establish that the old manager can no longer issue conflicting management writes
or dispatches for the transferred scope under [operations' quiescence or
enforceable exclusion boundary](operations.md); silence, a stopped model or a
handoff note alone is insufficient. Preserve task write-owners and their
operations; management handoff does not transfer unknown task write ownership
or authorize replay. The old manager retains its other scopes; only the named
scope transfers, including on any later handback. After verified transfer the
new manager self-renames and the old manager reconciles its remaining scope/title
on continuation; titles alone never establish or transfer ownership.

Before the successor schedule acts for the transferred scope, reconcile the
former manager's future and queued/accepted callbacks for that scope and establish
quiescence or enforceable exclusion under [hourly manager recovery](lifecycle.md#hourly-manager-recovery-check).
Each verified active manager may arrange at most one supported same-chat schedule
covering its current recorded scopes, not one per scope. A manager retaining other
scopes may continue their checks after excluding the transferred scope and
reconciling conflicting callbacks; do not inherit or retarget old callbacks.
An inactive chat has no schedule, automatic takeover or separate task queue.
