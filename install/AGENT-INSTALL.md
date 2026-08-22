# pilotfish — Legacy Global Agent Install Runbook

> This document is written for an AI agent (Claude Code) performing the installation on a user's machine. If you are that agent: follow the steps in order, never skip the approval gate in Step 2, and prefer merging over overwriting at every point. A human can follow the same steps by hand.

> New macOS users can use the [Claude Code Plugin beta](./PLUGIN-INSTALL.md) instead. The Plugin and this legacy global installation must not coexist.

## What you are installing

pilotfish is a global multi-model orchestration layer for Claude Code. It touches exactly three places, all under the Claude Code configuration root — written `$CFG` throughout this runbook and resolved in [Step 0](#step-0--resolve-the-configuration-root):

| Target | Change |
|---|---|
| `$CFG/settings.json` | Set `model` to `"opus"`, add `fallbackModel`, conditionally extend `availableModels` |
| `$CFG/agents/` | Install eight role agent files: `scout.md`, `Explore.md`, `plan-verifier.md`, `security-reviewer.md`, `mech-executor.md`, `executor.md`, `verifier.md`, `security-executor.md` |
| `$CFG/CLAUDE.md` | Insert one `## Orchestration` section between `<!-- pilotfish:begin -->` and `<!-- pilotfish:end -->` markers |

Source of truth for the files: the [templates/](../templates/) directory of this repository. If you are running inside a local clone, use those files directly; otherwise fetch each from `https://raw.githubusercontent.com/Nanako0129/pilotfish/main/templates/...`.

> ⚠️ **Commit pinning:** If the user's install prompt referenced this runbook at a specific commit SHA instead of `main`, fetch **every template from that same SHA** — never fall back to `main`. The point of pinning is that what the user reviewed is exactly what gets installed.

> **Portability:** Prefer your own Read / Write / Edit tools over shell commands for all file operations — they behave identically on macOS, Linux, WSL, and native Windows. The bash snippets below are references, not requirements: on native Windows (PowerShell, no Git Bash) they will not run — create directories and copy backups with your file tools, count markers by reading the file, and if `jq` is unavailable validate JSON by parsing it yourself.

## Step 0 — Resolve the configuration root

Claude Code reads global configuration from `~/.claude/` **only when `CLAUDE_CONFIG_DIR` is unset**. When that variable is set, every path in this runbook lives under it instead:

> `CLAUDE_CONFIG_DIR` — Override the configuration directory (default: `~/.claude`). All settings, session history, and plugins are stored under this path […]
> — [Claude Code environment variables](https://code.claude.com/docs/en/env-vars)

Resolve it before reading or writing anything, and use the printed path verbatim as `$CFG` for the rest of this runbook:

```bash
echo "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
```

> ⚠️ **Do not assume `~/.claude`.** On a machine where `CLAUDE_CONFIG_DIR` points elsewhere, installing into `~/.claude/` *creates* that directory, passes every check in Step 4, and installs nothing Claude Code will ever load — a silent no-op with no error to explain it. The same mistake makes an upgrade look like a fresh install (no markers found in the decoy directory) and makes an uninstall delete the decoy while leaving the real install in place.

Carry the resolved path into the Step 2 plan so the user can catch a wrong root before anything is written.

> ⚠️ **Do not normalize the value.** Claude Code does not expand a leading `~` inside `CLAUDE_CONFIG_DIR`, and it resolves a relative value against the current working directory. Observed on 2.1.220: with `CLAUDE_CONFIG_DIR='~/.claude-probe'` it creates a directory named literally `~` under the cwd, and with `CLAUDE_CONFIG_DIR='.claude-probe'` it uses `$PWD/.claude-probe`. Rewriting either value into `$HOME/...` installs into a directory Claude Code never reads — the exact failure this step exists to prevent. Use the value as Claude Code sees it.

If the resolved root is not absolute, **stop and tell the user** their `CLAUDE_CONFIG_DIR` is almost certainly misconfigured: a relative root moves with whatever directory the shell happens to be in, so their configuration is already split across every cwd they have launched `claude` from. Let them fix the variable; do not guess an absolute path on their behalf.

## Updating an existing install

When the user asks to **update** (rather than fresh-install), run this before Step 1:

1. Detect the installed version: search `$CFG/CLAUDE.md` for `pilotfish v` inside the marker block. A version comment like `<!-- pilotfish v1.1.0 -->` gives the installed version; **markers present but no version comment means a pre-v1.1.0 install** (update recommended).
2. Fetch the latest version and changelog from the same ref you were invoked from (`VERSION` and `CHANGELOG.md` at the repo root — e.g. `https://raw.githubusercontent.com/Nanako0129/pilotfish/main/VERSION`).
3. If already up to date, say so and stop. Otherwise show the user the changelog entries between their version and the latest, then proceed with Steps 1–4 below — the install is idempotent, so an update is just a re-run: unchanged files are skipped, the policy block is replaced in place, and settings keys are only touched if missing.
4. If the user customized any agent file, the Step 3.3 diff will surface it — never overwrite a customization without showing the diff and asking.

## Step 1 — Preflight (read-only)

Gather the current state before proposing anything:

1. Run `claude --version` and parse its semantic version. pilotfish requires **Claude Code 2.1.219 or newer** as its tested floor for Opus 5-aware alias routing; this is also newer than the verified baseline that enforces agent `tools` allowlists. The version floor does not guarantee one exact backend for every provider, account, or settings stack. If the command is unavailable, its version cannot be parsed, or it reports an older version, **stop before presenting a write plan or changing anything** and ask the user to update Claude Code. Do not install a prompt-only approximation: `plan-verifier` and `security-reviewer` depend on enforced tool exclusion to preserve the pre-approval read-only boundary.
2. Read `$CFG/settings.json` (note the current `model`, and whether `fallbackModel` / `availableModels` exist). If the file is missing, you will create a minimal one.
3. Read `$CFG/CLAUDE.md` if it exists. Check for existing `<!-- pilotfish:begin -->` / `<!-- pilotfish:end -->` markers — their presence means this is an **upgrade**, not a fresh install.
4. List `$CFG/agents/` and note which of the eight pilotfish filenames already exist. **Also read the `name:` frontmatter of every existing agent file (any filename)** — Claude Code resolves collisions by the `name` field, not the filename, and loads only one definition per name. If any existing agent already declares `name: scout`, `Explore`, `plan-verifier`, `security-reviewer`, `mech-executor`, `executor`, `verifier`, or `security-executor`, flag it as a name collision in the plan and ask the user whether to rename theirs, skip that pilotfish role, or overwrite. Likewise note any enabled **plugin** that ships agents with these names — a user-level file shadows the plugin's version (still reachable via its scoped `plugin:name`).
5. Check whether the environment variable `CLAUDE_CODE_SUBAGENT_MODEL` is set (`echo "$CLAUDE_CODE_SUBAGENT_MODEL"`).

> ⚠️ **Warning:** If `CLAUDE_CODE_SUBAGENT_MODEL` is set, it silently overrides every per-agent `model` frontmatter and defeats the entire tiering design. Flag it in your plan and recommend unsetting it. Do not unset it yourself without approval.

## Step 2 — Present the plan and get approval

State the resolved `$CFG` from Step 0 above the table, then show the user a table of every change you intend to make: each file, the exact modification, and whether it is a create / merge / replace-between-markers / skip. Include a backup line (Step 3.1). **Do not write anything until the user approves.**

## Step 3 — Apply

### 3.1 Backup and directories

```bash
CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"   # Step 0
mkdir -p "$CFG/backups" "$CFG/agents"
# settings backup: FIRST install only — the pristine pre-pilotfish state must be preserved
ls "$CFG"/backups/settings.json.pilotfish-* >/dev/null 2>&1 || \
  cp "$CFG/settings.json" "$CFG/backups/settings.json.pilotfish-$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
# CLAUDE.md backup: every run
cp "$CFG/CLAUDE.md" "$CFG/backups/CLAUDE.md.pilotfish-$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
```

> **Note:** If `$CFG/settings.json` did not exist before this install (fresh machine), there is no settings backup — record in your final summary that the pre-install state had **no `model` key**, so a future uninstall knows to *remove* the key rather than restore a value.

### 3.2 settings.json — merge, key by key

Never rewrite the whole file; edit only these keys and preserve everything else:

| Key | Rule |
|---|---|
| `model` | If absent → set `"opus"`. If present and different → **ask** the user: keep their value, or switch to `"opus"` (a provider-resolved family alias; the isolated Claude Code 2.1.219 first-party Gate observed Opus 5, but exact resolution can vary by provider, account, and settings). Never replace an existing `best`, `fable`, full model ID, or other user choice without approval. If already `"opus"` → no change. |
| `fallbackModel` | If absent → add `["sonnet"]` (handles primary-model overload/unavailability). If present → leave it and note it in the summary. |
| `availableModels` | **Only if the key already exists** (it is an allowlist): ensure it contains `"opus"`, `"fable"`, `"sonnet"`, `"haiku"`, and the chosen main-model value — append whatever is missing. This keeps the documented `/model fable` opt-in reachable. If the key is absent → do not add it (absent = unrestricted, which is fine). |

Validate afterwards: `jq empty "$CFG/settings.json"`.

> **Note:** `opus` is a family alias, not a full model pin; it follows the provider's current Opus version. Users can opt into Fable 5 with `/model fable`, or choose `"opus[1m]"` when they explicitly need the documented 1M alias. pilotfish does not replace those choices on later installs without approval.

### 3.3 Agent files

For each of the eight files in `templates/agents/`, write it to `$CFG/agents/<same-name>.md`:

| Existing state | Action |
|---|---|
| File doesn't exist, no `name:` collision (Step 1.3) | Write it |
| File exists, identical content | Skip (report as up-to-date) |
| File exists, different content | Show the diff, ask: overwrite (upgrade) or keep theirs |
| A *different* file declares the same `name:` | Stop and ask (see Step 1.3) — never install a second file with a duplicate `name` |

> **Note:** A user-level agent named `Explore` intentionally shadows Claude Code's built-in Explore subagent to pin exploration to Haiku. This is expected, not a conflict.

### 3.4 CLAUDE.md policy section

The canonical section content is [templates/claude-md.orchestration.md](../templates/claude-md.orchestration.md) — it already includes the begin/end markers.

Before writing, count the markers: `grep -c "pilotfish:begin" "$CFG/CLAUDE.md"`. The count must be `0` (fresh) or `1` (upgrade).

| Marker count | Action |
|---|---|
| File missing | Create it with the section as its content |
| `0` | Append the section at the end (or after the first `#` heading if the file has one — either is fine) |
| `1` | Replace exactly that one block, from its `<!-- pilotfish:begin -->` through its matching `<!-- pilotfish:end -->` inclusive (idempotent upgrade) |
| `>1` | **Stop and ask the user** — do not blind-replace; a greedy first-begin-to-last-end replacement could delete user content sitting between two marker pairs |

Do not modify anything outside the markers.

## Step 4 — Verify and hand off

1. Every path you wrote is under the `$CFG` resolved in Step 0. Re-run `echo "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"` and compare it against your Step 2 plan. The three checks below cannot catch a wrong root: they inspect whichever directory you just wrote to, so they pass either way.
2. `jq empty "$CFG/settings.json"` exits 0.
3. `ls "$CFG/agents/"` shows all eight files.
4. The markers appear exactly once in `$CFG/CLAUDE.md`: `grep -c "pilotfish:begin" "$CFG/CLAUDE.md"` prints `1`.
5. Read the installed policy block and verify that it says existing named roles are invoked without `model`, while only truly ad-hoc agents with no named role definition receive an explicit invocation model.
6. Tell the user to **restart their Claude Code session**: the agents directory is scanned at session start, and the `model` setting applies on restart. After restart, `/model` should show the new default, and asking Claude "which subagent types are available?" should list the eight roles (scout, Explore, plan-verifier, security-reviewer, mech-executor, executor, verifier, security-executor). On Claude Code before 2.1.198 you can also run `/agents` to see them; that wizard was removed in 2.1.198.
7. Summarize what changed, what was skipped, and where the backups are.

## Uninstall

On request, reverse the three targets:

1. Delete the eight files from `$CFG/agents/` (only ones whose content matches pilotfish templates — show a diff first if they were customized).
2. Remove the block from `<!-- pilotfish:begin -->` through `<!-- pilotfish:end -->` (inclusive) in `$CFG/CLAUDE.md`; delete the file only if that leaves it empty and the user confirms.
3. In `$CFG/settings.json`: restore `model` from the **oldest** `settings.json.pilotfish-*` backup in `$CFG/backups/` — that file is the pre-install state (Step 3.1 only ever backs up settings once, on first install). If no such backup exists, or the backup has no `model` key, **remove** the `model` key instead of leaving the pilotfish value. Remove `fallbackModel` if the user doesn't want it. Leave `availableModels` additions in place unless asked — they are harmless.
