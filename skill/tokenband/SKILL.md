---
name: tokenband
description: TokenBand (tb) coordinates folder-owned tasks and sprint stages through persistent task chats led by a configured executor and independent reviewer roles to conserve primary-model limits. Use for budget-conscious workflow setup, delegated development, research or content production, and explicitly requested managing/task chat creation or new-host setup; ordinary standalone answers need no team.
license: MIT
metadata:
  version: "0.6.6"
  maturity: "experimental"
  candidate_revision: "20261120.1"
  release_state: "local_experimental_release"
---

# TokenBand

**tb** is an accepted short name for TokenBand. Interpret it as this skill when the context refers to TokenBand; keep the canonical skill name and identifier `tokenband`.

Use the resolved human language for all workflow communication; this skill fixes no particular language for every project. Preserve exact source text, identifiers and requested deliverable language. [Communication](references/communication.md) owns the language rule, handoffs, source access and fidelity. Ordinary factual answers and meaning-preserving mechanical corrections stay direct: no new task, sprint, team, reviewer or packet solely for this skill. Very small simple tasks are performed directly by the manager, while any change in the behavior of the application, project, skill or process requires its own persistent task chat, and other substantive work also uses a task chat; task boundaries and supporting substeps follow [one task, one persistent chat](references/chats.md#one-task-one-persistent-chat). Technical proposals follow [advice before execution](#advice-before-execution), including when delivered in chat.

## Evidence-based recommendations and disagreement

Treat a user's suggested alternative as a proposal to evaluate, not as evidence that it is better or an instruction to endorse it. Distinguish a request for evaluation from an explicit decision to proceed.

Prepare and compare proposals under [advice before execution](#advice-before-execution).

When reconsidering an earlier recommendation:
- Identify the new evidence, changed requirement, or specific error in the earlier reasoning.
- Explain which comparison criterion changes and why that changes the conclusion.
- If there is no such basis, retain the recommendation and explain why the proposed alternative does not improve it.
- If the alternatives are effectively equivalent, say so and identify the preference or convention that decides between them.

Do not invent supporting reasons merely to align with the user's latest suggestion. User disagreement alone is not technical evidence.

If contradictory recommendations have already been given, pause implementation and compare all options under one consistent set of criteria. An apology or admission of error does not validate the latest recommendation. State what remains unverified and perform the smallest relevant check before claiming a preferred solution.

## Advice before execution

Before implementing a new task, the executor studies the problem, related sources (including source code where applicable) and current documentation, then prepares solution options. Reuse still-current findings and an already selected option rather than reopening an accepted decision.

Label the options explicitly in the human's language:

- **Simplest** ("Наиболее простой" in Russian): the minimal sufficient solution with the smallest amount of change.
- **Recommended** ("Рекомендуемый"): a solution with justified improvements whose benefit warrants the additional complexity.
- **Middle** ("Средний"), when project rules provide for it or the user requests it: the simple solution with the most useful elements of the recommended one.

For each option, explain in plain language:

1. The original problem; attach relevant screenshots when available.
2. What changes for the user and how the corrected scenario works.
3. Which requirements it meets and which limitations remain.
4. How it differs in complexity, risks and dependencies.

Compare viable options using the same task-specific criteria: correctness, scope, compatibility, duplication, maintainability and verification cost. Do not add requirements or infrastructure for possible future growth without confirmed need. If options effectively coincide, say so directly; if the simplest is also recommended, label it as both rather than inventing alternatives or unnecessary complexity. State separately which option is recommended and why, including material uncertainty.

All technical proposals require independent review before being presented as final, including short proposals in ordinary chat replies. Clearly mark drafts. After substantial changes, recheck the changed part and affected assumptions under the existing [review gate](references/routing.md#review-gates). A suitable independent review of the same final content against the same criteria may satisfy this requirement; do not duplicate it or lower an applicable critical gate.

When the user has reserved the choice, implementation waits for the user's decision. An already selected option and previously granted permission need no repeated confirmation. Distinguish informational/how-to questions from execution instructions: a question alone authorizes no edits, launches, installations or other state changes. Explain suitable approaches when asked how something can be done. A question during authorized work does not by itself cancel or expand that authorization.

Once this skill is active for a project's workflow, attempt to run every new task and every agent launch or assignment under these rules, including reviews, child delegation, follow-ups and replacement, unless the human explicitly changes the project's skill rules; only such an explicit human instruction changes them, and only within its stated scope. Carry the applicable rules and scoped exceptions into delegated briefs and handoffs. Before each assignment/send, apply [current routing and scoped exceptions](references/routing.md#apply-routing-to-every-assignment); historical blockers or temporary reserve permission do not silently become a new default.

Reuse the folder's sole TODO, plans/sprints, index and evidence (normally `TODO.md`, `docs/sprint-plan.md`, `docs/INDEX.md`). [Lifecycle](references/lifecycle.md) owns admission before EVERY delegated send, current ownership/pauses, accepted dependencies, engineering, intake and restart; consult it after context compaction and, when feasible, refresh the checkpoint before known compaction without delaying Stop. Choose direct manager work, a dedicated persistent task chat or a staged sprint by ready TODO scope, size, duration, dependencies, parallel ownership and risk; record the no-chat rationale in the sole TODO. One standalone substantive task uses one persistent task chat and related continuations/corrections of the same scope reuse its exact ID; a multi-task package forms a sprint divided into logical stages, and every substantive task in a stage gets its own persistent task chat. Keep all necessary task/sprint/worktree folders bound to the same existing project under [project and folder binding](references/chats.md#project-and-folder-binding), created inside the canonical project root, with the actual work directory explicit. A sprint is a plan/group of tasks in the sole TODO, not a chat: there is no one-chat-per-sprint, no shared sprint chat, no aggregate sprint or stage execution chat and no hidden hub, and the manager coordinates the task chats, distributing disjoint scopes, serializing shared files and resolving collisions. Stage order, the documented concurrency exception and task-chat titles follow [chats](references/chats.md#task-chats-inside-a-sprint). Supporting agents and stateless review follow [one task, one persistent chat](references/chats.md#one-task-one-persistent-chat); a bounded helper or stateless executor is not a replacement for a task chat. On first activation, [chats](references/chats.md#managing-titles-and-intake) governs current-chat manager adoption and the managing chat's own title self-rename; installation or discovery alone executes nothing. Plans and READY are not executing work. No unrelated chats, schedules or human messages are authorized.

[Chats](references/chats.md) owns new internal ordinary-primary coordination chats and explicit [manager succession](references/chats.md#manager-succession-and-handoff). First adoption keeps the current chat as manager. External executor/API routing remains distinct. [Lifecycle](references/lifecycle.md#continuing-a-stopped-external-task-chat) owns the permitted internal continuation of a known-stopped external task chat.

Use [routing](references/routing.md) before selecting roles or reviews: configured ordinary primary manages, main external executes, eligible independent peers review, and permitted reserve needs assignment-specific grounds. Preserve mode/provider restrictions and standing consent under [assigned-task authority](references/routing.md#equal-authority-within-the-assigned-task), which permits authorized external models all task materials allowed for the primary while keeping each request relevant and concise; no denial bypass or default/global change. Every top invocation needs scoped consent. Before the first legitimate dispatch, discover and bind the applicable trusted consent to the exact provider, task, data and actions per [trusted consent discovery](references/routing.md#discover-and-bind-trusted-consent-before-dispatch). Each critical gate keeps two independent non-top reviews plus exactly the approved additional top reviews; splitting or a small diff cannot lower aggregate risk.

New software behavior and bug fixes require intended RED, minimal GREEN and refactor on green tests. Accept architecture before dependent implementation; identify final bytes including dirty/untracked content and obtain the applicable independent final gate. Author DONE is not acceptance. Load only relevant subject checks: [research](references/research.md), [texts](references/texts.md), [graphics](references/graphics.md), [marketing](references/marketing.md).

Resolve the configured mechanism (role, provider, model, effort, transport, adapter/driver) before host delegation per [routing](references/routing.md#select-the-actual-configured-mechanism). Follow the actual selected mechanism. For the optional bundled CLI, read the applicable [worker section](references/worker.md); Python 3.10+ is its prerequisite, not a requirement for ordinary text/file coordination. For an explicit new managing or task chat, follow [requested-chat outcome](references/chats.md#requested-chat-outcome), including supported host discovery and completing already-authorized setup before a capability verdict. For persistent continuation, read [chats](references/chats.md) and its selected host. Use [setup](references/setup.md) for missing/changed configuration or requested setup; reuse trusted choices and keep credential values out of chat. Native tools require a compatible implemented route and actual host controls; ordinary Codex schema2 uses current structural checks without historical qualification or synthetic bootstrap. See [ordinary execution](references/qualification.md#ordinary-codex-schema2-execution). A no-tools brief or read-only selection does not establish capability.

Before observation, recovery or replacement read [operations](references/operations.md): preserve actual quotas, permissions/Auto-review, secrets and owned cleanup; never replay accepted/unknown work. Known progress differs from unknown outcome; the finite isolated read-only exception grants no write-owner transfer. Announce the requested provider/model/effort, role, scope, mechanism and access before launch; record returned identity and observed state separately. At active manager creation/adoption, arrange the built-in same-chat hourly check under [hourly manager recovery check](references/lifecycle.md#hourly-manager-recovery-check); installing this skill creates no schedule.

Keep host/product grants and mechanics in their owning folder/configuration. Use the [rule index](references/rule-index.md) for package maintenance/control verification; historical audits are not ordinary runtime dependencies.
