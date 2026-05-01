---
name: PDF body margins ≠ header band margins
description: When asked to make PDF content narrower, only inset body text — chapter header bands and full-width design elements should keep their original wider footprint
type: feedback
originSessionId: bc69b8d2-dac1-420f-a7cc-267e0d339298
---
In branded PDF/document generation, when Sean says "the content is too wide" or "give it more margins" or "more breathing room," he means the **body text and inline callouts** — NOT the colored chapter header bands, full-width banners, big CTA boxes, or other anchor visual elements.

**Why:** Sean specifically called out (Apr 2026, foreclosure guide work): "you applied them to everything including the header boxes, not just the content on the page." A uniform global margin increase shrinks the whole page proportionally, which is not the desired effect. The header bands and full-width design anchors should stay wide so the document feels visually anchored; only the body paragraphs/lists should indent further.

**How to apply:** When narrowing content in a reportlab PDF, do NOT change `MARGIN_X` / `CONTENT_W` globally. Instead, add `leftIndent` / `rightIndent` to the body ParagraphStyles, or wrap body sections in a narrower inner Frame/Table while leaving section header bands at full content width. Header bands (like "OPTION 02 / Sell & Move Forward" filled bands) and CTA boxes should continue to span the full content width.
