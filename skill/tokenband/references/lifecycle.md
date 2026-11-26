# Folder-owned tasks, development and restart

A working folder is the accounting unit. Additional sprint, task or worktree folders are working directories of the same project, created inside the canonical project root, and create no separate project; binding follows [chats](chats.md#project-and-folder-binding). Reuse its queue, plans/sprints, index, evidence and IDs. TODO alone records task result, risk, scope, dependencies, owner/write-set, base/version, status, acceptance and evidence. Plans explain goals/dependencies; indexes aid navigation; operation receipts identify execution. None is a second task queue. Do not create per-chat/host/worker TODO lists.

Before work, compare current dependencies, ownership and input versions. Preserve active owners, pauses and concurrent changes. Accepted human decisions differ from assumptions/proposals. Dependents wait for accepted predecessor evidence: waiting, blocked, execution-complete and accepted-complete have different meanings. Disjoint independent scopes may proceed concurrently.

## Bounded execution

Choose coordination by ambiguity, aggregate risk, dependencies and verifiable outcomes. Basic lookups and mechanical corrections need no team. For a new task the executor first prepares solution options per [advice before execution](../SKILL.md#advice-before-execution). Choose the execution format from the ready TODO scope, size, duration, dependencies, parallel ownership and risk; there is no universal numeric threshold. Very small simple tasks are performed directly by the manager with the rationale recorded in the sole TODO. Any change in the behavior of the application, project, skill or process requires a dedicated persistent task chat, even for a one-line or allegedly easy change; one standalone substantive task uses one persistent chat and related continuations/corrections of the same scope reuse its exact ID. A larger multi-task package forms a sprint: the manager divides it into logical stages by outcome and dependencies, and every substantive task in a stage gets its own persistent chat, so no aggregate sprint or stage execution chat exists; the sprint itself remains a plan/group in the sole TODO, with no one-chat-per-sprint and no shared sprint chat. Stage order, the documented concurrency exception and task-chat titles follow [chats](chats.md#task-chats-inside-a-sprint). A large set of individually tiny mechanical edits is judged by aggregate scope and cannot stretch the direct exception into a program. Re-evaluate on scope growth or resume without restarting completed work or taking over unknown owners. Both formats use the same configured external roles, consent, EVERY-send reservation, independence/critical gates, accepted dependencies and non-replay. For task execution, the exact dedicated persistent task chat with the selected [chat identity](chats.md), current owner/initializer/persistence and substantive ACK are mandatory before claiming it is running or sending dependent work; a bounded helper or stateless executor is not a replacement. Batch coherent same-shape work; do not combine unrelated acceptance surfaces or split to evade a gate. Preserve cross-module understanding and integration ownership.

Task boundaries and supporting reviewer/helper substeps follow [one task, one persistent chat](chats.md#one-task-one-persistent-chat), including return to the same task chat/TODO, supported mechanisms and step-specific capability limits. This also qualifies the execution-format rules above; independent agent sessions do not allocate new tasks or persistent chats.

On upgrade, preserve existing active or unknown chats, scopes, owners and receipts. Finish/reconcile their already allocated work on its original binding; do not fork, redistribute live writes or recreate chats to retrofit the new format. At the next safe allocation boundary, map new task scopes to their distinct task chats in the existing TODO. A legacy chat is not permission to allocate all future tasks to one aggregate sprint or stage chat.

### Continuing a stopped external task chat

When an external task chat is known unavailable for its assignment — a known terminal provider/capability failure or a stopped route or model — the manager evaluates the permitted primary reserve for that assignment under [routing](routing.md), preserving any real action/permission denial rather than switching routes to evade it, and, when it is permitted, organizes one new separately linked internal task chat for the same task or its remaining scope. The continuation reuses the existing sole-TODO entry, owner/write-set and accepted dependencies rather than a second queue; it does not replay completed, accepted or unknown work, does not change the old chat's frozen provider or receipts, does not fork competing writes and does not take over another owner's live work. The new chat is a fresh execution unit with its own protected intent, ACK and persistence evidence, and the old-to-new link is recorded in the existing TODO; an unknown acknowledgement or crash still never triggers automatic recreation ([chats](chats.md)). Unknown outcome or missing cleanup uses operations' default covered local policy, not automatic recreation/resending of that original chat/operation. Preserve the observation, recovery and non-replay limits in [operations](operations.md). When the reserve is not permitted or is itself unavailable, record the concrete blocker in the same TODO entry and continue only disjoint authorized work; this continuation rule alone creates no daemon, timer, second queue or self-wakeup guarantee. The separately configured [hourly manager check](#hourly-manager-recovery-check) can initiate the permitted assessment; it does not make blocked work resume by itself.

Use applicable [assignment fields](../assets/assignment-template.md) once and [communication](communication.md) for actual accessible source inputs. Reconnaissance follows the template's source/relationship/freshness/unknown map; proposed checks are not executed checks. A scouting role alone grants no build/test authority; read-only reconnaissance expects zero write delta.

## Hourly manager recovery check

At creation/adoption of an active manager that controls project tasks, the
manager must arrange ONE built-in schedule returning to its OWN chat every
hour when the supported mechanism is available, within applicable human authority
and actual host controls. This is the
specific scheduling rule, not permission for unrelated automation. Use
[setup](setup.md#built-in-schedule-setup) and the selected host's actual built-in
mechanism ([Codex](host-codex.md#built-in-same-chat-hourly-manager-schedule)).
Reconcile any existing schedule or pending intent first; do not create one per
task, on a greeting/installation, or for an inactive chat. If the required
mechanism/access is unavailable, skip this automation setup, briefly record the
actual reason and continue authorized project work without waiting. Unavailable
automation is not a prerequisite or required pending follow-up for that work.
Do not substitute cron, a system scheduler or custom service. Existing unknown
operations and real task permission/ownership limits remain subject to
[operations](operations.md); skipping setup does not resolve or bypass them.

Before any scheduled action, verify this exact chat is still the active manager
for its recorded scopes and reconcile previous active/queued/unknown checks. A scheduled prompt
is not enduring authority for a former manager. Reporting findings and actions
uses the resolved human language in this same manager chat.

When the active manager has a verified built-in same-chat hourly schedule under
[host-codex](host-codex.md#built-in-same-chat-hourly-manager-schedule), each scheduled
turn is an ordinary manager turn, not a new dispatcher or second queue: it re-reads the
sole TODO and current ownership, then reviews unfinished task chats assigned to its recorded scopes, not another manager's tasks.
Unfinished is not the same as an abnormal stop. From trusted exact TODO/turn/results,
distinguish a task that is DONE, awaiting QA, in progress, waiting on an accepted
dependency, deliberately paused, or ended by an explicit Stop, from one whose
route/provider/connection actually failed. A prematurely ended turn without the required task result also needs diagnosis
and permitted continuation of the missing remainder; it is not accepted DONE.
Keep deliberate pauses/Stop, completed results and live write ownership intact.
The hourly cadence does not replace existing live progress/silence handling in
[operations](operations.md).

On a confirmed abnormal stop of an unfinished task, resume only within that task's same
scope and existing TODO entry: continue the SAME task chat when a supported route permits
it, apply a supported root-cause fix, or hand the remaining scope to an eligible internal
reserve under [continuing a stopped external task chat](#continuing-a-stopped-external-task-chat) and [routing](routing.md). This transfers the remaining task, not project management. Do not duplicate a write, widen policy or permission, replay completed/accepted/unknown work, or take over another owner's live work; preserve unknown effects, live write owners, quotas, denials and non-replay. A real blocker or a needed but un-issued authority is reported concretely here with the last actual check and smallest next action, without endless retry. A manager handoff is a separate operation under [manager succession and handoff](chats.md#manager-succession-and-handoff). On that handoff, pausing or deleting the schedule's future runs does not by itself prove an already queued or accepted callback is terminated; before the new manager's own schedule acts, establish quiescence or an enforceable exclusion and reconcile unknown owners under [operations](operations.md), so no two recovering managers issue conflicting actions for the transferred scope. A manager retaining other scopes continues only their permitted checks; one same-chat schedule covers its recorded scopes, not one schedule per scope.

Every scheduled send still passes [allocate and reserve before dispatch](#allocate-and-reserve-before-dispatch); a timer, plan or READY is not an executing turn, and a manual smoke check is not a timed run. The durable generic prompt below is the reusable instruction the schedule carries each hour; render and act on it in the resolved human language per [communication](communication.md).

```text
Use TokenBand's Hourly manager recovery check for this project. First verify that
this exact chat is still an active manager for its recorded scopes. Re-read the current sole TODO,
checkpoints and exact operation receipts. Inspect unfinished task chats assigned to your scopes and
apply the canonical recovery rules to any confirmed abnormal stop or premature
incomplete result, preserving completed work, live/unknown owners, pauses, Stop,
actual controls and EVERY-send admission. Report significant findings, actions,
verified results and concrete blockers in this same chat in the owner's language.
Continue independent authorized work when a particular action remains blocked.
```

## Engineering and acceptance

1. Record the task and criteria in the existing queue. Verify owner, dependencies and actual base.
2. Independently accept new architecture/cross-module contracts before dependent code. Recheck a materially changed contract before continuing.
3. In every software project, new behavior starts with a test and observed intended failure; implement minimally, then refactor on green tests. Bug fixes start with a regression test. Pure wording/layout/config edits without changed behavior need no invented tests.
4. Author runs relevant checks/builds and records outcomes. Broaden for actual impact, unresolved failures or new evidence; avoid ritual full rebuilds/cache clearing.
5. Independent review checks the final identified snapshot against human requirements and the accepted contract. A plan's omission does not remove a requirement. Verify actual behavior/integration, source support or final pixels as appropriate; stub files, unwired output and checklist words alone do not demonstrate completion.
6. Track each finding's ID, risk/trigger, evidence, disposition, fix/refutation and recheck. Deduplicate defects without dropping claims. Recheck affected delta and neighboring invariants; reuse valid checks on unchanged relevant inputs and widen only for real scope/risk/change. Failed reviewer launches, missing evidence and unknowns cannot become clean acceptance.
7. Managing chat accepts only after the required [review gate](routing.md), updates TODO and releases ownership. Executor DONE is not acceptance. A finished child does not close an unfinished parent; sprint acceptance includes combined checks/demonstration when relevant.

After recording task or stage acceptance in the owning TODO, the manager checks before ending the same turn which successors in its scope may have been unblocked. Verify existing authorization, acceptance of all other prerequisites, current ownership, and applicable host and approval controls. Start each ready successor through its applicable execution path. For delegated work, reserve and dispatch under [allocate and reserve before dispatch](#allocate-and-reserve-before-dispatch). In that turn, verify substantive work start for the exact task and turn using the supported route's evidence. Queue state, title changes, READY, an initializer or a delivery ACK alone are insufficient. For eligible manager-direct work, record the existing no-chat rationale and evidence of substantive execution in the owning TODO.

If a checked successor cannot start or its start cannot be confirmed, record the concrete reason in the existing TODO or linked evidence and report it. Treat a send with uncertain ACK as unresolved under [operations](operations.md) and reconcile the exact operation without replay or duplicate dispatch. Respect existing running assignments, pending decisions and Stop. A verification-only grant leaves deployment out of scope. No dispatch is required when no successor is ready, and predecessor acceptance stands regardless of successor start.

Task titles display the explicit state in the owning TODO. The owning manager uses the [task title procedure](chats.md#managing-titles-and-intake) for the exact owned task chat. Use `🟡` (U+1F7E1) for queued work with a chat, including a newly created chat for a queued or reserved task awaiting confirmed substantive start. For a queue entry without a chat, record the state in TODO only. The title rule never creates a chat. On explicit reopening of a previously accepted task awaiting dispatch, record it as queued in the owning TODO and apply `🟡` to the same chat. After the manager observes a matching substantive work-start ACK for the exact task chat and records in-progress in TODO, apply `⚙️` (U+2699 U+FE0F). An initializer, READY or delivery ACK alone cannot establish substantive start. After recording actual accepted-complete in the owning TODO, apply `✔️` (U+2714 U+FE0F) in the same closing manager turn before reporting closure. A single completed turn, an old executor DONE, pending checks, archiving or cancellation alone cannot trigger a title transition. Preserve paused, blocked, unknown and cancelled states without automatically assigning a queued or completed icon. If a required title update cannot be safely confirmed, preserve the recorded TODO state, record the concrete pending or uncertain title outcome in the existing TODO or its linked evidence, and report and reconcile only the title effect. This task-title rule adds no scheduler or status registry.

During normal same-turn handling of the exact owned task and chat, including before substantive start, the owning manager must record the concrete wait and reason in the sole TODO before applying a waiting icon. Use `🙋` (U+1F64B) when a specific human choice, approval or answer is required to proceed and the question or needed decision is recorded there. Use `💤` (U+1F4A4) when progress is blocked pending the still-outstanding result or acceptance of another specifically identified task or stage. Record that task or stage ID and the needed result or acceptance in the sole TODO before applying the icon. A known relation without blocking effect is insufficient. Use `⏳` (U+23F3) for other concrete waits, such as tool, service or network recovery, exact operation reconciliation, or a concrete blocker before an exact task or stage dependency has been verified. When several gates coexist, display `🙋` first, then `💤` for any verified blocking task or stage dependency, then `⏳` for other concrete waits. A status question, ordinary queueing, an active in-flight job, mere inactivity or a deliberate pause is insufficient by itself to establish a wait. Preserve explicit Stop and indefinite deferral without automatically relabelling either as a live wait. Cancelled, historical and archived work do not become live waits. A concrete non-human wait may coexist with blocked or UNKNOWN evidence. A waiting icon leaves lifecycle, authorization, unknown ownership, approval and non-replay controls intact and supplies no resolution of an unknown outcome.

Use `⏸️` (U+23F8 U+FE0F) for a previously started or assigned task with confirmed cessation when either the task is explicitly deferred without a scheduled or reserved resumption, or the cause of cessation is unknown and no other actual state applies. Check the exact task and its executor or current work using the [cessation evidence](#task-chat-cessation-report). An idle chat, silence, discussion, READY or an unresolved operation that may still be running is insufficient evidence of cessation. A concrete, recorded wait for network or service recovery or exact operation reconciliation uses `⏳` under the wait rule, even when its timing or outcome is unknown. A verified explicit indefinite deferral overrides concurrent live waits until an explicit decision to resume. Preserve explicit Stop, denial, cancellation, archive, paused or unknown ownership and exact no-replay obligations. The icon supplies no authority or outcome. In the same handling turn, the owning manager records the confirmed cessation and its reason, including an unknown cause when applicable, in the existing TODO text before changing the exact title and checking it through the existing procedure. Use the existing TODO format and fields.

Keep all actual blockers in the sole TODO. Reassess the gates when verified facts change, and update the waiting icon on the same chat using that precedence. Clear each reason only when its resolution is verified. When the unknown cause of confirmed cessation is verified, replace `⏸️` with `⏳`, `🙋` or `💤` as applicable, or apply the exit rules if no actual wait remains. Once an explicit deferral is lifted, apply the existing gate precedence. When a dependency clears, use the highest-priority remaining wait, including `💤` if another verified blocking dependency remains. A cleared dependency alone cannot establish readiness, substantive start or acceptance. If no wait remains, apply the exit rules below. Record the resulting state in TODO before updating the title. On verified substantive continuation use `⚙️`, with matching current evidence when the same exact live assignment is already working. A human reply or cleared blocker alone cannot establish substantive start. Use `🟡` when ready and awaiting dispatch or start, including an authorized paused continuation awaiting start. Use `✔️` only after actual independent acceptance is recorded as accepted-complete, under the closing rule above.


Keep the authorized goal distinct from an individual invocation. After a failed,
incomplete, unusable or unknown result, assess the current TODO and receipts for
useful work still authorized: intake/review, preparation, decomposition, dependency
reconciliation or another ready task. Continue such work instead of ending the
goal because that invocation stopped. Preserve narrower grants, denials and unknown
ownership under [operations](operations.md): an exhausted one-call grant bars a
second call under that grant. If no useful authorized path remains, record the
concrete consolidated blocker and next required decision/access in the same
TODO/checkpoint. Human Stop and goal completion remain valid stopping conditions;
continuation creates no wakeup or schedule.

Identify exact reviewed source/result using the project's chosen mechanism. Version control, including Git, is optional; when used, include base/head and all relevant dirty/untracked content, since HEAD alone is insufficient. For file or native document/table/image work without VCS, use exact bytes/hashes or native object IDs and revisions with sufficient accessible content to identify the result. Preserve any required worker/native hash and pin contracts. A reviewer records requirement, artifact/snapshot, substantive result, actual check, evidence and verified/failed/unknown disposition; a compact table is useful when there are several requirements. Author/material coauthors cannot independently accept their result. If a reviewer makes a substantive fix, another independent reviewer accepts that part. Use the [result packet](../assets/result-template.md), retaining actual driver state separately.

## Resume safely

Store the [resume packet](../assets/resume-template.md) in existing plan/evidence and link it from TODO. On restart read TODO for current owner/status, reconcile the same task chat/assignment and operation receipts, check relevant freshness, then take the single next safe action. Preserve accepted decisions, input versions, open findings and late-result handling. Verify base and dependent versions before applying and integrating; a detected shift stops application for reconciliation. Late answers/edits are preserved separately and compared, never auto-overwriting an accepted result. Do not blindly relaunch an unknown operation or an alternative with ambiguous dispatch intent. Known-running confirmed progress follows normal observation; unfinished does not mean unknown. A checkpoint cannot declare termination or transfer write ownership; default covered reversible local continuation after uncertainty expiry or a trusted terminal is governed by [operations](operations.md), without a separate project risk acknowledgement or required exact terminal/cleanup proof.

Persist a material accepted new or changed decision in the existing appropriate TODO, plan or evidence record before its first dependent action, with source/scope reference. Mark replaced decisions within the affected scope; preserve original evidence, unrelated standing decisions and existing consent/architecture/review gates.

Check the resume checkpoint for freshness at task completion or acceptance, material direction changes, an authorized pause, and before known upcoming compaction when feasible. Update only changed facts/references; an already current checkpoint needs no rewrite. Never delay or override Stop to save it.

Keep an unambiguous pointer from the existing TODO item to the applicable current checkpoint; retain replaced snapshots as history. Apply the existing Resume safely procedure after context compaction using relevant current inputs, without replaying operations, restarting workers or transferring owners.

[Operations](operations.md) defines default continuation of covered reversible local work after at most 15 minutes of uncertainty, with a new linked remaining-work assignment, preserved original ownership/receipts, non-replay, actual controls and manager reconciliation/integration. Exact terminal/cleanup and separate project activation are not prerequisites for that covered policy. Its finite text-only alternative remains distinct. A checkpoint cannot declare termination or transfer the original operation's ownership. Non-covered integration and manager handoff retain the operations cleanup/exclusion boundary; a matching snapshot proves no physical exclusion.

Archive only fully completed queue entries with dates/evidence and corrected links. Retain active, paused, blocked, partial or disputed work. Preserve history. Product-specific tests, audience rules, infrastructure/deployment grants and run-volume consent stay in the folder and can strengthen common controls.

## Allocate and reserve before dispatch

For a multi-task package, form the sprint in the sole TODO and allocate its tasks to logical stages by shared outcome/dependencies
before dispatch; each task's persistent chat is the execution unit, linked to its sprint and stage in the existing TODO. The sprint plan explains goal, stage membership, order and completion;
sole TODO owns current allocation, owner/write-set and accepted dependency evidence.
The manager defines each unit's goal, acceptance criteria, input snapshot, dependencies and owner/write-set in the existing TODO. Run task chats concurrently only where their work is independent and write-sets do not conflict; serialize changes to shared files. Within a sprint, stages execute in order by default unless the documented concurrency exception in [chats](chats.md#task-chats-inside-a-sprint) applies. The manager resolves collisions against the current base, coordinates the required reconciliation and integrates/checks the combined result, without silently overwriting another owner's work or bypassing accepted dependencies. A completed stage does not close an unfinished sprint. Very small manager-performed work may have a justified no-chat rationale recorded in the sole TODO. A bounded helper or stateless executor does not establish a task chat. Planning alone
is not execution and neither batching nor splitting lowers the review gate.

Supporting assignments remain substeps of the original task under [one task, one persistent chat](chats.md#one-task-one-persistent-chat); reserve their dispatches in that task's existing sole-TODO item, not as new task execution units.

Before EVERY delegated send, including review and follow-up, the manager verifies
the [current assignment routing and scoped human exceptions](routing.md#apply-routing-to-every-assignment),
current sole-TODO allocation, current owner, bounded scope/write-set or read-only
boundary, accepted prerequisites, exact intended recipient and logical dispatch
reservation. Missing, stale, conflicting or unknown allocation, owner, target or
prior outcome means **NO SEND** for that unbound/unknown operation. A new
covered local remaining-work unit must have its own known recipient, current
allocation and admission under operations; the old unknown receipt is not
erased or reused to qualify it. Briefs, plans and technical receipts cannot
replace that pre-send reservation. Use ordinary text in the existing TODO entry,
not another queue, schema or state engine.

For first dispatch, the manager retains launch coordination and records the
proposed executor/reviewer; executing ownership is not claimed before ACK.
Follow-up preserves the existing known live owner. Never erase unknown intent,
reservation or receipts to regain eligibility.

Bind identity to the actual route:

- Persistent: use the exact known chat/session and relevant operation/turn IDs.
  Creation retains protected pending intent before an ID exists; save the
  acknowledged chat ID before later calls. Reuse the same task chat for resume
  and follow-up under [chats](chats.md) and the selected host's supported semantics.
- Stateless: bind exact logical assignment/intended invocation, selected
  destination/profile and supplied snapshot. Independent reviewer invocation
  differs from actual authors/coauthors under [routing](routing.md). No invented
  chat/turn or persistent bootstrap applies; this is not an executing task chat.

After ACK, save and match the route's returned identity/receipt to the SAME
reserved assignment, target, owner and scope. Match persistent chat/turn IDs when
returned; stateless receipt/invocation binding needs no synthetic native turn.
Without ACK, retain uncertain intent and available receipt; a local prepared
record is not remote acceptance. Reconcile actual dispatched ownership only
within the preassigned scope/dependencies. Conflicting ACK or missing binding
leaves delivered work unaccepted and blocks dependent continuation. No retroactive
allocation, resend or other remote effect may repair metadata.

Unknown live-owner identity/status or earlier request outcome means **NO SEND to
that target until trusted exact reconciliation**. Preserve owners, pauses/Stop,
accepted prerequisites and original receipts. A new invocation ID, provider or
output path never permits replay, a duplicate task chat/worker or takeover.
This NO SEND preserves the original unknown target/operation; it does not forbid
a separately admitted remaining-work unit under [operations](operations.md)
default covered local continuation after its non-resetting deadline. The finite
text-only alternative remains separate. Neither replays the original operation
or transfers its ownership; covered local integration uses manager reconciliation.
Delivery, response, task completion and manager acceptance remain separate;
backend persistence needs separate human GUI confirmation for a visibility claim.
READY, a plan or internal subagent is not executing visible sprint work. Apply
the [in-progress title rule](#engineering-and-acceptance) when recording a
confirmed substantive start.

Concrete missing capability blocks only its dependent action. Continue disjoint
already-authorized preparation; do not stop merely at metadata. A scoped reserve
preserves provider/mode restrictions and independence; missing access never
permits denial bypass or a new default. The manager checks TODO admission;
existing transport receipts/duplicate barriers do not implement a TODO parser.

## One coherent brief and useful return

Use [assignment](../assets/assignment-template.md), [result](../assets/result-template.md)
and [checkpoint](../assets/resume-template.md) fields only as applicable, once.
[Communication](communication.md) owns source coverage/access, language and
source-as-data separation. Retain actual task capability/controls; a native
no-tools brief or read-only selection does not establish tool suppression or
qualification; see [chats](chats.md#managing-titles-and-intake).

Record supplied bytes/hash and applicable context/output accounting, labeling
estimates. Bytes are not tokens; retained conversation/tool context needs headroom.
When reported reasoning consumes output budget, distinguish total budget from
requested public answer. Use supported task-scoped settings without changing defaults or
equating effort labels across providers. There is no universal numerical task, prompt,
file, effort or output cap or hidden-reasoning word limit. Do not expose hidden
reasoning or force compression.

Return the actual artifact/hash, checks, unmet criteria and next safe action;
safe partials remain unaccepted. Resume from current TODO/checkpoint/receipts,
accepted decisions and relevant deltas instead of transcript replay. Independent
reviewers keep their identities and receive fresh final inputs, never the author
conversation for acceptance.

## Task-chat cessation report

Before a task chat deliberately ceases active work on its assignment or enters a managed wait, it must leave a short state report for the exact current manager bound to this task and scope. Abrupt failures and explicit human Stop follow the exceptions below. This rule applies to the existing execution flow and creates no new dispatcher, daemon or callback engine.

- **Managed stop or wait** — assigned work completed and ready for review, acceptance reached, blocked, waiting on a dependency or human decision, authorized pause or deliberate handover — requires this short report before the chat ceases active work.
- **Crash, route failure or abrupt interruption** — the report is best-effort and is not guaranteed to be sent. The manager records the missing expected report for the exact known task/turn as unknown; missing delivery alone proves neither a stop nor completion.
- **Explicit human Stop** — obey immediately; do not wait for, launch tools for, or delay the Stop to produce a report.

Report format (concise, actual facts only):
state/reason; what was completed and actually checked within the assigned scope; concrete remainder; exact available artifacts/checkpoints with project-chosen identity (never a display number instead of canonical IDs); the single next safe action and who must take it.

State labels stay separate: report ready, delivery acknowledged, manager observed and manager accepted are distinct facts. A transport acknowledgement is not the manager reading the report. DONE claims only completed scope and still require independent acceptance; BLOCKED and WAIT are never disguised as DONE.

Save the report in the same task chat and existing evidence/TODO binding. Notify the exact current manager bound to this task and scope only through a supported, permitted mechanism bound by the assignment; direct sending is not an invented capability. If no route or delivery exists, record the report as unconfirmed/pending and leave the manager to retrieve it on the next opportunity; a missing route does not justify holding authorized work indefinitely or weakening controls. Do not create mutual notification obligations on acknowledgement.

An initializer, ordinary ACK or routine progress is not a cessation; this rule is not invoked for every tool call or short pause. For a managed contextual handover, preserve continuation and bind the exact return route in the assignment. Before any notification, respect current manager ownership, non-replay, EVERY-send admission and handoff state; never send to a former manager after handoff. No automatic manager wakeup or delivery guarantee exists for a crash; the existing hourly check acts only when a supported mechanism is present.

At the next supported observation opportunity, the manager reconciles the exact task, turn, available public result and receipts against the expected report. Confirmed active work remains under normal observation. A confirmed premature end without the required result calls for diagnosis and permitted continuation under the existing recovery rules; deliberate pauses and human Stop are preserved. Record actual report observation in the existing task evidence/TODO binding before treating it as received, and apply the independent gate before accepting the task. If no observation or wakeup mechanism is available, retain that concrete limitation and pending state rather than claiming background monitoring or delivery.
