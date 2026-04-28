"""Bulk-apply Property Status + SiftLine board placement to Podio-migrated records.

Source of truth: output/podio_migration/podio_to_sift_status_mapping.md

Reads cohorts from the locked mapping. For each cohort:
  1. Filter Properties by tag (Any Tags OR -> podio-status:<value>)
  2. Select all (uses CheckboxDropdown -> "Select Max")
  3. Bulk Change Property Status -> mapped status
  4. Bulk Add to Board (if mapped) -> board / phase
  5. Bulk Add Tag (DNC cohort only)

Build is staged. Phase 1 = --discover only: no mutations, dumps the top-bar
action menus (Manage, Send To, Add to Board, etc.) so we can pick selectors
for the bulk actions in subsequent phases.

Usage:
    # Phase 1 — discover the bulk-action UI
    python scripts/podio_apply_status_mapping.py --discover --cohort "Discovery"

    # Phase 2+ — once selectors are known
    python scripts/podio_apply_status_mapping.py --dry-run
    python scripts/podio_apply_status_mapping.py --cohort "DNC List" --limit 1
    python scripts/podio_apply_status_mapping.py
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from playwright.async_api import Page, async_playwright  # noqa: E402

from datasift_core import (  # noqa: E402
    dismiss_popups as _dismiss_popups,
    login,
    screenshot as _screenshot,
)
from datasift_uploader import _select_all_records  # noqa: E402

DATASIFT_RECORDS_URL = "https://app.reisift.io/records/properties"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("podio_apply")


# ── Cohort table (locked source of truth) ──────────────────────────────
# Mirrors output/podio_migration/podio_to_sift_status_mapping.md.
# `podio-temp:HOT` cohort intentionally OMITTED — the temp tag is unreliable
# (operator didn't update it when status changed), so we trust podio-status:*
# only. Sean will verify cohort placement manually after the run.

@dataclass
class Cohort:
    name: str                 # human label for logging / --cohort flag
    tag: str                  # exact tag value to filter by (Any Tags OR)
    expected_count: int       # from the mapping playbook (for sanity)
    status: str               # Property Status to set
    board: str | None = None  # SiftLine board name (None = no card)
    phase: str | None = None  # SiftLine phase name within board
    extra_tags: list[str] = field(default_factory=list)


COHORTS: list[Cohort] = [
    Cohort("Discovery",                  "podio-status:Discovery",                              29,  "Warm Lead",      "Lead Management", "Nurture New Lead (Unqualified)"),
    # Tag value preserves Podio's bold-markdown asterisks literally — verified
    # against tmp/podio_migration/sift_records_export.csv.
    Cohort("Interested Set Offer",       "podio-status:Interested - **Set Offer Status**",      12,  "Hot Lead",       "Acquisitions",    "Appointment / Make Offer"),
    Cohort("Interested Add to Followup", "podio-status:Interested - Add to Followup",           20,  "Warm Lead",      "Lead Management", "Nurture New Lead (Unqualified)"),
    Cohort("Add to Followup",            "podio-status:Add to Followup",                        110, "Cold Lead",      "Lead Management", "COLD Leads (Qualified)"),
    Cohort("Offer Follow up",            "podio-status:Offer Follow up",                        21,  "Hot Lead",       "Acquisitions",    "Offer Follow-Up"),
    Cohort("In Contract Manual",         "podio-status:In Contract - Set Manually",             2,   "Under Contract", "Transactions",    "New Contract"),
    # "Listed" and "Sold" don't exist as Property Status options in Sean's
    # tenant — only 11 statuses: Default, New Lead, No Contact New Lead,
    # Cold Lead, Warm Lead, Hot Lead, Ghosting Lead, Dead Lead, Not Interested,
    # Under Contract, Closed. Sean mapped both to Dead Lead: "we did not
    # close them so closed is not the way" — they're off the pipeline but
    # not via our close.
    Cohort("Referred to Agent",          "podio-status:Referred to Agent",                      4,   "Dead Lead"),
    Cohort("DNC List",                   "podio-status:DNC List",                               44,  "Dead Lead",      extra_tags=["DNC"]),
    Cohort("Already Sold",               "podio-status:Already Sold",                           32,  "Dead Lead"),
    Cohort("Lost Deal",                  "podio-status:Lost Deal",                              7,   "Dead Lead"),
    Cohort("Not Owner / Bad Phone",      "podio-status:Not Owner/ Bad Name/ Bad Phone Number",  79,  "Dead Lead"),
    Cohort("Dead",                       "podio-status:Dead",                                   100, "Dead Lead"),
    Cohort("Contract Cancelled",         "podio-status:Contract Cancelled",                     1,   "Dead Lead"),
]


# ── Filter by tag (mirrors _filter_by_list pattern) ────────────────────

async def _filter_by_tag(page: Page, tag: str, mode: str = "any") -> bool:
    """Filter records by a single tag value.

    Mirrors the _filter_by_list flow: open filter panel -> search "Tags"
    in the filter-block search input -> click "Any Tags (OR)" or
    "All Tags (AND)" -> type tag value -> click matching option ->
    Apply Filters.

    Args:
        page: Logged-in Playwright page on /records/properties.
        tag: Exact tag value to match (e.g. "podio-status:Discovery").
        mode: "any" -> Any Tags (OR), "all" -> All Tags (AND).

    Returns:
        True if filter was applied, False otherwise. Does NOT verify
        record count — caller should check via header text after.
    """
    block_label = "Any Tags (OR)" if mode == "any" else "All Tags (AND)"

    try:
        await _dismiss_popups(page)

        # Open filter panel
        filter_link = page.locator("#Records__Filters_Trigger")
        if await filter_link.count() == 0:
            filter_link = page.locator('a:has-text("Filter Records")')
        if await filter_link.count() == 0:
            logger.warning("No Filter Records link found")
            return False
        await filter_link.first.click()
        await page.wait_for_timeout(2000)

        await _dismiss_popups(page)
        await _screenshot(page, "tagfilter_panel_opened")

        # Type "Tags" in the "Add new filter block" search input
        filter_search = page.locator("#RecordsFilters__Filter_Blocks__Search")
        if await filter_search.count() == 0:
            filter_search = page.locator('input[placeholder*="filter block"]')
        if await filter_search.count() == 0:
            logger.warning("Filter block search input not found")
            return False
        await filter_search.first.click()
        await filter_search.first.fill("Tags")
        await page.wait_for_timeout(1500)
        await _screenshot(page, "tagfilter_block_search")

        # Click the "Any Tags (OR)" / "All Tags (AND)" option
        block_opt = page.locator(f'text="{block_label}"')
        if await block_opt.count() == 0:
            logger.warning("Filter block option '%s' not found", block_label)
            return False
        await block_opt.first.click()
        await page.wait_for_timeout(2000)
        logger.info("Added '%s' filter block", block_label)

        await _dismiss_popups(page)
        await _screenshot(page, "tagfilter_block_added")

        # Now find the tag-search input that just appeared in the new block.
        # Placeholder is likely "Search for tags..." or similar — try several.
        tag_search = page.locator(
            'input[placeholder*="Search for tags" i], '
            'input[placeholder*="Enter tag" i], '
            'input[placeholder*="tag" i]'
        )
        if await tag_search.count() == 0:
            logger.warning("Tag search input not found in newly added block")
            await _screenshot(page, "tagfilter_no_input")
            return False

        # Use the LAST tag input — multiple may exist if other tag blocks
        # were left in place from prior cohorts.
        last_idx = await tag_search.count() - 1
        await tag_search.nth(last_idx).fill(tag)
        await page.wait_for_timeout(1500)
        await _screenshot(page, "tagfilter_value_typed")

        # Click the matching tag option in the autocomplete dropdown.
        # Use exact text match to avoid false positives on substring tags.
        tag_opt = page.locator(f'text="{tag}"')
        if await tag_opt.count() == 0:
            logger.warning("Tag option '%s' not found in dropdown", tag)
            await _screenshot(page, "tagfilter_no_option")
            return False
        # Use last match (the one in the dropdown, not the input field echo)
        await tag_opt.last.click(force=True)
        await page.wait_for_timeout(1500)
        logger.info("Selected tag: %s", tag)
        await _screenshot(page, "tagfilter_value_selected")

        # Apply Filters
        apply_btn = page.locator('text="Apply Filters"')
        if await apply_btn.count() > 0:
            await apply_btn.first.click()
            await page.wait_for_timeout(3000)
            logger.info("Applied tag filter")
        else:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(2000)

        await _screenshot(page, "tagfilter_applied")
        return True
    except Exception as e:
        logger.warning("Filter by tag failed: %s", e)
        await _screenshot(page, "tagfilter_failed")
        return False


# ── Record-count probe ─────────────────────────────────────────────────

async def _probe_record_count(page: Page) -> int | None:
    """Read the filtered record count WITHOUT opening any dropdown.

    Original implementation opened the CheckboxDropdown to read "Select all (N)"
    — but that left the dropdown in a "primed" state where the next click
    (from _select_all_records Strategy 0) toggled it CLOSED instead of open,
    breaking Strategy 0 and forcing the Strategy 2 fallback that only selects
    the 10 visible-page records (Sift paginates at 10/page). This caused
    ~295 records to miss the bulk status update on the first full run.

    Workaround: read the count from a non-modal source — the records header
    typically shows "X records" or similar. If we can't find it, return None
    and let _select_all_records report the count from Strategy 0's log line.
    """
    try:
        count = await page.evaluate(r"""() => {
            // Look for "X Records" / "X Properties" / "1-N of M" patterns
            // OUTSIDE the CheckboxDropdown (which we don't want to open).
            for (const el of document.querySelectorAll('div, span, p, h1, h2, h3, h4')) {
                if (el.children.length > 3) continue;
                const cls = (el.className || '').toString();
                if (cls.includes('CheckboxDropdown')) continue;
                const t = (el.textContent || '').trim();
                if (!t || t.length > 80) continue;
                let m;
                m = t.match(/^(\d{1,3}(?:,\d{3})*)\s+(?:Records|Properties|results)\b/i);
                if (m) return parseInt(m[1].replace(/,/g, ''));
                m = t.match(/of\s+(\d{1,3}(?:,\d{3})*)\s*$/);
                if (m) return parseInt(m[1].replace(/,/g, ''));
            }
            return null;
        }""")
        return count
    except Exception as e:
        logger.debug("Probe record count failed: %s", e)
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return None


async def _switch_to_all_view(page: Page) -> bool:
    """Click the "All" toggle in the Clean/Incomplete/All toggle group.

    Default view is "Clean" — excludes records flagged Incomplete. Podio
    migration records often lack Smarty-validated addresses and end up in
    Incomplete, so we must flip to "All" before counting/selecting.

    Returns True if we clicked All (or it was already active).
    """
    try:
        await _dismiss_popups(page)
        # ToggleGroup styled buttons — find by exact text "All"
        result = await page.evaluate(r"""() => {
            const btns = document.querySelectorAll('[class*="ToggleGroup"]');
            for (const b of btns) {
                const t = (b.textContent || '').trim();
                if (t === 'All') {
                    const cls = (b.className || '').toString();
                    // Active class is "vcyoq" (lighter), inactive is "kWjhhh".
                    // Click regardless — it's idempotent in styled-components.
                    b.scrollIntoView({behavior: 'instant', block: 'center'});
                    b.click();
                    return {clicked: true, was_active: cls.includes('vcyoq')};
                }
            }
            return {clicked: false};
        }""")
        await page.wait_for_timeout(2000)
        if result.get("clicked"):
            logger.info("Clicked 'All' toggle (was_active=%s)", result.get("was_active"))
            return True
        logger.warning("'All' toggle not found")
        return False
    except Exception as e:
        logger.warning("Switch to All view failed: %s", e)
        return False


async def _dump_action_modal(page: Page) -> dict:
    """Dump every interactive element in whatever modal/panel just opened.

    Captures inputs, buttons, styled-dropdowns (SelectValue), and option
    containers — enough to figure out the modal's UI shape without
    committing any action.
    """
    return await page.evaluate(r"""() => {
        const out = {inputs: [], buttons: [], select_values: [], options: [], headings: []};
        const cap = (el) => {
            const r = el.getBoundingClientRect();
            return {
                text: ((el.placeholder || el.value || el.innerText || el.textContent) || '').toString().trim().substring(0, 80),
                tag: el.tagName,
                x: Math.round(r.x), y: Math.round(r.y),
                w: Math.round(r.width), h: Math.round(r.height),
                cls: (el.className || '').toString().substring(0, 100),
                ph: (el.placeholder || '').substring(0, 60),
            };
        };
        const inViewport = (r) => r.height > 0 && r.width > 0 && r.y > 0 && r.y < 900;

        // Inputs (text + textarea)
        for (const el of document.querySelectorAll('input, textarea')) {
            const r = el.getBoundingClientRect();
            if (!inViewport(r)) continue;
            // Skip sidebar (x < 220) and tiny utility inputs
            if (r.x < 220 || r.height < 16) continue;
            out.inputs.push(cap(el));
        }
        // Buttons
        for (const el of document.querySelectorAll('button, [role="button"]')) {
            const r = el.getBoundingClientRect();
            if (!inViewport(r)) continue;
            if (r.x < 220) continue;
            const t = (el.innerText || el.textContent || '').trim();
            if (!t || t.length > 60) continue;
            out.buttons.push(cap(el));
        }
        // Styled select displays (SelectValue = currently displayed value)
        for (const el of document.querySelectorAll('[class*="SelectValue"]')) {
            const r = el.getBoundingClientRect();
            if (!inViewport(r) || r.x < 220) continue;
            out.select_values.push(cap(el));
        }
        // Option containers (visible only when a dropdown is open)
        for (const el of document.querySelectorAll('[class*="SelectOptionContainer"], [class*="SelectOption"]')) {
            const r = el.getBoundingClientRect();
            if (!inViewport(r) || r.x < 220) continue;
            const t = (el.innerText || el.textContent || '').trim();
            if (!t || t.length > 80) continue;
            out.options.push(cap(el));
        }
        // Modal headings — useful for confirming we're looking at the right modal
        for (const el of document.querySelectorAll('h1, h2, h3, h4, [class*="Modal"] [class*="Header"], [class*="Modal"] [class*="Title"]')) {
            const r = el.getBoundingClientRect();
            if (!inViewport(r) || r.x < 220) continue;
            const t = (el.innerText || el.textContent || '').trim();
            if (!t || t.length > 80) continue;
            out.headings.push(cap(el));
        }
        return out;
    }""")


async def _ensure_dropdown_closed(page: Page) -> None:
    """Click a neutral region to collapse any open top-bar dropdown.

    Manage and Send to... buttons TOGGLE — second click closes. If the
    dropdown was left open by previous activity, our "open" click would
    actually close it and the nav-item search fails. Click neutral first.
    """
    try:
        # Click on the page heading area (well clear of dropdown items)
        await page.evaluate(r"""() => {
            // Click somewhere away from buttons — try the page heading
            // or the records area top-left corner.
            const h = document.querySelector('h1, [class*="PageHeader"], [class*="AdminTabs"]');
            if (h) h.click();
        }""")
        await page.wait_for_timeout(400)
    except Exception:
        pass


async def _open_dropdown_action(page: Page, button_text: str, action_text: str) -> bool:
    """Open a top-bar dropdown (Manage / Send to...) and click its nav item.

    Detects whether the dropdown is already open (via the action_text being
    visible) and skips the toggle click in that case — handles the
    Manage/Send To toggle-state alternation that otherwise causes failures.
    """
    try:
        await _dismiss_popups(page)

        # Is the action already visible (dropdown already open)?
        already_open = await page.evaluate(r"""(target) => {
            const items = document.querySelectorAll('[class*="DropdownNavItem"]');
            for (const it of items) {
                const t = (it.textContent || '').trim();
                if (t !== target) continue;
                const r = it.getBoundingClientRect();
                if (r.height > 0 && r.width > 0) return true;
            }
            return false;
        }""", action_text)

        if not already_open:
            # Ensure clean state — click neutral so a stuck-open dropdown collapses
            await _ensure_dropdown_closed(page)
            btn = page.locator(f'button:has-text("{button_text}")').first
            await btn.click()
            await page.wait_for_timeout(900)

        # Click the dropdown nav item by exact text
        clicked = await page.evaluate(r"""(target) => {
            const items = document.querySelectorAll('[class*="DropdownNavItem"]');
            for (const it of items) {
                if ((it.textContent || '').trim() === target) {
                    const r = it.getBoundingClientRect();
                    if (r.height === 0 || r.width === 0) continue;
                    it.click();
                    return true;
                }
            }
            return false;
        }""", action_text)
        if not clicked:
            logger.warning("%s > '%s' nav item not found", button_text, action_text)
            return False
        await page.wait_for_timeout(1500)
        return True
    except Exception as e:
        logger.warning("Open %s > '%s' failed: %s", button_text, action_text, e)
        return False


async def _open_manage_action(page: Page, action_text: str) -> bool:
    """Click Manage -> <action_text> and wait for the modal/panel to render."""
    return await _open_dropdown_action(page, "Manage", action_text)


async def _open_send_to_action(page: Page, action_text: str) -> bool:
    """Click 'Send to...' -> <action_text> and wait for the modal."""
    return await _open_dropdown_action(page, "Send to", action_text)


async def _close_modal(page: Page) -> None:
    """Try to close any open modal without committing.

    Strategy: ESC, then click Cancel/Close button if present, then try
    clicking a modal backdrop. We DO NOT click any save/apply/confirm
    buttons during discovery.
    """
    for _ in range(2):
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)
    # Cancel/Close buttons (defensive — discovery shouldn't need this if ESC works)
    cancel = page.locator(
        'button:has-text("Cancel"), '
        'button:has-text("Close"), '
        '[class*="Modal"] button:has-text("×")'
    )
    if await cancel.count() > 0:
        try:
            await cancel.first.click()
            await page.wait_for_timeout(500)
        except Exception:
            pass
    await _dismiss_popups(page)


# ── Single-record select (for --limit 1 smoke test) ────────────────────

async def _select_first_record_only(page: Page) -> bool:
    """Click only the first record row's checkbox.

    Used for --limit 1 smoke testing — operates on a single record so any
    bug only damages one record. Returns True if a checkbox was clicked
    AND the bulk-action top bar (Manage / Send to) appeared.

    Strategy: find the OWNER column header (same anchor _select_all_records
    uses for the header checkbox), then pick the smallest-y checkbox whose
    y is STRICTLY BELOW the header.
    """
    try:
        await _dismiss_popups(page)
        await _screenshot(page, "single_select_before")
        debug = await page.evaluate(r"""() => {
            // Step 1: find the OWNER header row's y coordinate
            let headerY = null;
            for (const el of document.querySelectorAll('*')) {
                const t = (el.textContent || '').trim();
                if (t === 'OWNER' && el.children.length === 0) {
                    const r = el.getBoundingClientRect();
                    if (r.height > 0) {
                        headerY = r.top;
                        break;
                    }
                }
            }
            // Step 2: native checkboxes (don't exist in this Sift) AND
            // styled-component checkbox elements ([class*="Checkbox"]).
            const native = [];
            for (const cb of document.querySelectorAll('input[type="checkbox"]')) {
                if (cb.classList.contains('react-toggle-screenreader-only')) continue;
                const r = cb.getBoundingClientRect();
                if (r.height === 0 || r.width === 0) continue;
                native.push({type: 'native', y: r.y, x: r.x, w: r.width, h: r.height,
                             cls: (cb.className || '').toString().substring(0, 80)});
            }
            // Only StyledLabel = the actual clickable checkbox label.
            // CustomCheckbox is the visual wrapper, SVG is the checkmark.
            const labels = [];
            for (const el of document.querySelectorAll('[class*="Checkbox__StyledLabel"]')) {
                const cls = (el.className || '').toString();
                if (cls.includes('CheckboxDropdown')) continue;
                if (cls.includes('Toggle')) continue;
                const r = el.getBoundingClientRect();
                if (r.height === 0 || r.width === 0) continue;
                labels.push({type: 'styled_label', y: r.y, x: r.x,
                             w: r.width, h: r.height,
                             cls: cls.substring(0, 80)});
            }
            // Dedupe by y (within 2px) so we don't double-count overlapping
            // wrappers, then sort by y. The header label sits at the smallest
            // y; row labels are below it.
            labels.sort((a, b) => a.y - b.y);
            const dedup = [];
            for (const l of labels) {
                if (dedup.length === 0 || Math.abs(l.y - dedup[dedup.length-1].y) > 5) {
                    dedup.push(l);
                }
            }
            // First item = header checkbox; second = first record row.
            // (Header has class "hQSwIv" in current build; rows have "egqrmj".)
            const first_row = dedup.length >= 2 ? dedup[1] : null;
            return {
                headerY,
                native_count: native.length,
                styled_label_count: labels.length,
                dedup_count: dedup.length,
                first_native: native[0] || null,
                header_candidate: dedup[0] || null,
                first_row: first_row,
                all_dedup: dedup.slice(0, 6),
            };
        }""")
        logger.info("Select-first debug: %s", debug)

        first = debug.get("first_row")
        if not first:
            logger.warning("No record-row checkbox found (after header skip)")
            return False

        # Click center of the discovered checkbox
        cx = first["x"] + first["w"] / 2
        cy = first["y"] + first["h"] / 2
        logger.info("Clicking record checkbox (%s) at (%.0f, %.0f)",
                    first.get("type"), cx, cy)
        await page.mouse.click(cx, cy)
        await page.wait_for_timeout(1500)
        await _screenshot(page, "single_select_after")
        # Verify Manage / Send To buttons appeared (selection succeeded)
        manage_visible = await page.locator('button:has-text("Manage")').count() > 0
        send_to_visible = await page.locator('button:has-text("Send to")').count() > 0
        logger.info("After single-select: Manage visible=%s, Send To visible=%s",
                    manage_visible, send_to_visible)
        return manage_visible or send_to_visible
    except Exception as e:
        logger.warning("Select first record failed: %s", e)
        return False


# ── Bulk action: Change Property Status ────────────────────────────────

async def _bulk_change_status(page: Page, status: str) -> bool:
    """Open Manage > Change status, pick `status`, click Save status.

    Modal layout (from discovery):
      - Heading "Update status"
      - One SelectValue at (~591, 422) showing current value (default "Default")
      - "Save status" button at (~927, 547)
      - 11 status options: Default, New Lead, No Contact New Lead, Cold Lead,
        Warm Lead, Hot Lead, Ghosting Lead, Dead Lead, Not Interested,
        Under Contract, Closed.
    """
    try:
        opened = await _open_manage_action(page, "Change status")
        if not opened:
            logger.error("Could not open Manage > Change status")
            return False
        await page.wait_for_timeout(1200)
        await _screenshot(page, f"status_modal_open_{status.replace(' ', '_').lower()}")

        # Click the modal's SelectValue (the picker — last visible at x > 220)
        opened_picker = await page.evaluate(r"""() => {
            const svs = document.querySelectorAll('[class*="SelectValue"]');
            let target = null;
            for (const sv of svs) {
                const r = sv.getBoundingClientRect();
                if (r.x > 220 && r.height > 0 && r.y > 0 && r.y < 900) {
                    target = sv;
                }
            }
            if (!target) return false;
            target.click();
            return true;
        }""")
        if not opened_picker:
            logger.error("Status picker SelectValue not found")
            return False
        await page.wait_for_timeout(800)

        # Click the matching status option
        picked = await page.evaluate(r"""(target) => {
            const opts = document.querySelectorAll(
                '[class*="SelectOptionDisplayValueContainer"]'
            );
            for (const o of opts) {
                const t = (o.innerText || o.textContent || '').trim();
                const r = o.getBoundingClientRect();
                if (t === target && r.height > 0 && r.x > 220) {
                    o.click();
                    return true;
                }
            }
            return false;
        }""", status)
        if not picked:
            logger.error("Status option '%s' not found", status)
            return False
        await page.wait_for_timeout(1000)
        await _screenshot(page, f"status_modal_picked_{status.replace(' ', '_').lower()}")

        # Click "Save status" button
        saved = await page.evaluate(r"""() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                const t = (b.innerText || b.textContent || '').trim();
                if (t === 'Save status') {
                    b.click();
                    return true;
                }
            }
            return false;
        }""")
        if not saved:
            logger.error("'Save status' button not found")
            return False
        logger.info("Clicked 'Save status' for status='%s'", status)
        await page.wait_for_timeout(3000)  # give Sift time to commit + close modal
        await _dismiss_popups(page)
        await _screenshot(page, f"status_after_save_{status.replace(' ', '_').lower()}")
        return True
    except Exception as e:
        logger.error("Bulk change status failed: %s", e)
        await _screenshot(page, "status_error")
        return False


# ── Bulk action: Add Tags ──────────────────────────────────────────────

async def _bulk_add_tags(page: Page, tags: list[str]) -> bool:
    """Open Manage > Add tags, fill each tag, click Add tags.

    Modal has a tag input (autocomplete). For each tag: type the value,
    press Enter to add as a chip. After all tags added, click 'Add tags'.
    """
    if not tags:
        return True

    try:
        opened = await _open_manage_action(page, "Add tags")
        if not opened:
            logger.error("Could not open Manage > Add tags")
            return False
        await page.wait_for_timeout(1200)
        await _screenshot(page, "tags_modal_open")

        # Find the tag input (NOT the global "Search for records..." input)
        # The modal's tag input is to the right of x=450 and within y 350-550.
        for tag in tags:
            await page.evaluate(r"""(tagValue) => {
                const inputs = document.querySelectorAll('input');
                let target = null;
                for (const inp of inputs) {
                    const r = inp.getBoundingClientRect();
                    const ph = (inp.placeholder || '').toLowerCase();
                    // Skip the global record search at top-right (y < 200)
                    if (r.y < 200) continue;
                    // Skip sidebar
                    if (r.x < 220) continue;
                    // Heuristic: tag input has a tag-related placeholder OR
                    // is the only input visible in the modal body
                    if (ph.includes('tag') || ph.includes('add') || ph === '') {
                        target = inp;
                    }
                }
                if (!target) return false;
                target.scrollIntoView({behavior: 'instant', block: 'center'});
                target.focus();
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                ).set;
                setter.call(target, tagValue);
                target.dispatchEvent(new Event('input', {bubbles: true}));
                target.dispatchEvent(new Event('change', {bubbles: true}));
                return true;
            }""", tag)
            await page.wait_for_timeout(800)
            # Press Enter to commit the tag (most autocomplete inputs accept Enter)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(800)
            logger.info("Entered tag: %s", tag)
            await _screenshot(page, f"tags_modal_typed_{tag.replace(' ', '_').lower()[:20]}")

        # Click "Add tags" button to commit
        clicked = await page.evaluate(r"""() => {
            const btns = document.querySelectorAll('button');
            // Find the "Add tags" button — there may be 2 (header + commit).
            // Prefer the one in the modal action bar (large width, bottom-right).
            let best = null;
            for (const b of btns) {
                const t = (b.innerText || b.textContent || '').trim();
                if (t !== 'Add tags') continue;
                const r = b.getBoundingClientRect();
                if (r.width < 80) continue;  // skip sidebar / nav-item buttons
                // Prefer larger Y (lower on screen = action bar)
                if (best === null || r.y > best.r.y) {
                    best = {el: b, r: r};
                }
            }
            if (!best) return false;
            best.el.click();
            return true;
        }""")
        if not clicked:
            logger.error("'Add tags' commit button not found")
            return False
        logger.info("Clicked 'Add tags' commit (tags=%s)", tags)
        await page.wait_for_timeout(3000)
        await _dismiss_popups(page)
        await _screenshot(page, "tags_after_save")
        return True
    except Exception as e:
        logger.error("Bulk add tags failed: %s", e)
        await _screenshot(page, "tags_error")
        return False


# ── Bulk action: Send to SiftLine (board + phase placement) ────────────

async def _bulk_send_to_siftline(page: Page, board: str, phase: str) -> bool:
    """Open Send to > Siftline, pick board + phase, click Import button.

    Modal has TWO SelectValues side-by-side (board picker leftmost,
    phase picker to the right). Phase picker is initially "—" and only
    populates after a board is picked.
    """
    try:
        opened = await _open_send_to_action(page, "Siftline")
        if not opened:
            logger.error("Could not open Send to > Siftline")
            return False
        await page.wait_for_timeout(1500)
        await _screenshot(page, f"siftline_modal_open_{board.replace(' ', '_').lower()}")

        # Pick the board (leftmost SelectValue)
        opened_board = await page.evaluate(r"""() => {
            const svs = document.querySelectorAll('[class*="SelectValue"]');
            let leftmost = null;
            for (const sv of svs) {
                const r = sv.getBoundingClientRect();
                if (r.x > 220 && r.height > 0 && r.y > 0 && r.y < 900) {
                    if (leftmost === null || r.x < leftmost.x) {
                        leftmost = {el: sv, x: r.x};
                    }
                }
            }
            if (!leftmost) return false;
            leftmost.el.click();
            return true;
        }""")
        if not opened_board:
            logger.error("Board picker not found")
            return False
        await page.wait_for_timeout(800)

        picked_board = await page.evaluate(r"""(target) => {
            const opts = document.querySelectorAll(
                '[class*="SelectOptionDisplayValueContainer"]'
            );
            for (const o of opts) {
                const t = (o.innerText || o.textContent || '').trim();
                const r = o.getBoundingClientRect();
                if (t === target && r.height > 0 && r.x > 220) {
                    o.click();
                    return true;
                }
            }
            return false;
        }""", board)
        if not picked_board:
            logger.error("Board option '%s' not found", board)
            return False
        await page.wait_for_timeout(1500)
        await _screenshot(page, f"siftline_board_picked_{board.replace(' ', '_').lower()}")

        # Pick the phase (rightmost SelectValue, now populated with phases)
        opened_phase = await page.evaluate(r"""() => {
            const svs = document.querySelectorAll('[class*="SelectValue"]');
            let rightmost = null;
            for (const sv of svs) {
                const r = sv.getBoundingClientRect();
                if (r.x > 220 && r.height > 0 && r.y > 0 && r.y < 900) {
                    if (rightmost === null || r.x > rightmost.x) {
                        rightmost = {el: sv, x: r.x};
                    }
                }
            }
            if (!rightmost) return false;
            rightmost.el.click();
            return true;
        }""")
        if not opened_phase:
            logger.error("Phase picker not found")
            return False
        await page.wait_for_timeout(1000)

        picked_phase = await page.evaluate(r"""(target) => {
            const opts = document.querySelectorAll(
                '[class*="SelectOptionDisplayValueContainer"]'
            );
            for (const o of opts) {
                const t = (o.innerText || o.textContent || '').trim();
                const r = o.getBoundingClientRect();
                if (t === target && r.height > 0 && r.x > 220) {
                    o.click();
                    return true;
                }
            }
            return false;
        }""", phase)
        if not picked_phase:
            logger.error("Phase option '%s' not found on board '%s'", phase, board)
            return False
        await page.wait_for_timeout(1500)
        await _screenshot(page, f"siftline_phase_picked_{phase.replace(' ', '_').lower()[:25]}")

        # Click "Import N properties" button — text varies per cohort size
        clicked = await page.evaluate(r"""() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                const t = (b.innerText || b.textContent || '').trim();
                if (/^Import\s+\d/.test(t)) {
                    b.click();
                    return t;
                }
            }
            return null;
        }""")
        if not clicked:
            logger.error("'Import N properties' button not found")
            return False
        logger.info("Clicked '%s' (board=%s phase=%s)", clicked, board, phase)
        await page.wait_for_timeout(3000)
        await _dismiss_popups(page)
        await _screenshot(page, "siftline_after_import")
        return True
    except Exception as e:
        logger.error("Bulk send to siftline failed: %s", e)
        await _screenshot(page, "siftline_error")
        return False


# ── Cohort orchestrator ────────────────────────────────────────────────

async def process_cohort(page: Page, cohort: Cohort, *,
                          dry_run: bool = False, limit: int = 0,
                          skip_status: bool = False,
                          skip_tags: bool = False,
                          skip_boards: bool = False) -> dict:
    """Run all bulk actions for a single cohort.

    Steps:
      1. Switch to All view
      2. Filter by cohort.tag (Any Tags OR)
      3. Probe count
      4. Select all (or first 1 if limit==1)
      5. Change Property Status (always, unless skip_status)
      6. Add tags (if cohort.extra_tags and not skip_tags)
      7. Send to SiftLine board+phase (if cohort.board and not skip_boards)

    With dry_run=True, performs filter + count only — no mutations.

    The skip_* flags exist for repair runs: e.g., status-only re-run after a
    bug caused some records to miss the status step on the first pass, where
    we don't want to re-tag or re-create board cards.
    """
    result = {
        "cohort": cohort.name,
        "tag": cohort.tag,
        "expected": cohort.expected_count,
        "actual": None,
        "status_set": False,
        "tags_added": False,
        "board_set": False,
        "skipped": False,
    }

    # 1. Switch to All view
    await _switch_to_all_view(page)

    # 2. Filter
    filtered = await _filter_by_tag(page, cohort.tag)
    if not filtered:
        logger.error("[%s] Filter failed — skipping cohort", cohort.name)
        result["skipped"] = True
        return result

    # 3. Probe count
    count = await _probe_record_count(page)
    result["actual"] = count
    logger.info("[%s] tag=%s count=%s (expected ~%d)",
                cohort.name, cohort.tag, count, cohort.expected_count)

    if count == 0:
        logger.warning("[%s] 0 records — skipping cohort", cohort.name)
        result["skipped"] = True
        return result

    if dry_run:
        logger.info("[%s] DRY RUN — would set status='%s', tags=%s, board=%s/%s",
                    cohort.name, cohort.status, cohort.extra_tags or [],
                    cohort.board, cohort.phase)
        result["skipped"] = True
        return result

    # 4. Select records
    if limit == 1:
        logger.info("[%s] LIMIT 1 — selecting first record only", cohort.name)
        selected = await _select_first_record_only(page)
    else:
        selected = await _select_all_records(page)
    if not selected:
        logger.error("[%s] Select failed — skipping cohort", cohort.name)
        result["skipped"] = True
        return result

    do_status = not skip_status
    do_tags = bool(cohort.extra_tags) and not skip_tags
    do_boards = bool(cohort.board and cohort.phase) and not skip_boards

    # 5. Change Property Status
    if do_status:
        logger.info("[%s] Setting Property Status -> %s",
                    cohort.name, cohort.status)
        result["status_set"] = await _bulk_change_status(page, cohort.status)
        if not result["status_set"]:
            logger.error("[%s] Status change FAILED — aborting cohort", cohort.name)
            return result
        await page.wait_for_timeout(2000)

        # After Save status, selection MAY have cleared. Re-select if more steps follow.
        if do_tags or do_boards:
            if limit == 1:
                await _select_first_record_only(page)
            else:
                await _select_all_records(page)
            await page.wait_for_timeout(1500)
    else:
        logger.info("[%s] skip_status=True — leaving Property Status as-is",
                    cohort.name)

    # 6. Add tags
    if do_tags:
        logger.info("[%s] Adding tags: %s", cohort.name, cohort.extra_tags)
        result["tags_added"] = await _bulk_add_tags(page, cohort.extra_tags)
        await page.wait_for_timeout(2000)

        # Re-select before Siftline if needed
        if do_boards:
            if limit == 1:
                await _select_first_record_only(page)
            else:
                await _select_all_records(page)
            await page.wait_for_timeout(1500)
    elif cohort.extra_tags and skip_tags:
        logger.info("[%s] skip_tags=True — leaving tags unchanged", cohort.name)

    # 7. SiftLine board placement
    if do_boards:
        logger.info("[%s] Sending to SiftLine: %s / %s",
                    cohort.name, cohort.board, cohort.phase)
        result["board_set"] = await _bulk_send_to_siftline(
            page, cohort.board, cohort.phase
        )
    elif cohort.board and skip_boards:
        logger.info("[%s] skip_boards=True — leaving SiftLine cards unchanged",
                    cohort.name)

    return result


# ── Discovery: dump bulk-action menus ──────────────────────────────────

async def _dump_top_bar_buttons(page: Page) -> list[dict]:
    """After select-all, dump every visible top-bar action button.

    Returns a list of {text, x, y, w, h, tag, cls} dicts so we can see
    exactly what bulk-action entry points appear (Manage / Send To / etc.).
    """
    return await page.evaluate(r"""() => {
        const out = [];
        const btns = document.querySelectorAll('button, [role="button"], a');
        for (const el of btns) {
            const t = (el.innerText || el.textContent || '').trim();
            const rect = el.getBoundingClientRect();
            if (!t || t.length > 60) continue;
            if (rect.height === 0 || rect.width === 0) continue;
            // Top-bar action region: roughly y < 250 (the records table starts
            // below the action bar). Skip sidebar (x < 220).
            if (rect.y > 260 || rect.x < 220) continue;
            out.push({
                text: t,
                tag: el.tagName,
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                w: Math.round(rect.width),
                h: Math.round(rect.height),
                cls: (el.className || '').toString().substring(0, 80),
            });
        }
        // De-dup by text+y
        const seen = new Set();
        return out.filter(o => {
            const k = o.text + ':' + o.y;
            if (seen.has(k)) return false;
            seen.add(k);
            return true;
        });
    }""")


async def _dump_dropdown_after_click(page: Page, button_text: str) -> dict:
    """Click a top-bar button by exact text and dump whatever dropdown opens.

    Returns {clicked: bool, items: [{text, x, y, w, h, cls}], post_click_buttons: [...]}.
    Doesn't commit anything — caller can close the dropdown via Escape after.
    """
    out = {"button": button_text, "clicked": False, "items": [], "post_click_buttons": []}

    btn = page.locator(f'button:has-text("{button_text}")')
    if await btn.count() == 0:
        btn = page.locator(f'text="{button_text}"')
    if await btn.count() == 0:
        logger.warning("Button '%s' not found", button_text)
        return out

    try:
        # Click via JS to dodge any pointer interception
        await btn.first.evaluate("el => el.click()")
        await page.wait_for_timeout(1200)
        out["clicked"] = True
    except Exception as e:
        logger.warning("Click on '%s' failed: %s", button_text, e)
        return out

    # Dump everything that looks like a dropdown menu item
    out["items"] = await page.evaluate(r"""() => {
        const items = [];
        const sels = [
            '[class*="Dropdown"] *',
            '[class*="Menu"] *',
            '[class*="Option"]',
            '[role="menuitem"]',
            '[role="option"]',
        ];
        const seen = new Set();
        for (const sel of sels) {
            for (const el of document.querySelectorAll(sel)) {
                const t = (el.innerText || el.textContent || '').trim();
                if (!t || t.length > 80 || el.children.length > 5) continue;
                const rect = el.getBoundingClientRect();
                if (rect.height === 0 || rect.width === 0) continue;
                if (rect.y < 0 || rect.y > 900) continue;
                const key = t + ':' + Math.round(rect.x) + ':' + Math.round(rect.y);
                if (seen.has(key)) continue;
                seen.add(key);
                items.push({
                    text: t,
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    w: Math.round(rect.width),
                    h: Math.round(rect.height),
                    cls: (el.className || '').toString().substring(0, 80),
                });
            }
        }
        return items;
    }""")

    return out


async def discover_bulk_actions(page: Page, cohort: Cohort) -> dict:
    """Phase 1: filter to a cohort, select all, dump every menu + the 3 target modals.

    Outputs are logged and screenshotted. NO mutations — every modal is
    dismissed via ESC/Cancel without committing.
    """
    report: dict = {"cohort": cohort.name, "tag": cohort.tag}

    # Switch to "All" view BEFORE filtering so Incomplete-bucketed Podio
    # records aren't hidden. Default Sift view is "Clean" only.
    await _switch_to_all_view(page)
    await _screenshot(page, "discover_after_all_toggle")

    # Filter
    filtered = await _filter_by_tag(page, cohort.tag)
    report["filtered"] = filtered
    if not filtered:
        logger.error("Filter failed — bailing out of discovery")
        return report

    # Probe count BEFORE select-all (probe opens CheckboxDropdown, reads N,
    # closes via Escape — doesn't actually select).
    count = await _probe_record_count(page)
    report["count"] = count
    logger.info("Cohort '%s' filter applied — count: %s (mapping says %d)",
                cohort.name, count, cohort.expected_count)

    # Now do the real select-all
    selected = await _select_all_records(page)
    report["selected"] = selected
    if not selected:
        logger.error("Select-all failed — bailing out of discovery")
        return report

    await page.wait_for_timeout(1500)
    await _dismiss_popups(page)

    # Snapshot every action button visible after select
    top_bar = await _dump_top_bar_buttons(page)
    report["top_bar_buttons"] = top_bar
    logger.info("Top-bar buttons after select-all (%d):", len(top_bar))
    for b in top_bar:
        logger.info("  [%s] '%s' at (%d,%d) %dx%d  cls=%s",
                    b["tag"], b["text"], b["x"], b["y"], b["w"], b["h"], b["cls"])

    await _screenshot(page, "discover_after_selectall")

    # ── Drill into the 3 target modals ────────────────────────────────
    # For each: open the modal, dump its inputs/buttons/dropdowns/options,
    # screenshot, dismiss without committing.
    report["modals"] = {}

    targets = [
        ("Manage", "Change status",   "manage_change_status"),
        ("Manage", "Add tags",        "manage_add_tags"),
        ("Send to", "Siftline",       "sendto_siftline"),
    ]

    for top, action, slug in targets:
        logger.info("─" * 50)
        logger.info("Discovering modal: %s > %s", top, action)
        if top == "Manage":
            opened = await _open_manage_action(page, action)
        else:
            opened = await _open_send_to_action(page, action)

        if not opened:
            report["modals"][slug] = {"opened": False}
            await _close_modal(page)
            continue

        await page.wait_for_timeout(1500)
        await _screenshot(page, f"discover_modal_{slug}_initial")

        dump = await _dump_action_modal(page)
        report["modals"][slug] = {"opened": True, "dump": dump}

        logger.info("'%s > %s' modal — headings (%d):", top, action, len(dump["headings"]))
        for h in dump["headings"]:
            logger.info("    H: '%s' at (%d,%d)", h["text"], h["x"], h["y"])
        logger.info("'%s > %s' modal — inputs (%d):", top, action, len(dump["inputs"]))
        for i in dump["inputs"]:
            logger.info("    I: tag=%s ph='%s' val='%s' at (%d,%d) %dx%d",
                        i["tag"], i["ph"], i["text"], i["x"], i["y"], i["w"], i["h"])
        logger.info("'%s > %s' modal — select_values (%d):", top, action, len(dump["select_values"]))
        for s in dump["select_values"]:
            logger.info("    S: '%s' at (%d,%d) cls=%s", s["text"], s["x"], s["y"], s["cls"])
        logger.info("'%s > %s' modal — buttons (%d):", top, action, len(dump["buttons"]))
        for b in dump["buttons"]:
            logger.info("    B: '%s' at (%d,%d) cls=%s", b["text"], b["x"], b["y"], b["cls"])
        logger.info("'%s > %s' modal — options visible (%d):", top, action, len(dump["options"]))
        for o in dump["options"][:30]:  # cap noise
            logger.info("    O: '%s' at (%d,%d) cls=%s", o["text"], o["x"], o["y"], o["cls"])

        # If there's a SelectValue (status picker, board picker), click it
        # to reveal the option list — that's the actual content we need.
        if dump["select_values"]:
            logger.info("Probing SelectValue dropdowns to expose options...")
            await page.evaluate(r"""() => {
                // Click the LAST visible SelectValue (modal's primary picker —
                // sidebar SelectValues live at x < 220 and are filtered out)
                const svs = document.querySelectorAll('[class*="SelectValue"]');
                let last = null;
                for (const sv of svs) {
                    const r = sv.getBoundingClientRect();
                    if (r.x > 220 && r.height > 0 && r.y > 0 && r.y < 900) {
                        last = sv;
                    }
                }
                if (last) last.click();
            }""")
            await page.wait_for_timeout(1200)
            await _screenshot(page, f"discover_modal_{slug}_selectvalue_open")

            opened_dump = await _dump_action_modal(page)
            report["modals"][slug]["dump_with_selectvalue_open"] = opened_dump
            logger.info("After SelectValue click — options now visible (%d):",
                        len(opened_dump["options"]))
            for o in opened_dump["options"][:50]:
                logger.info("    O: '%s' at (%d,%d) cls=%s",
                            o["text"], o["x"], o["y"], o["cls"])

        # Always dismiss without committing
        await _close_modal(page)
        await page.wait_for_timeout(800)
        await _screenshot(page, f"discover_modal_{slug}_closed")

    # ── Board-phase discovery ─────────────────────────────────────────
    # Open Send to > Siftline once and pick each target board to surface
    # its phase list. This is the only way to learn the actual phase names
    # (e.g. "Appointment / Make Offer", "New Contract", "Title Issues").
    logger.info("─" * 50)
    logger.info("Discovering board phases via Send to > Siftline...")
    report["board_phases"] = await _discover_board_phases(
        page, ["Lead Management", "Acquisitions", "Transactions", "Wholesale"]
    )

    return report


async def _discover_board_phases(page: Page, board_names: list[str]) -> dict:
    """Open Send to > Siftline, pick each board, dump its phase list.

    Closes the modal between boards so each board pick is a fresh modal
    open — avoids stale state from the previous phase dropdown.

    Returns: {board_name: [phase, phase, ...]}.
    """
    out: dict[str, list[str]] = {}

    for board in board_names:
        logger.info("→ Discovering phases for board: %s", board)

        # Open the modal fresh each iteration
        opened = await _open_send_to_action(page, "Siftline")
        if not opened:
            logger.warning("Could not open Send to > Siftline for board '%s'", board)
            await _close_modal(page)
            out[board] = []
            continue

        await page.wait_for_timeout(1200)

        # Pick the board: click the FIRST SelectValue (board picker, leftmost),
        # then click the option matching the board name.
        clicked_board = await page.evaluate(r"""(targetBoard) => {
            // First SelectValue at x > 220 is the board picker (leftmost in modal)
            const svs = document.querySelectorAll('[class*="SelectValue"]');
            let boardPicker = null;
            for (const sv of svs) {
                const r = sv.getBoundingClientRect();
                if (r.x > 220 && r.height > 0 && r.y > 0 && r.y < 900) {
                    if (boardPicker === null || r.x < boardPicker.getBoundingClientRect().x) {
                        boardPicker = sv;
                    }
                }
            }
            if (!boardPicker) return {ok: false, why: 'no_board_picker'};
            boardPicker.click();
            return {ok: true};
        }""", board)
        if not clicked_board.get("ok"):
            logger.warning("Board picker open failed: %s", clicked_board)
            await _close_modal(page)
            out[board] = []
            continue
        await page.wait_for_timeout(800)

        # Click the matching board option in the now-open dropdown
        picked = await page.evaluate(r"""(targetBoard) => {
            const opts = document.querySelectorAll(
                '[class*="SelectOptionDisplayValueContainer"], '
                + '[class*="SelectOptionContainer"]'
            );
            for (const o of opts) {
                const t = (o.innerText || o.textContent || '').trim();
                const r = o.getBoundingClientRect();
                if (t === targetBoard && r.height > 0 && r.x > 220) {
                    o.click();
                    return {clicked: true};
                }
            }
            return {clicked: false};
        }""", board)
        if not picked.get("clicked"):
            logger.warning("Board option '%s' not found in dropdown", board)
            await _close_modal(page)
            out[board] = []
            continue

        await page.wait_for_timeout(1500)
        await _screenshot(page, f"discover_board_{board.replace(' ', '_').lower()}_picked")

        # Now open the phase picker (the SECOND SelectValue — to the right
        # of the board picker, was showing "—" / dash before board pick).
        opened_phase = await page.evaluate(r"""() => {
            const svs = document.querySelectorAll('[class*="SelectValue"]');
            // Visible SVs sorted by x — pick the rightmost (phase picker)
            const visible = [];
            for (const sv of svs) {
                const r = sv.getBoundingClientRect();
                if (r.x > 220 && r.height > 0 && r.y > 0 && r.y < 900) {
                    visible.push({el: sv, x: r.x});
                }
            }
            visible.sort((a, b) => b.x - a.x);
            if (visible.length === 0) return {ok: false};
            visible[0].el.click();
            return {ok: true, x: Math.round(visible[0].x)};
        }""")
        if not opened_phase.get("ok"):
            logger.warning("Phase picker not found for board '%s'", board)
            out[board] = []
            await _close_modal(page)
            continue
        await page.wait_for_timeout(1000)
        await _screenshot(page, f"discover_board_{board.replace(' ', '_').lower()}_phases_open")

        # Dump phases — they live in the now-open option container
        phases_raw = await page.evaluate(r"""() => {
            const opts = document.querySelectorAll(
                '[class*="SelectOptionDisplayValueContainer"]'
            );
            const out = [];
            const seen = new Set();
            for (const o of opts) {
                const t = (o.innerText || o.textContent || '').trim();
                const r = o.getBoundingClientRect();
                if (!t || t.length > 80) continue;
                if (r.height === 0 || r.x < 220) continue;
                if (seen.has(t)) continue;
                seen.add(t);
                out.push({text: t, x: Math.round(r.x), y: Math.round(r.y)});
            }
            // Sort by y so phases appear in board order
            out.sort((a, b) => a.y - b.y);
            return out;
        }""")
        # Filter out the board names themselves (they show in the board
        # picker option list which may still be in the DOM) — phases are
        # the items that AREN'T the boards we know about.
        known_boards = set(board_names) | {"Choose a board", "Choose a phase"}
        phase_texts = [p["text"] for p in phases_raw if p["text"] not in known_boards]
        out[board] = phase_texts
        logger.info("  Board '%s' phases (%d): %s", board, len(phase_texts), phase_texts)

        await _close_modal(page)
        await page.wait_for_timeout(1000)

    return out


# ── Main entry ─────────────────────────────────────────────────────────

async def _run(args) -> int:
    # Cohort selection: --cohort filters to one; default = run ALL cohorts.
    if args.cohort:
        cohorts = [c for c in COHORTS if c.name.lower() == args.cohort.lower()]
        if not cohorts:
            logger.error("Unknown cohort '%s'. Available: %s",
                         args.cohort, ", ".join(c.name for c in COHORTS))
            return 1
    else:
        cohorts = list(COHORTS)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=args.headless)
        ctx = await browser.new_context(
            viewport={"width": 1600, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"),
        )
        page = await ctx.new_page()

        ok = await login(page)
        if not ok:
            logger.error("Login failed — aborting")
            return 2

        await page.goto(DATASIFT_RECORDS_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        await _dismiss_popups(page)

        if args.discover:
            # Discovery mode requires exactly one cohort
            cohort = cohorts[0]
            report = await discover_bulk_actions(page, cohort)
            logger.info("=" * 60)
            logger.info("DISCOVERY REPORT for cohort '%s' (tag=%s)",
                        cohort.name, cohort.tag)
            logger.info("=" * 60)
            for board, phases in (report.get("board_phases") or {}).items():
                logger.info("  Board '%s' phases: %s", board, phases)
            logger.info("=" * 60)
            logger.info("Filtered: %s | Count: %s | Selected: %s",
                        report.get("filtered"), report.get("count"),
                        report.get("selected"))
            logger.info("Top-bar buttons: %d", len(report.get("top_bar_buttons", [])))
            for name, dump in report.get("dropdowns", {}).items():
                logger.info("Dropdown '%s' clicked=%s items=%d",
                            name, dump.get("clicked"), len(dump.get("items", [])))
            logger.info("Screenshots written to working dir as datasift_*.png")
            logger.info("=" * 60)

            if not args.headless:
                logger.info("Pausing 30s so you can inspect the browser...")
                await page.wait_for_timeout(30000)
            await browser.close()
            return 0

        # ── Bulk action mode (Phase 2) ────────────────────────────────
        results: list[dict] = []
        for cohort in cohorts:
            logger.info("=" * 60)
            logger.info("COHORT: %s  tag=%s  target=%s%s%s",
                        cohort.name, cohort.tag, cohort.status,
                        f" tags={cohort.extra_tags}" if cohort.extra_tags else "",
                        f" board={cohort.board}/{cohort.phase}" if cohort.board else "")
            logger.info("=" * 60)

            res = await process_cohort(
                page, cohort,
                dry_run=args.dry_run,
                limit=args.limit,
                skip_status=args.skip_status,
                skip_tags=args.skip_tags,
                skip_boards=args.skip_boards,
            )
            results.append(res)

            # Return to clean records view between cohorts
            await page.goto(DATASIFT_RECORDS_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            await _dismiss_popups(page)

        # ── Final summary ──────────────────────────────────────────────
        logger.info("=" * 60)
        logger.info("FINAL SUMMARY (%d cohorts)", len(results))
        logger.info("=" * 60)
        for r in results:
            logger.info(
                "[%s] count=%s/expected~%s  status=%s  tags=%s  board=%s%s",
                r["cohort"], r.get("actual"), r.get("expected"),
                "OK" if r["status_set"] else ("DRY" if args.dry_run else "FAIL"),
                "OK" if r["tags_added"] else "—",
                "OK" if r["board_set"] else "—",
                "  (skipped)" if r.get("skipped") else "",
            )
        logger.info("=" * 60)

        await browser.close()
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort", default=None,
                   help="Run only this cohort (default: all 13)")
    p.add_argument("--discover", action="store_true",
                   help="Phase 1: filter + select-all + dump menus, no mutations")
    p.add_argument("--dry-run", action="store_true",
                   help="Filter + count only; no mutations")
    p.add_argument("--limit", type=int, default=0,
                   help="Apply to only the first N records of the cohort "
                        "(smoke test). Currently only --limit 1 is supported.")
    p.add_argument("--headless", action="store_true",
                   help="Run headless (default: headful)")
    p.add_argument("--skip-status", action="store_true",
                   help="Repair flag: skip the Property Status update step")
    p.add_argument("--skip-tags", action="store_true",
                   help="Repair flag: skip the Add Tags step (e.g., DNC tag)")
    p.add_argument("--skip-boards", action="store_true",
                   help="Repair flag: skip the Send to SiftLine board placement "
                        "(use during status-only repair to avoid duplicate cards)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    # Discovery defaults: if --discover is set without --cohort, use Discovery
    if args.discover and not args.cohort:
        args.cohort = "Discovery"

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    rc = asyncio.run(_run(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
