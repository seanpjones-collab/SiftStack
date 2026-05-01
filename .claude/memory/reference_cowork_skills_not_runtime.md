---
name: "Skills for REI/" folder is distribution bundles, not runtime skills
description: Distinguish the public Co-Work skill library from Claude Code runtime skills so future sessions don't confuse them
type: reference
originSessionId: ee2bb737-70f2-4339-a960-986fae018007
---
Two separate skill locations in this project — DO NOT confuse them:

1. **`c:\Users\SeanJones\code\SiftStack\Skills for REI/`** — **Distribution bundles** (`.skill` / `.plugin` ZIP files). These are the public library Sean distributes at learn.datasift.ai/claude-skills-rei for DataSift community members to load into their own Claude **Co-Work** sessions. They are NOT loaded into Claude Code at runtime. Most assume Co-Work-specific tools (`javascript_tool`, `mcp__cowork__present_files`, sandbox mount paths like `/sessions/.../mnt/Claude/`) that don't exist in Claude Code.

2. **`~/.claude/skills/`** (C:\Users\SeanJones\.claude\skills\) — **Runtime skills** loaded by Claude Code. These appear in the skills list on session start. This is where a skill must live to be callable via the Skill tool.

**Implications:**
- When a user references "a skill in the stack" or "I have a skill for X", check BOTH locations. The folder name overlap causes confusion.
- Co-Work `.skill` files CANNOT be used as-is in Claude Code. Their **knowledge** (API contracts, regex patterns, step-by-step playbooks) is valuable and reusable — the **implementation** (tools they call) is not. When porting, extract the knowledge and rewrite against Claude Code's native tools (Bash, Python, Playwright).
- The `cjis-foreclosure-puller.skill` was a good case study: the skill's documented API contract was WRONG in several places (scCode table, query format, case detail URL). Treat Co-Work skill contents as a starting hypothesis, not ground truth — verify via live probe before building.
