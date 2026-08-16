# Antigravity Lifecycle Hooks Specification

> **Source of Truth:** [Google Antigravity Official Hooks Documentation](https://antigravity.google/docs/hooks/)  
> **Schema Version:** Antigravity 2.0 / `agy` CLI  

Lifecycle hooks allow external shell commands or scripts to execute at deterministic lifecycle points in the Antigravity agent execution loop. This document serves as the authoritative specification for hook configuration, payload schemas, event types, and gating contracts.

---

## 1. Configuration & Discovery

Hooks are defined in a JSON object file named `hooks.json`.

### Discovery Locations & Precedence:
1. **Workspace Plugin:** `<workspace>/.agents/plugins/<plugin_name>/hooks.json`
2. **Workspace Root:** `<workspace>/.agents/hooks.json`
3. **Global Plugin:** `~/.gemini/config/plugins/<plugin_name>/hooks.json`
4. **Global Root:** `~/.gemini/config/hooks.json`

### Top-Level Manifest Structure (`hooks.json`):
```json
{
  "<hook-name>": {
    "enabled": true,
    "PreToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python scripts/eval_guard.py",
            "timeout": 15
          }
        ]
      }
    ],
    "PostToolUse": [],
    "PreInvocation": [],
    "PostInvocation": [],
    "Stop": []
  }
}
```

* **`enabled`** *(boolean, optional, default: `true`)*: Enables or disables the hook bundle.
* **Merging**: Multiple named hook bundles across active plugins are merged and executed sequentially.

---

## 2. Event Types & Matchers

| Event | Fired When | Matcher Scope | Handler Structure |
| :--- | :--- | :--- | :--- |
| **`PreToolUse`** | Before a tool executes. Used for gating, blocking, or argument rewriting. | Regex matching tool name (e.g. `.*`, `run_command`, `run_command\|view_file`) | Grouped (`matcher` + `hooks`) |
| **`PostToolUse`** | After a tool completes. Used for linters, formatting, and audit trails. | Regex matching tool name | Grouped (`matcher` + `hooks`) |
| **`PreInvocation`** | Before the model is called. Used to inject prompt context. | N/A (Ignored) | Flat list of handlers |
| **`PostInvocation`** | After tool calls finish. Used to evaluate output or force loop continuation. | N/A (Ignored) | Flat list of handlers |
| **`Stop`** | When the agent execution loop terminates. Used to prevent premature stopping. | N/A (Ignored) | Flat list of handlers |

### Matcher Rules
* The `matcher` string is compiled as a standard **regular expression**.
* `"matcher": ".*"` or `""`: Matches all tool names.
* `"matcher": "run_command"`: Matches exact tool name `run_command`.
* `"matcher": "run_command|write_to_file"`: Matches either tool.
* `"matcher": "browser_.*"`: Matches any tool starting with `browser_`.
* *(Note: Avoid bare `*` as regex engines will reject it as an invalid quantifier).*

---

## 3. Hook Handler Definition

Each handler object within a `hooks` array supports:

* **`type`** *(string, optional, default: `"command"`)*: Currently, `"command"` (shell execution) is supported.
* **`command`** *(string, required)*: The command string to execute (`cmd /c` on Windows, `sh -c` on Unix). `~` expands to the user home directory. The working directory is set to the directory containing `hooks.json`.
* **`timeout`** *(integer, optional, default: `30`)*: Timeout in seconds.

---

## 4. Input & Output Contracts (IPC over Stdin/Stdout)

All JSON keys use **`camelCase`** (protojson encoding).

### Common Inbound Metadata (sent on `stdin` to all hooks):
```json
{
  "conversationId": "4db1fa9e-1285-4dc7-9534-e0d74e9a9d88",
  "workspacePaths": ["/path/to/project/antigravity-auto-mode"],
  "transcriptPath": "~/.gemini/antigravity/brain/.../transcript.jsonl",
  "artifactDirectoryPath": "~/.gemini/antigravity/brain/...",
  "modelName": "auto",
  "stepIdx": 5
}
```

---

### Contract 1: `PreToolUse`

#### Input (`stdin`):
```json
{
  "toolCall": {
    "name": "run_command",
    "args": {
      "CommandLine": "echo hello",
      "Cwd": "/path/to/project/antigravity-auto-mode"
    }
  },
  "stepIdx": 5,
  "conversationId": "4db1fa9e-1285-4dc7-9534-e0d74e9a9d88"
}
```

#### Output (`stdout`) - Safe Action (Allow):
```json
{
  "decision": "allow",
  "reason": "Shieldstral: Safe execution approved (P(Unsafe)=0.00 < 0.20)"
}
```

#### Output (`stdout`) - Unsafe / Dangerous Action (Force Confirmation):
```json
{
  "decision": "force_ask",
  "reason": "Shieldstral: Potential safety violation detected (P(Unsafe)=0.95 >= 0.20)"
}
```

#### Internal Go / Protobuf Struct Definition
Discovered directly in `agy.exe` (`google3/third_party/jetski/hooks_pb/hooks.proto`):

```protobuf
message PreToolHookResult {
  string decision = 1;                      // "allow" | "deny" | "ask" | "force_ask" | "deny_unless_prior_grant"
  string reason = 2;                        // User-facing explanation string
  google.protobuf.Struct overwrite = 3;     // Shallow argument modifications
  repeated string permission_overrides = 4; // Custom permission strings for "ask"
  bool allow_tool = 5;                      // Boolean tool execution grant
  string deny_reason = 6;                   // Rejection explanation
}
```

#### Detailed Field Specifications:

* **`decision`** *(string, required)*:
  * `"allow"`: Automatically approves tool execution in the agent engine without blocking.
  * `"deny"`: Hard blocks tool execution immediately (returns rejection error to the agent).
  * `"ask"`: Prompts the user for manual confirmation (respects cached permissions).
  * `"force_ask"`: Always prompts the user, ignoring any cached approvals or session grants.
  * `"deny_unless_prior_grant"`: Denies execution unless the specific resource permission was already granted in a prior step.

* **`reason`** *(string, optional)*:
  Explanatory message displayed to the user or recorded in session transcripts.

* **`permissionOverrides` / `permission_overrides`** *(array of strings, optional)*:
  * **Internal Description:** `"If decision is 'ask', requests these standard permission resource strings instead of default."`
  * **Behavior:** When `decision: "ask"` is returned, this field allows the hook to specify custom permission resource strings (e.g. `["command(npm test)"]`, `["file_write(src/index.ts)"]`) in the prompt dialog instead of the default generic permission prompt.
  * *Note:* When `decision: "allow"`, the engine grants tool execution directly via the `decision` field.

* **`overwrite`** *(object, optional)*:
  A shallow top-level key-value map merged over tool arguments before execution.

* **`allow_tool` / `allowTool`** *(boolean, optional)*:
  Internal protobuf field indicating direct tool execution authorization.

* **`deny_reason` / `denyReason`** *(string, optional)*:
  Internal rejection reason used when tool execution is denied.

---

### Contract 2: `PostToolUse`

#### Input (`stdin`):
```json
{
  "toolCall": {
    "name": "run_command",
    "args": { "CommandLine": "npm test" }
  },
  "stepIdx": 6,
  "error": "exit status 1"
}
```

#### Output (`stdout`):
```json
{}
```

---

### Contract 3: `PreInvocation`

Used to inject dynamic context or ephemeral guidelines before LLM generation.

#### Output (`stdout`):
```json
{
  "injectSteps": [
    {
      "ephemeralMessage": "Remember to run tests before completing the turn."
    }
  ]
}
```

---

### Contract 4: `PostInvocation`

#### Output (`stdout`):
```json
{
  "injectSteps": [],
  "terminationBehavior": "force_continue"
}
```
* **`terminationBehavior`**: `"force_continue"` | `"terminate"` | `""`

---

### Contract 5: `Stop`

Fires when the agent execution loop attempts to terminate.

#### Output (`stdout`):
```json
{
  "decision": "continue",
  "reason": "Background tasks are still in progress. Awaiting completion."
}
```
* **`decision`**: `"continue"` blocks agent stop; any other value allows normal completion.

---

## 5. Execution Surface Behavior: CLI vs. Desktop IDE

The Antigravity ecosystem has two primary execution surfaces that interact with hooks:

### A. Antigravity CLI (`agy`)
* In the CLI interface, `PreToolHookResult` directly governs tool execution.
* When `decision: "allow"` is returned by the hook, `agy` executes the command **immediately with zero interactive prompts**.
* When `decision: "ask"` is returned, `agy` renders a prompt in the terminal asking the user to confirm.

### B. Antigravity Desktop App / IDE (Electron GUI)
* The Desktop App contains two distinct security layers:
  1. **Backend Agent Engine (Cortex in `agy.exe`)**: Consumes the hook's `PreToolHookResult` and approves the tool step.
  2. **Frontend UI Security Manager**: Governs interactive UI confirmation cards for terminal commands based on the active IDE Security Preset (`Default`, `Full Machine`, etc.).
* Even when the backend agent engine approves an action via `decision: "allow"`, the Desktop IDE's UI layer may still display a confirmation card if the IDE's terminal execution policy is configured to require user confirmation in the chat interface.

---

## 6. Best Practices for Hook Implementations

1. **Always Exit With Status Code `0` (Antigravity 2.0)**: In Antigravity 2.0, exiting with a non-zero status code (e.g., `1`) causes the hook runner to treat the execution as a process crash and discard the `stdout` JSON payload. All gating decisions (`allow`, `force_ask`, `deny`, and fail-closed fallbacks) must be communicated via the `stdout` JSON payload with a clean exit code `0`.
2. **Non-Blocking Stdin Consumption**: Read incoming single-line JSON via `sys.stdin.readline()` first to prevent deadlocks on open pipes.
3. **Valid Regex Matchers**: Always use `".*"` instead of bare `"*"` to ensure cross-platform regular expression compatibility.
4. **Fast-Path Caching**: Hash static safe actions (`tool + args`) via SHA-256 to achieve $< 2\text{ ms}$ evaluation latency.

