"""Diff (and optionally sync) the Apify schedule's runInput.body against
input.cloud.json.

The Apify schedule stores its input as a JSON-encoded string under
actions[0].runInput.body. That blob is a SNAPSHOT — if input.cloud.json
gains new keys (a new credential, a new toggle), the schedule keeps using
the old snapshot until manually re-synced. This bit Sean on 2026-04-25
when MS_GRAPH credentials were missing from the schedule and the daily
run shipped Apify KVS links to Slack instead of OneDrive.

Usage:
    # Show drift (read-only)
    python scripts/sync_schedule_input.py

    # Apply input.cloud.json overrides into the schedule
    python scripts/sync_schedule_input.py --apply

    # Use a different input file (e.g. input.json for a one-off schedule)
    python scripts/sync_schedule_input.py --input input.json --apply

    # Use a different schedule by id (default: the one in code)
    python scripts/sync_schedule_input.py --schedule <SCHED_ID> --apply

Returns exit code 1 if drift exists and --apply was NOT passed (CI hook
material — fail the build if input.cloud.json was edited but schedule
wasn't re-synced).

Environment:
    APIFY_API_TOKEN — falls back to APIFY_TOKEN. Required.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests


REPO = Path(__file__).resolve().parent.parent
DEFAULT_SCHEDULE_ID = "5hYZIZN7r7OsnZWfL"  # siftstack-oh-daily-9am-et
DEFAULT_INPUT_FILE = REPO / "input.cloud.json"

# Keys that should always be set as fixed values for SCHEDULED runs
# (they shouldn't track any since_date / scope override left over in
# input.cloud.json from a manual one-off backfill).
SCHEDULE_OVERRIDES = {
    "mode": "daily",
    "counties": [],
    "types": [],
    "since_date": "",
}


def load_token() -> str:
    """Resolve API token from env, .env, or ~/.apify/auth.json (CLI login)."""
    tok = os.environ.get("APIFY_API_TOKEN") or os.environ.get("APIFY_TOKEN")
    if not tok:
        env = REPO / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("APIFY_TOKEN="):
                    tok = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not tok:
        # Apify CLI login state
        cli_auth = Path.home() / ".apify" / "auth.json"
        if cli_auth.exists():
            try:
                tok = json.loads(cli_auth.read_text()).get("token")
            except Exception:
                pass
    if not tok:
        print("error: no Apify API token found. Set APIFY_API_TOKEN, "
              "or run `apify login`.", file=sys.stderr)
        sys.exit(2)
    return tok


def fetch_schedule(token: str, sched_id: str) -> dict:
    r = requests.get(
        f"https://api.apify.com/v2/schedules/{sched_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["data"]


def schedule_input(sched: dict) -> dict:
    if not sched.get("actions"):
        return {}
    body = sched["actions"][0].get("runInput", {}).get("body", "")
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def diff_inputs(local: dict, remote: dict) -> dict:
    """Compare local vs remote input. Returns dict of changes."""
    out = {"missing_from_remote": [], "extra_in_remote": [], "value_changes": []}
    for k in sorted(set(local) | set(remote)):
        lv = local.get(k, "<<MISSING>>")
        rv = remote.get(k, "<<MISSING>>")
        if k not in remote:
            out["missing_from_remote"].append((k, lv))
        elif k not in local:
            out["extra_in_remote"].append((k, rv))
        elif lv != rv:
            out["value_changes"].append((k, lv, rv))
    return out


def write_schedule(token: str, sched: dict, new_input: dict) -> None:
    new_actions = []
    for a in sched["actions"]:
        new_actions.append({
            **a,
            "runInput": {
                "body": json.dumps(new_input),
                "contentType": "application/json",
            },
        })
    payload = {
        "name": sched["name"],
        "title": sched.get("title", ""),
        "cronExpression": sched["cronExpression"],
        "timezone": sched.get("timezone", "America/New_York"),
        "isEnabled": sched.get("isEnabled", True),
        "isExclusive": sched.get("isExclusive", True),
        "description": sched.get("description") or "",
        "actions": new_actions,
    }
    r = requests.put(
        f"https://api.apify.com/v2/schedules/{sched['id']}",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--schedule", default=DEFAULT_SCHEDULE_ID,
                   help=f"Schedule id (default: {DEFAULT_SCHEDULE_ID})")
    p.add_argument("--input", default=str(DEFAULT_INPUT_FILE),
                   help=f"Input JSON file (default: {DEFAULT_INPUT_FILE.name})")
    p.add_argument("--apply", action="store_true",
                   help="Apply local input to the schedule (otherwise diff-only)")
    args = p.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"error: {input_path} not found", file=sys.stderr)
        return 2
    local = json.loads(input_path.read_text(encoding="utf-8"))
    # Apply schedule-specific overrides (mode=daily etc.) on top of local
    desired = {**local, **SCHEDULE_OVERRIDES}

    token = load_token()
    sched = fetch_schedule(token, args.schedule)
    remote = schedule_input(sched)

    print(f"Schedule:  {sched.get('name')!r}  ({sched['id']})")
    print(f"Cron:      {sched.get('cronExpression')!r} {sched.get('timezone','')}")
    print(f"Input src: {input_path}")
    print(f"  desired keys: {len(desired)}")
    print(f"  remote keys:  {len(remote)}")

    diffs = diff_inputs(desired, remote)
    drift = (diffs["missing_from_remote"] or diffs["extra_in_remote"]
             or diffs["value_changes"])

    if not drift:
        print("\n✓ in sync — schedule input matches local")
        return 0

    print("\n⚠ DRIFT DETECTED:")
    if diffs["missing_from_remote"]:
        print(f"  {len(diffs['missing_from_remote'])} keys present locally but "
              "MISSING from schedule:")
        for k, lv in diffs["missing_from_remote"]:
            preview = "<{}-char secret>".format(len(lv)) if isinstance(lv, str) and len(lv) > 30 else repr(lv)
            print(f"    + {k}: {preview}")
    if diffs["extra_in_remote"]:
        print(f"  {len(diffs['extra_in_remote'])} keys in schedule but NOT in "
              "local input:")
        for k, rv in diffs["extra_in_remote"]:
            print(f"    - {k}")
    if diffs["value_changes"]:
        print(f"  {len(diffs['value_changes'])} keys with different values:")
        for k, lv, rv in diffs["value_changes"]:
            preview_l = "<{}-char>".format(len(lv)) if isinstance(lv, str) and len(lv) > 30 else repr(lv)
            preview_r = "<{}-char>".format(len(rv)) if isinstance(rv, str) and len(rv) > 30 else repr(rv)
            print(f"    ~ {k}: local={preview_l}  remote={preview_r}")

    if not args.apply:
        print("\nRe-run with --apply to push local input to the schedule.")
        return 1

    print("\nApplying...")
    write_schedule(token, sched, desired)
    # Verify
    sched2 = fetch_schedule(token, args.schedule)
    remote2 = schedule_input(sched2)
    diffs2 = diff_inputs(desired, remote2)
    if (diffs2["missing_from_remote"] or diffs2["extra_in_remote"]
            or diffs2["value_changes"]):
        print("error: drift still present after apply", file=sys.stderr)
        return 3
    print(f"✓ schedule input synced ({len(desired)} keys)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
