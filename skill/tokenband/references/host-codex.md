# Codex native session integration

Read this reference only for the selected Codex session host. Resolve its native
runtime, configuration and optional local socket through user settings/discovery;
the core settings remain in WORKFLOW_HOME. The managing model need not belong
to this host's default provider. Use the installed version's qualified schema.
See the [official App Server reference](https://learn.chatgpt.com/docs/app-server).

Use this reference for internal coordination chats, authorized external worker execution,
and exact existing-session observations. Keep these scopes separate.

Initialize the connection and send initialized. Use persistent thread/start
with the selected registered native provider ID, model and effort, then set the
name. Native provider IDs can differ from workflow connection aliases. Verify
the returned identity, complete the initialization turn under the actual parent
permissions, confirm normal discovery and read after reconnect before the real
sprint brief. An empty draft may disappear; a CLI exec transcript can remain
absent from the client's ordinary chat list.

The bundled driver resumes and starts later turns on the same ID after the
previous foreground turn ends. Its locked foreground journal does not expose
concurrent live steering, interruption or live status to another worker command.
The underlying App Server's richer controls do not make those capabilities
available through this driver; use only an independently supported host control
channel when one exists.
Preserve the actual native permission profile and approval reviewer; never mix
incompatible permission/sandbox fields. Approval requests without the authorized
handler remain blocked. A shared daemon owns its server and accepted work;
close only your connection. An owned server requires verified process ownership
and cleanup, and its owner must stay alive through the active turn.

## Ограниченное наблюдение exact turn на существующем соединении

Для уже разрешённого manual control channel используйте `RPC.next_event(timeout)`:
он сначала отдаёт существующую очередь, включая события до ACK. `RPC.event()`
читает transport напрямую и для этого observer не подходит. `RPC.call()` внутри
по-прежнему читает transport и сохраняет уведомления до matched ответа.
`call(method, params, deadline=...)` принимает абсолютный monotonic deadline
только для metadata reads и `turn/interrupt`; `turn/start`, создание/resume,
steer и command/exec с таким deadline запрещены до send. Defaults `_turn` и
progress/silence не меняются. Новый общий deadline задачи не вводится.

Ниже executable recipe для caller, который уже владеет проверенным `rpc` из
того же закрытого пакета. Он не открывает соединение, не пишет новый receipt
формат и не даёт полномочий на interrupt. `deadline` вычисляет caller из остатка
существующего бюджета; `interrupt_allowed` учитывает исходный intent, exact IDs,
поддержку owned stop и отсутствие уже принятого/неизвестного control запроса.
После рестарта monotonic значение не переиспользуется: остаток восстанавливается
из прежнего first uncertainty без сброса часов по [operations](operations.md).

```python
import time
import worker as w
from native_transport import NativeRPCError
from native_codex import terminal_observation

def observe_existing(rpc, thread_id, turn_id, deadline, *, interrupt_allowed):
    observed, failure = None, None

    def queued():
        while rpc.events:
            value = terminal_observation(rpc.next_event(timeout=0),
                                        thread_id=thread_id, turn_id=turn_id)
            if value is not None:
                return value
        return None

    try:
        observed = queued()
        if observed is not None:
            return observed, failure
        if interrupt_allowed and time.monotonic() < deadline:
            # Caller сохраняет исходный exact intent ДО этого call, не replay.
            try:
                rpc.call("turn/interrupt", {"threadId": thread_id, "turnId": turn_id},
                         deadline=deadline)
            except w.WorkflowError as error:
                failure = error
            finally:
                observed = queued()  # До-ACK события доступны и после rejection.
            if observed is not None:
                return observed, failure
            if (failure is not None and not isinstance(failure, NativeRPCError)
                    and failure.code != "native_inactivity"):
                return None, failure  # Host/approval/protocol error не обходится.
            # Timeout control остаётся UNKNOWN, не ACK: продолжаем только чтение.
        while time.monotonic() < deadline:
            try:
                event = rpc.next_event(timeout=min(60, deadline - time.monotonic()))
            except w.WorkflowError as error:
                if error.code == "native_inactivity":
                    continue  # Следующий чанк в том же deadline, без нового RPC.
                raise
            observed = terminal_observation(event, thread_id=thread_id, turn_id=turn_id)
            if observed is not None:
                return observed, failure
    except w.WorkflowError as error:
        if failure is None:
            failure = error
    return None, failure
```

Caller отдельно сохраняет available safe control evidence и terminal result в
своём существующем receipt, не `str(error)`, message/data или raw event. Для
`NativeRPCError` доступны `method/request_id/rpc_code/category`; собственные
thread/turn берутся из intent. `None` вместо terminal означает UNKNOWN; ACK `{}`
остаётся отдельным фактом. `terminal_observation()` возвращает только exact
`thread_id/turn_id/status` (completed/failed/interrupted), отклоняет чужие,
противоречивые IDs и malformed terminal. Это primitive также вызывает `_turn`;
его прежние public processing и status-before-raise сохраняются. Primitive не
проверяет все прочие уведомления: полный event loop обязан сохранить существующие
host validators, error projection и обработку реальных approval/denial. Recipe
служит только наблюдению terminal на уже разрешённом канале; ненулевой `failure`
не стирается найденным terminal и не разрешает следующий запуск.

Terminal не доказывает полноту ответа, cleanup или передачу записи. Порядок
выбора оставшегося scope и все gates принадлежат [operations](operations.md).
Новый CLI profile описан в [worker](worker.md#persistent-sprint-sessions).
`sprint-interrupt` от этого recipe не становится live control. Уже потерянная
очередь не восстанавливается; существующий внешний observer должен отдельно
перейти на правильный вызов на разрешённой границе, без повторного interrupt.

When Codex Desktop is available, inspect projects/chats and use its creation
tool only if it explicitly supports the selected chat provider/model/effort under
[chat-model rules](chats.md) and the actual controls.
A queued client ID is not a usable native chat ID. Verify registration and
intended project/host in the client; attach a native-created chat through the
client's supported project operation if needed. Pin only when authorized.
Source metadata or native thread discovery alone does not confirm visibility.
Follow the creation tool's UI directive requirements for chats it creates.
Headless execution keeps visibility pending until a client can verify it.

## Native Windows worker sessions with the bundled driver

Use this route to execute an authorized external worker assignment, linked to its
internal coordination chat and the exact TODO reservation. The bundled driver
uses its own App Server over stdio for the worker lifecycle.

1. Select an existing protected task configuration whose `roles.main_external`
   points to the requested provider, model, and effort. Verify the profile's
   `chat.driver` and `chat.native_provider`, the driver's pinned Windows
   runtime, `owned-stdio` connection and `native_home`, and the existing
   provider registration. The provider alias for the authorization and the
   native provider ID are different fields. Examples: StepFun
   `step-5-preview` with `stepfun_token_plan`; Z.ai `glm-5.3` with
   `zai_coding_plan`. Resolve the actual current binding rather than
   copying an example or changing shared defaults.
2. In each operation's process set `WORKFLOW_HOME` to the original or already
   frozen workflow root and `CODEX_HOME` to the driver's resolved native home.
   Use the verified current parent controls, a new task identity, a unique
   operation ID, a UTF-8 brief and fresh protected authorization tied to that
   brief. Follow [reservation and non-replay](lifecycle.md#allocate-and-reserve-before-dispatch).
   Leave credentials in the existing native authentication mechanism.
3. Run the installed worker once. This is one command; quote paths on
   Windows. A smoke-test brief needs only a distinctive expected reply and
   no tools.

   ```text
   python -B <installed worker.py> --config <protected config> sprint-create
     --workdir <folder> --sprint <new task ID> --parent <parent chat ID>
     --authorization-file <protected authorization> --parent-context <verified context>
     --brief <UTF-8 brief> --operation-id <new operation ID>
   ```

   The driver passes both `model` and `modelProvider` with fallback disabled,
   saves the acknowledged native ID, initializes the chat, reconnects and
   sends the brief. The legacy `chat-create` alias allocates internal metadata only.
4. Verify the bound provider, model, effort, completed reply and thread ID.
   After the foreground process exits and owned cleanup is verified, run
   `sprint-status` with the same config, environment, folder, task ID, parent,
   authorization and context, omitting `--brief` and `--operation-id`.
   This reads without inference. Confirm the exact same ID and
   `native_read_status=persistent_idle` in the journal when that field is
   available; `operation_status=completed` alone does not prove a read.
   Continue via `sprint-send` with the same task identity and fresh authorization
   for each later turn. Reconcile an unknown acknowledgment on the original
   operation; do not create a replacement.

Keep the worker unit and any internal client chat separate, even if both are
persistent. Record the worker’s native persistence and observed result.

## Project and folder binding on the Codex host

[chats](chats.md#project-and-folder-binding) owns the coordination rule; this
section covers the native surface and its observed limits. Bind extra task,
sprint and worktree folders to the existing project; do not create a project
for such a folder. New working folders stay inside the canonical project root;
a host or worktree operation that requires an outside path follows
[chats](chats.md#project-and-folder-binding) as a concrete limitation, not a
silent outside creation.

The pinned schema supports three binding surfaces. `thread/start` takes an
optional `projectId` next to `cwd`, and a durable thread persists the
assignment. `thread/metadata/update` assigns an existing project ID to an
existing thread, or clears it with an empty string. `project/update` sets an
existing project's `roots`, which is how an additional folder joins that same
project; read the existing roots first and supply their union with all required
working folders, preserving unrelated roots. Confirm the actual readback; do not
replace the list with only the newest folder. `thread/resume` carries no
`projectId`, so resuming never changes the binding. Check support for every
field on the pinned host/version: a schema field is not a route capability, and
the selected helper's whitelist decides what may actually be called.

For project association, verify that projectId is a supported native
registry mapping before creation. An unrelated Desktop UUID is not that mapping;
omit an unverified optional ID. Preserve required supported client association.
Correct a known mapping/read rejection before create; a generic creation failure
or unknown ACK never authorizes replay. No global projectId ban or speculative
project API is introduced.

The bundled helper may exclude project operations even when the selected
host schema defines them. A local `unsupported_rpc` before submission proves
only that helper limit, not server incapability. Do not bypass its whitelist
or invent an unreviewed raw route. Use another already-supported, authorized
client operation when available; extending the helper requires separately
authorized and independently accepted implementation, not an implicit binding
exception.

[Official worktree documentation](https://learn.chatgpt.com/docs/environments/git-worktrees)
describes Codex worktree chats belonging to the same
project and a native Worktree/Handoff UI, with no universal API mapping from
folder structure to project grouping. Schema and model metadata alone do not
prove UI grouping; obtain separate human GUI confirmation of the exact chat and
its intended project.

When no supported explicit grouping is available, keep the canonical project
root as `cwd` for the new chat and convey the actual task/worktree directory
explicitly in the brief, the command `workdir` and absolute paths; a relative
path then resolves inside the main checkout, so any command that must touch the
work directory names it explicitly. This variant is expressible in the pinned
schema (`cwd`, `runtimeWorkspaceRoots` with absolute paths) but it is not an
attested GUI outcome and it adds no native grouping.

## Built-in same-chat hourly manager schedule

[Lifecycle](lifecycle.md#hourly-manager-recovery-check) owns the required hourly
check at active manager creation/adoption. Use the Codex app's supported built-in
schedule that continues the SAME manager chat. No cron, system scheduler or
separate service is part of this mechanism.

The [official automations documentation](https://learn.chatgpt.com/docs/automations?surface=app)
describes scheduled continuation of an existing chat, use of skills, the absence
of schedule-management UI in the CLI, and the requirement to keep the computer
and app running for local project work. Product support does not establish this
session's tool exposure, an actual registered schedule or a successful run.

Discover the actual built-in automation/schedule tool, including
`automation_update` where exposed. Use its actual schema to bind the existing
manager chat, one-hour cadence and applicable timezone; invent no tool fields.
Use the selected host's supported serialization when a previous check is busy;
reconcile active, queued or unknown operations before another recovery action.
Scheduling uses the host's effective background controls, which must be checked
separately from foreground permissions and may be narrower. A schedule does not
widen grants or controls. Pages/Sites schedules target a different product and
do not register a native Codex manager chat.

Follow [setup](setup.md#built-in-schedule-setup) for exact intent, ACK, readback
and unavailable-host handling. Distinguish configured from run-verified: an observed
hourly run and its effect are separate evidence; a manual check is not a timed
run. If the supported tool is unavailable, skip this automation and briefly record
the reason; project work continues without a setup dependency or waiting. Do not
assert that Codex lacks the feature or register it through files/TOML/raw RPC.
Installation of the skill alone creates no schedule.

## Existing shared-daemon route

Apply [EVERY-send admission](lifecycle.md#allocate-and-reserve-before-dispatch)
from this standalone host reference too. Use this route only where actually supported. Its Linux implementation
imports `native_transport.UnixWebSocket` and `native_transport.RPC` from the
trusted installed skill root; do not start a new writer or copy private connection
paths into this guide. Manual host operations expose neither concurrent worker
CLI controls nor satisfaction of its separate qualified-driver preflight.

### New-account discovery before an unavailable verdict

For an explicit request to create a chat, inspect the actual Codex host even when
no dedicated creation tool is exposed. Reuse [selected setup](setup.md#complete-selected-chat-setup)
and distinguish workflow text API configuration from the native provider registry.
A text-only workflow profile is not a native-host inspection result.

Resolve the current OS and trusted executable/version first. On a version that
supports it, the discovery command below inspects an existing daemon; it is not
a request to start another app-server. Use only that version's actual supported
schema and protected configuration. Missing local shell/read access means host
inspection unavailable, not "Codex cannot create chats". Record unsupported
commands/methods narrowly; do not assume this documented Linux shared route exists
on Windows or that a new version has the same protocol.

Inspect the selected native provider ID and nonsecret endpoint/wire/auth-reference
metadata. Use configured native registration when present. If absent, carry out
only already-authorized supported scoped setup or prepare the exact missing
registration/protocol/settings decision under setup's existing boundaries. A
successful text request is not a reason to guess native Responses compatibility,
copy credentials or launch a second daemon. Prefer an existing supported client
creation tool when it can honor the requested identity and controls.

The optional worker driver's qualification/control preflight and a supported
manual shared-host creation method are distinct surfaces. Determine which actual
surface is applicable before launch; incompatibility of one driver is not proof
that every host route is absent. This is not permission to evade an actual denial
or adopt a manual route without its own supported binding/controls evidence.
Keep native tool qualification separate from a requested persistent text chat.

Once all applicable prerequisites are established, complete the protected
creation/initializer/reconnect sequence below for the original request. Otherwise
report the exact last safe observation, missing capability/setup or actual denial
and the smallest prepared next action. Do not stop with only "creation tool
unavailable", a text-connection status or an unexecuted generic checklist.

### Discover and validate the existing writer

Resolve the actual runtime and reviewed executable SHA256 from trusted current
host configuration, following [setup](setup.md) and [paths](paths.md). Do not
substitute a PATH alias, wrapper or similarly named binary. For a pinned version
that supports the discovery command, invoke that resolved runtime with
`app-server daemon version`. Inspect its bounded discovery metadata: running
status, matching CLI/App Server versions, managed executable and discovered
`socketPath`. Compare the managed executable's bytes with the configured pin.
Missing, conflicting or ambiguous daemon identity is a blocker; it is not
permission to launch another writer or try arbitrary sockets. No private socket
path, numeric UID, binary location, endpoint or authentication value belongs in
this guide. Discovery through the existing protected host configuration does not
require modifying global settings.

Open the discovered socket with `UnixWebSocket(discovered_socket,
expected_hash=reviewed_runtime_sha256)`. The installed Linux transport checks that
the path is a socket owned by the current user, rejects externally writable or
symlink ancestors, and uses actual `SO_PEERCRED` to check the connected peer UID.
It resolves the peer executable through `/proc/<peer-pid>/exe` and compares its
SHA256 with the expected runtime pin, then validates the WebSocket upgrade.
Discovery metadata alone is not peer validation. Never disable these checks or
pretend that a Windows path converted to Unix syntax validates a Windows peer.
Close only this client connection; never signal or stop the shared daemon.

`RPC(transport)` performs `initialize` with the installed supported capabilities
(including `experimentalApi`) and then sends `initialized`. Initialize each new
connection before other calls. Use the installed RPC method surface and actual
supported host protocol. A client approval request needs the authorized supported
host bridge: RPC does not fabricate approval answers. Actual sandbox, reviewer,
permission profiles, workspace/temporary roots and secret controls still apply.

### Create one internal coordination chat

Only use this creation path for the selected internal provider and model. Apply
[coordination-chat scope](chats.md) before inspecting or choosing a creation surface.

1. Reconcile the existing protected record keyed by host, canonical folder and
   sprint before creation. Bind manager identity as an attribute, not a second
   allocation key. Save a durable protected pending creation intent using the
   actual [control integrity mode](qualification.md#actual-context-and-control-integrity), with ownership, selected provider/model/
   effort, current controls and source/brief identity. A task-folder mirror is
   evidence only. Missing acknowledgement or a crash requires reconciliation,
   never another `thread/start`.
2. Use the host's registered native provider ID; a workflow connection alias may
   map to a different ID. Call `thread/start` with explicit `modelProvider`,
   `model`, canonical `cwd`, the verified existing `projectId` when one is bound
   ([project and folder binding](#project-and-folder-binding-on-the-codex-host)),
   actual authorized `approvalPolicy`, the current `approvalsReviewer` when
   supported, named `permissions`, and
   `config.model_reasoning_effort`. For the observed persistent route set
   `allowProviderModelFallback: false` and `ephemeral: false`. Choose a supported
   history mode from this selected host/history evidence; do not universally force
   legacy. Check support for every field on the pinned host.
   Keep required workspace roots and integration controls consistent with the
   actual parent. Never combine named `permissions` with incompatible `sandbox`
   fields or change a global/default provider to get the desired model.
3. Save the acknowledged `thread.id` durably BEFORE any later native call,
   including naming, identity validation or an initialization turn. If saving
   fails, stop, preserve the acknowledgement evidence and reconcile without
   recreating. Compare returned provider/model/effort, folder and effective
   controls against the intended binding; record requested and observed values
   separately. An echo is not an independent serving-model attestation.
4. Set the title with `thread/name/set` on that exact ID. Send one small explicit
   readiness initializer through `turn/start`, authorizing only a known public
   answer and no tools. Use its actual initialization profile under
   [qualification](qualification.md); observed absence of tool use is not tool
   suppression or qualification of task permissions.
   Save the acknowledged turn ID before subsequent calls. Require that SAME turn
   to reach terminal `completed`, verify the exact public marker and item types,
   and confirm absence of tool items. `inProgress`, reasoning activity, delivery
   acknowledgement, empty output or another turn's completion is insufficient.
   Inspect reasoning item type only; do not persist hidden reasoning content.
5. Close the connection, reconnect to the validated existing daemon, initialize,
   and read that exact thread with `thread/read` and `includeTurns: false`.
   Verify ID, folder and metadata, then inspect supported bounded turn metadata
   using `thread/turns/list` (`itemsView: "notLoaded"`, explicit page limit and
   cursor). Match the saved initializer turn and terminal status. Distinguish
   durable history from whether a thread is currently loaded for execution.
   Supported discovery may confirm registration; neither read nor discovery
   proves GUI visibility. Obtain separate human confirmation of the exact chat
   and intended project/host in the GUI; pending visibility remains pending.

Generalized creation settings (illustrative placeholders, never literal launch
values; resolve all identities, controls and roots from trusted current records;
omit optional `projectId` unless verified):

```json
{
  "modelProvider": "REGISTERED_INTERNAL_NATIVE_PROVIDER_ID",
  "model": "AUTHORIZED_MODEL_ID",
  "cwd": "CANONICAL_PROJECT_ROOT",
  "projectId": "VERIFIED_EXISTING_PROJECT_ID",
  "approvalPolicy": "ACTUAL_AUTHORIZED_POLICY",
  "permissions": "AUTHORIZED_NAMED_INITIALIZATION_PROFILE",
  "config": {"model_reasoning_effort": "SUPPORTED_REQUESTED_EFFORT"},
  "allowProviderModelFallback": false,
  "ephemeral": false
}
```

### Sidebar discovery and existing-chat navigation

Различайте четыре наблюдения: exact ID доступен в выбранном хранилище;
он входит в отфильтрованный backend list; соответствует нужному проекту/хосту;
его строка видна в клиентской панели. Первые три по отдельности не доказывают
четвёртое. `notLoaded` не означает удаление истории. Отсутствие ID на ограниченной
странице с оставшимся cursor не доказывает отсутствие чата.

На фактически поддерживающем поля маршруте для диагностики provider-bound
чата явно задавайте `modelProviders: [NATIVE_PROVIDER_ID]`. Пропуск поля может
выбрать настроенного провайдера; `[]` означает всех провайдеров. `sourceKinds`
проверяется отдельно: источник берётся из сохранённых метаданных, а не угадывается
по транспорту. Не меняйте источник ради отображения. Для строгого readonly
списка используйте `useStateDbOnly: true`, когда фактические schema/route его
поддерживают: обычный список может восстанавливать метаданные из JSONL.
Используйте точный cwd, узкий searchTerm и конечную пагинацию; оставшийся cursor
означает неполную проверку. Поля, отсутствующие у wrapper, нельзя выдумывать или
подменять неизвестным RPC. Это не отменяет уже подтверждённый разрешённый native
маршрут с нужными возможностями. Учитывайте отдельно фильтры разных списков
клиента, например недавних и закреплённых чатов; один путь не доказывает другой.

В рамках уже разрешённой работы менеджер может проверить штатную навигацию
к существующему exact ID. Технически проверьте нужное хранилище/хост, отсутствие
ожидающего отправки ввода и, при использовании URL, установленный first-party
обработчик. Это проверка возможностей в рамках действующей авторизации;
повторный вопрос о разрешении не нужен, если действие уже ею покрыто.
[Документированный переход](https://learn.chatgpt.com/docs/reference/commands)
`codex://threads/<thread-id>` относится к локальному чату:
он не импортирует private store, не выбирает провайдера и не задаёт удалённый
хост. Наличие документации не подтверждает обработчик или GUI на данной машине;
для удалённого хоста используйте проверенную навигацию его проекта.

Штатная GUI-загрузка или resume самого открываемого ID возможны и фиксируются;
они сами по себе не требуют остановки, отсутствие сетевой активности не обещается.
В проверке только навигации не отправляйте сообщение, не начинайте model turn,
не создавайте новый ID и не меняйте хранилище/хост, provider/default/controls или
историю ради результата. Не инициируйте отдельный explicit resume только ради
видимости. Открытое содержимое в центре отличается от строки слева в нужном
проекте/хосте; GUI-видимость подтверждается отдельно по правилам выше.

Цель native-чата — сохранённый exact ID в хранилище выбранного клиента,
с нужной привязкой и видимостью. Владение процессом самим Desktop не является
обязательной предпосылкой. Новый one-shot owned-stdio unit существующего driver
с тем же основным native home может рассматриваться после проверки
runtime/store compatibility, provider override, frozen home/config/control/
environment и owned cleanup. Он не равен новому daemon/framework, но сам по
себе не доказывает GUI-совместимость. Не переносите старые private units в другой
home и не переигрывайте accepted/unknown операции. Другой private home, смена
global default, DB edit, rollout copy или неизвестный RPC не заменяют same-store
и GUI-проверку. Наличие `model` у creation wrapper без подтверждённого provider
resolver не доказывает привязку провайдера; фиксируйте конкретный недостающий
контракт. Дополнение поддерживаемого маршрута проходит применимые независимые
проверки до исполнения; backend persistence и FILE-проверки сохраняют свои границы.

### Bounded history reading

The selected bundled CodexDriver uses one exact-turn reader for readiness and
qualification reconnect. It starts with thread/items/list for the acknowledged
thread/turn, limit=1 and explicit sortDirection=asc. It accepts reviewed flat
items or wrappers carrying the matching turnId, exhausts bounded pages, validates
cursors and typed identities, and retains chronological message order. Public
readiness must match the original streamed digest; order is never guessed.

Only a matched typed NativeRPCError with exact code -32601 for that read permits
thread/turns/list(itemsView=full) fallback. The fallback scans bounded pages,
selects only the completed exact turn and validates duplicates/cursors. Other
codes, wrong IDs, malformed responses or transport uncertainty stop. Native error
messages/data are suppressed; -32602 does not establish project, quota or approval
failure. Matched rejection does not justify replaying a mutating operation.

`native_transport.NativeRPCError` уже предоставляет `method`, `request_id`,
`rpc_code` и `category` после проверки совпадения ответа с запросом. Код `-32600`
имеет category `matched_rejection`: это отказ конкретного запроса, не доказательство
неподдерживаемости сервера/host, STEP_INCOMPLETE, квоты или первопричины сбоя.
Код `-32601` имеет category `unsupported_method` только для точного method на
фактическом маршруте, а не для всего host. Локальный `unsupported_rpc` до отправки
означает описанное выше ограничение whitelist helper, не ответ сервера. Правила
безопасной записи диагностики и дальнейших действий принадлежат
[operations](operations.md#recover-from-the-observed-outcome).

The 1 MiB transport frame guard remains. If even one item exceeds it, report the
bounded-read failure; never mark a partial inventory complete, resume/mutate
history to read it, or replace the chat. Adapter history support cannot repair a
Desktop application's own loader. Preserve existing IDs and copies and state UI
compatibility limits separately.

### Deliver to the exact existing chat

Read trusted receipts and current ownership/authorization first. Use the known
native ID; no fuzzy title match, fork, database edit, provider change or default
change can substitute for it. Retain every previous intent, acknowledged ID and
unknown outcome. Check current pauses, dependencies, host controls and supported
active-turn metadata before a mutating call.

After the client closes, an exact persistent chat can return `notLoaded`.
If bounded reconciliation establishes that there is no conflicting active turn,
call `thread/resume` with that SAME `threadId`, frozen `modelProvider`, `model`,
canonical `cwd`, `config.model_reasoning_effort`, current actual `approvalPolicy`,
reviewer and authorized TASK permission reference/required roots. For the bundled
schema-2 direct builtin selector and task-local alias correction, follow
[the actual-context mapping](qualification.md#actual-context-and-control-integrity). Use
`excludeTurns: true`; do not supply replacement `history` or a storage `path`.
Verify the returned ID/settings and save the acknowledgement, then send the
newly authorized text with `turn/start` on that SAME open connection. A resume
on a connection that closes before sending does not establish a loaded context
on another connection. Preserve the binding and current task controls for the
turn (including explicit `model` and supported `effort`); never restore the
legacy restricted initializer profile for substantive authorized work. This restores
existing session load, not permission, capability or tool qualification.

For an existing active turn, use the independently supported host control
channel and `turn/steer` with the exact `threadId`, `expectedTurnId` and authorized
input. A mismatched ID is a conflict, not a reason to bypass the precondition.
Deliberate `turn/start` can steer the same active chat ONLY where those semantics
are supported and qualified for the actual host/version and intended operation.
It is not a universal fallback for failed steering. The bundled locked foreground
worker journal still does not expose concurrent steering through another CLI
command merely because these underlying RPC methods exist.

Save each delivery acknowledgement and returned turn ID separately from public
response, terminal outcome, artifact production, QA and task acceptance. Observe
only the acknowledged exact turn; do not infer completion from an idle thread,
accepted message, timer observation or unrelated result. Preserve an unknown
acknowledgement without replay. A new explicit human-authorized follow-up may
be sent after exact-chat reconciliation with its own intent; preserve the old
unknown receipt and describe the new message as a follow-up, never a retry.
No automatic unknown-request replay, duplicate chat/worker, fallback provider,
permission widening, session-database change or shared-daemon shutdown is allowed.
Secret filtering, no-tools separation, denials, cleanup ownership and independent
review remain in force under [routing](routing.md), [qualification](qualification.md)
and [operations](operations.md).

### Bundled Codex route selection

Use the [portable setup chain](setup.md#portable-setup-chain) for the selected
native provider/auth, `@runtime:ID`, reviewed pin, actual inherited `CODEX_HOME`
and task-local native-chat/driver binding. Text connection success does not
establish native wire compatibility. The following is the implemented bundled
driver's selection contract; it does not expand the separate manual shared surface.

Selection happens **before new allocation**. With `connection: "owned-stdio"`,
select the pinned owned process. On Linux, `auto`/`shared-unix` performs bounded
read-only daemon discovery; it does not start a daemon:

| Discovery observation | Pre-allocation disposition |
| --- | --- |
| Known unavailable/unqualified daemon, version mismatch or not running | `auto` may select pinned owned-stdio; explicit shared-unix fails `shared_unavailable`. |
| Missing/empty advertised executable, or an absolute advertised file proven missing by FileNotFoundError | Shared is unselectable before socket contact; `auto` records `shared_daemon_advertisement_incomplete` / `shared_daemon_runtime_missing` and selects pinned owned-stdio. Explicit shared fails. |
| Malformed/oversize discovery, invalid field/path shape, wrong executable bytes, unreadable path or uncertain identity | Fail `daemon_identity_unknown`; no fallback after ambiguity. A broad missing_path error is not proof of FileNotFoundError. |
| Qualified running daemon with pinned executable and valid socket | Select shared-unix, then retain all peer and effective-config checks. |
| Explicit shared-unix outside Linux | Fail `unsupported_shared_transport`. `auto` can select the implemented owned route, subject to its own OS/runtime/control/cleanup prerequisites; this is not evidence that it works on that host. |

Shared always requires current-user socket ownership, protected nonsymlink
ancestors, `SO_PEERCRED` UID,
`/proc/<peer-pid>/exe` SHA256 and verified WebSocket upgrade. Missing advertisement
never permits bypassing these checks. After opening, before turns, verify effective
endpoint/wire, actual approval/reviewer/permission mapping, disabled integrations,
closed shell environment and admitted profiles. Both effective
`request_max_retries` and `stream_max_retries` must be **0**. If shared cannot
retain task-scoped retry 0, it stays blocked with `native_retry_mismatch`; do not
relax it or change daemon globals/defaults. An explicitly chosen supported
owned-stdio binding may apply launch overrides for a NEW allocation only.

A retained accepted, unknown, active or migrating operation keeps its original
route and owner. A cached `owned-stdio` route name is not a live owner/handle:
opening a new owned process, even of the same kind, is forbidden. Only the exact
known original shared owner may be reconnected while still qualified; an
unbound/missing/uncertain owner blocks before any transport constructor with
`native_reconciliation_required`. Reconcile existing evidence under
[operations](operations.md); never reroute/replay it as recovery. Owned foreground
lifetime requires actual verified kernel-cleanup proof and an unchanged environment
binding; failed cleanup remains unknown. Shared cleanup closes only this connection.
The owned implementation requires Linux subreaper/pidfd/waitid support or the
Windows private Job mechanism and its actual membership/cleanup checks. Absence
of that mechanism blocks that route on the actual host; neither source presence
nor Linux evidence qualifies Windows, another OS or a different host surface.

### Optional pinned model catalog

Codex drivers may opt into `native_model_catalog` with exactly `path`,
`final_sha256` and `source_entry_sha256`. Use a protected anchored `path` resolved
by PathContext; no catalog, instructions template or runtime ships in the package.
Trusted host setup binds its actual runtime and full source entry separately:
the source-entry hash establishes entry identity, not PE/ELF provenance.

Prepare the catalog from that full entry by changing only `tool_mode` from
`code_mode_only` to `direct`. The bounded JSON must contain exactly one selected
model `slug`. Validation reverses that one field and hashes the complete entry
using the existing `native_sprint.digest()` canonical JSON format (sorted keys,
UTF-8, ensure_ascii=False, allow_nan=False, compact comma/colon separators).
All other fields, including the complete instructions_template, must match the
trusted source-entry hash. Final file bytes must match final_sha256. Duplicate
JSON keys, invalid UTF-8/JSON, more than MAX_JSON bytes, nesting beyond 64 levels,
unknown/missing selected entries, aliases or mismatched pins fail before allocation.

The conditional catalog record joins the existing immutable binding and frozen
snapshots, checked before every opening. Owned launch passes its absolute pinned
reference through the existing TOML encoder as `-c model_catalog_json=...`.
The same single config/read rejects a visible conflicting reference; null or
unexposed means UNKNOWN. A matching reference does not prove loading or FILE use.
Absent record adds no catalog override or null/default binding fields and keeps
the old route; this does not migrate stored journals across changed module pins.
This field is Codex-only, distinct from Claude settings and auth dependencies.
See the [Byesu recipe](setup.md#byesu-with-the-existing-text-and-codex-routes).

### File capability and exact tool evidence

For ordinary Codex schema2, diagnose capability from the implemented selected
native-chat route, effective actual controls, bounded exact-turn typed history
and independent disk-byte verification. Current structural/operation checks
apply; no native-probe/native-qualify ceremony or synthetic history is required.
A tool-free initializer, catalog entry or permission selector proves no file use;
the supported catalog has no per-chat apply_patch availability field. Do not
invent a tools/list API. A separately authorized real task can establish use;
that is model execution, not a non-invasive inspection or a mandatory bootstrap.

A permitted shell read/write/reread with verified disk bytes demonstrates general
file-change capability. An exact native `apply_patch` requirement additionally
needs verified native file-change history for the intended path and independent
disk verification. A completed `fileChange` is valid; an optional same-ID
`functionCallOutput` named `apply_patch` pair is also allowed, not mandatory for
every fileChange. Shell-only `commandExecution`, prose claims or an unchanged
fixture do not satisfy that exact requirement or prove host-wide unavailability.
Report the requested tool and actual observed surface with its limitation; do
not relabel shell writes, synthesize fileChange items, silently substitute or
replay. Interpret relative paths against the actual task cwd when checking disk
results. Schema1/Claude keep their separate evidence and capability boundaries.

### Evidence and host capability limits

Record creation, terminal public initializer/item checks, reconnect persistence,
exact-chat delivery and human GUI confirmation as separate observations. Short
text/creation does not qualify tools or full assignment execution; requested and
returned profile settings do not independently attest serving model/effort.
A source transport/proxy failure concerns that route/request, not general provider
incapability. Preserve the receipt/unknown outcome; do not replay or weaken controls.

| Host / route | Actual requirement / limit |
| --- | --- |
| Linux shared daemon + installed UnixWebSocket/RPC | Discover actual pinned runtime/socket and validate peer; establish persistent identity/reconnect and supported exact-ID delivery. Tools and active steering require their own route-specific evidence. |
| Bundled Codex worker driver | Schema 1 retains its bounded contract. Schema 2 preserves actual builtin full-access and actual approval/network, including never with unknown reviewer, uses ordinary current structural/operation checks without historical qualification; see [ordinary execution](qualification.md#ordinary-codex-schema2-execution). Manual text creation proves no file capability. |
| Owned stdio / JSONL proxy | Use only the actually implemented compatible binding with its actual controls and owned kernel cleanup. Selection is before allocation; retained accepted/unknown work cannot acquire a new owner. |
| Windows shared host | Establish actual supported Windows transport and peer validation independently. This installed Unix transport is Linux-only; no fake Unix socket/path conversion or inherited Linux qualification. |
| Other host/provider binding | Actual controls, authorized provider, implemented driver and independent evidence are required; no qualification inherited from another route's text test. |

Retain [existing execution binding](chats.md#existing-session-configuration) and
explicit legacy/diagnostic evidence separately from ordinary sessions. Common [review gates](routing.md) and
[acceptance/intake](lifecycle.md#engineering-and-acceptance) apply to changes;
these instructions grant no runtime/control change or author self-acceptance.
