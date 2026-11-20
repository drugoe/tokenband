# Compact result packet

Lead with the outcome: **DONE**, **CONCERNS**, **BLOCKED** or **NEEDS_CONTEXT**, then its practical meaning. These are semantic report labels, not worker JSON/lifecycle states. DONE means the executor completed its scope; only the managing chat records acceptance after the required independent gate.

- Binding: assignment/folder/TODO and route/invocation IDs; allocated task chat if any, its sprint and stage identifiers/prefix when applicable, exact chat/session/relevant turn only for a persistent route; actual author/coauthors and role; requested provider/model/effort versus observed metadata; continuation identity or unknown.
- Artifacts: produced/changed artifacts and exact final identity using the project-chosen mechanism, including relevant dirty/untracked content when VCS applies or native object IDs/revisions and accessible content otherwise; input versions/freshness; actual versus permitted write delta. Preserve originals where relevant.
- Requirements: requirement → actual behavior/integration, supported claim or inspected final pixels → check/result → evidence → verified/failed/unknown. Summarize useful deltas; link durable evidence rather than whole logs. Text-only recipients receive necessary bytes.
- Verification: checks actually run and outcomes/limitations; separate suggested or unrun checks. Include intended RED/GREEN for new software behavior/bug fixes. Reused checks name the unchanged inputs that keep them valid.
- Findings: ID, risk/trigger, source evidence, disposition, fix/refutation and focused recheck. State unmet criteria, uncertainty and next needed action; do not hide concerns behind DONE.
- Execution: driver's actual status, last confirmed progress/unknown-since time if relevant, operation IDs, original/alternative receipt links, cleanup/isolation evidence and any late result. Report these separately from the semantic outcome; a timeout or wrapper exit is not termination proof.
- Intake: required review stage/reviewer IDs, exact reviewed snapshot, conclusions and remaining findings; managing acceptance remains pending unless actually recorded in TODO.
- Cessation/handover transition: if this packet closes a managed stop, handover or wait under [task-chat cessation report](../references/lifecycle.md#task-chat-cessation-report), state the transition facts — reason, exact remainder, available artifacts/checkpoints and next owner — without duplicating the full cessation report.

Use only applicable fields; follow [communication](../references/communication.md), [lifecycle](../references/lifecycle.md) and the relevant subject checks. Never replace evidence with template words or infer observed model identity from a requested setting.
