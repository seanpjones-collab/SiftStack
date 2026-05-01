# Claude Code Setup for SiftStack

This folder ships project-local Claude Code config so anyone working on SiftStack gets the same skills + accumulated project memory automatically.

## What's here

- **`skills/`** — 13 REI skills (buyer-prospector, real-estate-comping, rehab-estimator, deal analysis, market research, etc.). Claude Code loads these automatically when you open this repo.
- **`memory/`** — 43 project-memory `.md` files plus `MEMORY.md` index. These are the accumulated facts/feedback/decisions from prior sessions (Ty's curriculum, Sean's defaults, hard-won OH pipeline learnings, etc.). Claude Code's auto-memory system needs these copied to a per-user path to load them automatically — see setup below.

## First-time setup (new machine)

### 1. Skills — already work, no setup needed
Project-local skills load automatically from `.claude/skills/` when Claude Code starts in this repo. Verify with `/help` or by triggering one (e.g., "audit this call" should hit `call-audit-skill`).

### 2. Memory — one-time symlink (or copy)

Auto-memory is keyed by your Windows username, so the files have to live at:

```
C:\Users\{YOUR_USERNAME}\.claude\projects\c--Users-{YOUR_USERNAME}-code-SiftStack\memory\
```

**Option A — symlink (recommended; updates flow both ways):**

PowerShell as Administrator:
```powershell
$user = $env:USERNAME
$target = "C:\Users\$user\.claude\projects\c--Users-$user-code-SiftStack"
New-Item -ItemType Directory -Force -Path $target | Out-Null
New-Item -ItemType SymbolicLink -Path "$target\memory" -Target "C:\Users\$user\code\SiftStack\.claude\memory"
```

**Option B — one-time copy:**

```bash
USER_DIR="/c/Users/$USERNAME/.claude/projects/c--Users-$USERNAME-code-SiftStack"
mkdir -p "$USER_DIR"
cp -r .claude/memory "$USER_DIR/"
```

After either option, restart Claude Code — `MEMORY.md` and the 43 memory files should auto-load on every SiftStack session.

### 3. Secrets (NOT in git)

Get these from Sean via secure channel (1Password / Signal / etc.):

- `.env` — fill in from `.env.example` template
- `input.json` — fill in from `input.example.json`
- `input.cloud.json` — fill in from `input.cloud.example.json`

### 4. GSD framework (optional)

If you want the same `gsd-*` slash commands and agents Sean uses, install GSD at the user level (not from this repo). Ask Sean for the install command.

## What's NOT shipped here

- **GSD agents/hooks** — installed at user level (`~/.claude/agents/`, `~/.claude/hooks/`). Not project-specific.
- **Conversation history** — your sessions, not portable.
- **`.env` / `input*.json`** — secrets, transferred out-of-band.
- **Browser profiles** (`.datasift_profile/`, `.ancestry_profile/`) — login state, recreate on first run.

## Updating shared memory

When Sean's Claude saves a new project-memory file (auto-memory does this during sessions), it lands in his user-level path, not this repo. To share an update:

```bash
cp -r "/c/Users/SeanJones/.claude/projects/c--Users-SeanJones-code-SiftStack/memory/." .claude/memory/
git add .claude/memory && git commit -m "sync project memory"
```

If teammates symlinked (Option A), their `~/.claude/.../memory` already points at the repo — pulling the commit is enough.
