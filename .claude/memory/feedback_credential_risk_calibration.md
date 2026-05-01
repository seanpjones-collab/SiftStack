---
name: Credential risk calibration
description: Don't treat API keys shared in Claude chat as "compromised" — calibrate realistically against the user's actual threat model
type: feedback
originSessionId: 249385bf-7db4-4572-b6d8-84963b60ea5d
---
When the user pastes an API key, secret, or credential into a Claude conversation, do NOT call it "compromised" or recommend urgent rotation as if it were a public leak. The trust boundary is the same as the credential sitting in the user's local `.env` file or in `~/.claude.json` for an MCP server — Anthropic-hosted, encrypted, governed by privacy policy, not publicly accessible.

**Why:** I called the user's Firecrawl key "compromised" after they pasted it, then later asked them to paste the rotated key in the same chat — they correctly called out the contradiction. Pasting in chat ≠ public leak. Treating it as one is security theater that wastes the user's time and undermines the trust model that makes MCP integrations possible (MCP server configs *store* the same keys Claude already sees).

**How to apply:**
- Real public exposure (committed to public repo, posted in public Slack/Discord, screenshotted publicly) → recommend rotation.
- Pasted to me in a private chat, written to `.env`, written to `~/.claude.json`, sent to a vendor MCP server → no rotation needed; treat as normal credential handling.
- If a security note is genuinely warranted, frame it as "best practice" not "compromise" — and only mention once, not repeatedly across turns.
- Never ask the user to paste a "rotated" credential in the same chat I just told them was unsafe — the contradiction is obvious and corrosive.
