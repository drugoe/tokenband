# Portable paths and runtime discovery

Core settings resolve from absolute WORKFLOW_HOME, otherwise the current user's
home plus .tokenband. Fresh installations use that new default.
For an existing installation, preserve the exact original workflow home, config
path and bytes, credentials, anchored references, receipts and uncertainty records.
Do not copy the config into a new default: its parent identifies receipt storage.
The host's user-level workflow instructions must retain the original absolute
WORKFLOW_HOME for every optional worker/API invocation, including --config calls;
preserve already-frozen task-specific WORKFLOW_HOME/--config pairs. This is a
process-scoped selection, not a global environment or provider change.

Before publishing an upgraded skill, the authorized installer places an empty
regular PRESERVE-EXISTING-STATE file under the new default .tokenband directory,
without creating a config, results or receipt store there. Any existing marker
or marker symlink blocks implicit default selection with existing_state_binding;
the worker never reads its contents or redirects state. Select the original
explicit WORKFLOW_HOME recorded in user-level instructions. The current CLI
resolves its default before parsing --config, so --config alone (and --help)
also requires that explicit home on an upgraded host. Fresh users without the
marker use .tokenband normally. Archive superseded installed skills outside all
skill-discovery roots with exact-byte backups and owned rollback; retain
required physical state paths and historical proof. Never alias an old skill
with a symlink, move live state or inherit old exact native qualification.

 The skill root comes from worker.py's location;
the task root is the explicit working folder. Preserve both lexical and physical
path identities for every permission check and frozen invocation.

Use anchored string references in settings:

| Reference | Meaning |
| --- | --- |
| @workflow_home/relative/path | Shared user settings and protected control data |
| @config/relative/path | Location relative to the selected configuration file |
| @skill/relative/path | File bundled with this skill |
| @home/relative/path | User-specific installed resource |
| @python | Current supported native Python interpreter, interpreter field only |
| @runtime:ID | Configured pinned native runtime, native consumer field only |

Suffixes use forward slashes. Reject traversal, empty segments,
drive/UNC/alternate-stream syntax and invalid host names. Never evaluate or expand
shell/environment expressions in anchored suffixes: $ and % remain literal path
characters, subject to the same containment checks. An anchored
reference must stay within its physical anchor even across symlink/junction
ancestors. Changing an anchor or resolved identity after selection blocks launch.
Legacy absolute user settings remain readable; new setup uses portable references.

Runtime IDs and candidate/command lists belong to user configuration. Search
configured candidates first, then qualified PATH directories. Inspect native
PE/ELF files without executing them during discovery. Verify the reviewed SHA256
and protected location; never adopt new bytes merely because their filename or
reported version looks newer. Wrappers, scripts, aliases and unknown executables
remain unqualified. Discovery does not install runtimes or grant provider access.

Structural validation can succeed on another OS. doctor checks connection
references, external adapters and optional legacy metadata configuration only;
native-driver paths/pins/readiness require the [setup checklist](setup.md) and
the selected driver's fail-closed preflight. No doctor result qualifies a host. Keep credentials,
control evidence and receipts outside all real task writable/temporary roots.
An unavailable home anchor is a setup prerequisite when that anchor is needed.
