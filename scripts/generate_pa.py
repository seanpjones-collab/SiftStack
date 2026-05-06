"""
Generate and send a DocuSign Purchase Agreement envelope.

Usage:
    # Inspect template to see what tabs DocuSign has and their actual tabLabels.
    # Run this once after the template is finalized to build the tooltip map.
    python scripts/generate_pa.py --inspect-template

    # Dry-run: build the payload and print it. No envelope is created.
    python scripts/generate_pa.py --dryrun \\
        --street "123 Main St" --city Akron --state OH --zip 44306 \\
        --price 50000 --seller-name "John Doe" --seller-email john@example.com

    # Actually send.
    python scripts/generate_pa.py \\
        --street "123 Main St" --city Akron --state OH --zip 44306 \\
        --price 50000 --seller-name "John Doe" --seller-email john@example.com

Optional flags:
    --emd 2000                      # default 1000
    --close-date 2026-06-15         # default = today + 30 days
    --inspection-days 14            # default 7
    --acceptance-days 3             # default 2 (seller has N days to accept)
    --county Summit                 # county name only
    --legal-description "Parcel ..." # legal/parcel ID
    --title-company "ABC Title"     # default from .env ALWORTH_DEFAULT_TITLE_CO
    --additional-terms "..."        # Section 19 additional terms
    --seller-mailing-street ...     # defaults to property street
    --seller-mailing-city/state/zip # defaults to property values

Required env vars (in .env):
    DOCUSIGN_INTEGRATION_KEY, DOCUSIGN_USER_ID, DOCUSIGN_ACCOUNT_ID,
    DOCUSIGN_PRIVATE_KEY_PATH, DOCUSIGN_PA_TEMPLATE_ID,
    DOCUSIGN_BASE_URL, DOCUSIGN_API_BASE_URL

Optional env vars (with sensible defaults):
    ALWORTH_BUYER_NAME (default "Sean Jones")
    ALWORTH_BUYER_EMAIL (default "sean@alworthhomes.com")
    ALWORTH_ACQ_NAME (default "Zane Stacy")
    ALWORTH_ACQ_EMAIL (default "zane@alworthhomes.com")
    ALWORTH_DEFAULT_TITLE_CO (no default)
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from docusign_esign import (
    ApiClient,
    Envelope,
    EnvelopeDefinition,
    EnvelopesApi,
    Expirations,
    Notification,
    PrefillTabs,
    Tabs,
    TemplateRole,
    TemplatesApi,
    Text,
)
from dotenv import load_dotenv

load_dotenv()

# --- Env vars ---
INTEGRATION_KEY = os.getenv("DOCUSIGN_INTEGRATION_KEY")
USER_ID = os.getenv("DOCUSIGN_USER_ID")
ACCOUNT_ID = os.getenv("DOCUSIGN_ACCOUNT_ID")
PRIVATE_KEY_PATH = os.getenv("DOCUSIGN_PRIVATE_KEY_PATH", "docusign_private_key.pem")
TEMPLATE_ID = os.getenv("DOCUSIGN_PA_TEMPLATE_ID")
BASE_URL = os.getenv("DOCUSIGN_BASE_URL", "https://account-d.docusign.com")
API_BASE_URL = os.getenv("DOCUSIGN_API_BASE_URL", "https://demo.docusign.net/restapi")

BUYER_NAME = os.getenv("ALWORTH_BUYER_NAME", "Sean Jones")
BUYER_EMAIL = os.getenv("ALWORTH_BUYER_EMAIL", "sean@alworthhomes.com")
ACQ_NAME = os.getenv("ALWORTH_ACQ_NAME", "Zane Stacy")
ACQ_EMAIL = os.getenv("ALWORTH_ACQ_EMAIL", "zane@alworthhomes.com")
DEFAULT_TITLE_CO = os.getenv("ALWORTH_DEFAULT_TITLE_CO", "")

CACHE_DIR = Path(".cache")
TABS_CACHE_PATH = CACHE_DIR / "docusign_pa_template_tabs.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    # Modes
    p.add_argument("--inspect-template", action="store_true",
                   help="Fetch template tabs; print and cache tooltip -> tabLabel mapping")
    p.add_argument("--dryrun", action="store_true",
                   help="Build payload but do not send envelope")

    # Property
    p.add_argument("--street", help="Property street address")
    p.add_argument("--city")
    p.add_argument("--state", default="OH")
    p.add_argument("--zip", dest="zip_code")
    p.add_argument("--county", default=None)
    p.add_argument("--legal-description", default=None,
                   help="Parcel ID or legal description (Section 2c)")

    # Seller
    p.add_argument("--seller-name")
    p.add_argument("--seller-email")
    p.add_argument("--seller-tax-id", default=None)
    p.add_argument("--seller-mailing-street", default=None)
    p.add_argument("--seller-mailing-city", default=None)
    p.add_argument("--seller-mailing-state", default=None)
    p.add_argument("--seller-mailing-zip", default=None)

    # Deal terms
    p.add_argument("--price", type=int, help="Purchase price in whole dollars")
    p.add_argument("--emd", type=int, default=100, help="Earnest money deposit in dollars (default 100)")
    p.add_argument("--close-date", default=None, help="YYYY-MM-DD; default = today + 30 days")
    p.add_argument("--inspection-days", type=int, default=7)
    p.add_argument("--acceptance-days", type=int, default=1,
                   help="Days seller has to accept (default 1 = 24 hours). Also drives envelope auto-expiration.")
    p.add_argument("--title-company", default=None)
    p.add_argument("--additional-terms", default=None,
                   help="Section 19 — extra terms beyond 'Contingent Clear title and Investor approval'")

    # Section 18 — Addenda and Advisories (names of attached docs, free-text)
    p.add_argument("--addenda-1", default=None)
    p.add_argument("--addenda-2", default=None)
    p.add_argument("--advisory-1", default=None)
    p.add_argument("--advisory-2", default=None)
    p.add_argument("--advisory-3", default=None)
    p.add_argument("--advisory-4", default=None)

    return p.parse_args()


def authenticate() -> ApiClient:
    """JWT auth flow. Returns ApiClient configured with bearer token."""
    if not all([INTEGRATION_KEY, USER_ID, ACCOUNT_ID, TEMPLATE_ID]):
        sys.exit("ERROR: missing required env vars. Need DOCUSIGN_INTEGRATION_KEY, "
                 "DOCUSIGN_USER_ID, DOCUSIGN_ACCOUNT_ID, DOCUSIGN_PA_TEMPLATE_ID")

    private_key_path = Path(PRIVATE_KEY_PATH)
    if not private_key_path.exists():
        sys.exit(f"ERROR: private key not found at {private_key_path.absolute()}")

    api_client = ApiClient()
    auth_host = BASE_URL.replace("https://", "").replace("http://", "")
    api_client.set_oauth_host_name(auth_host)

    with open(private_key_path, "rb") as f:
        key_bytes = f.read()

    response = api_client.request_jwt_user_token(
        client_id=INTEGRATION_KEY,
        user_id=USER_ID,
        oauth_host_name=auth_host,
        private_key_bytes=key_bytes,
        expires_in=3600,
        scopes=["signature", "impersonation"],
    )
    api_client.host = API_BASE_URL
    api_client.set_default_header("Authorization", f"Bearer {response.access_token}")
    return api_client


def inspect_template(api_client: ApiClient) -> None:
    """Fetch template; print tab_id, tab_label, tooltip, required for every tab."""
    templates_api = TemplatesApi(api_client)
    print(f"Fetching template {TEMPLATE_ID}...\n")
    template = templates_api.get(ACCOUNT_ID, TEMPLATE_ID)

    tooltip_to_label: dict[str, str] = {}
    required_tabs: list[dict] = []

    print(f"Template: {template.name}\n")

    # Pre-fill tabs live on documents
    print("=== Pre-fill (Sender) Tabs ===")
    if template.documents:
        for doc in template.documents:
            doc_id = getattr(doc, "document_id", "?")
            doc_name = getattr(doc, "name", "?")
            print(f"\n  Document {doc_id}: {doc_name}")

            tabs_obj = getattr(doc, "tabs", None) or getattr(doc, "document_fields", None)
            prefill_tabs = getattr(tabs_obj, "prefill_tabs", None) if tabs_obj else None

            if not prefill_tabs:
                # Try per-document tabs API
                try:
                    doc_tabs = templates_api.get_document_tabs(ACCOUNT_ID, doc_id, TEMPLATE_ID)
                    prefill_tabs = getattr(doc_tabs, "prefill_tabs", None)
                except Exception:
                    pass

            if not prefill_tabs:
                continue

            for t in (getattr(prefill_tabs, "text_tabs", None) or []):
                tab_id = getattr(t, "tab_id", "") or ""
                label = getattr(t, "tab_label", "") or ""
                tooltip = (getattr(t, "tooltip", "") or "").strip()
                required = str(getattr(t, "required", "false")).lower()
                value = getattr(t, "value", "") or ""
                req_marker = "*REQ*" if required == "true" else "     "
                print(f"    {req_marker} tabId={tab_id!r}  tabLabel={label!r}  tooltip={tooltip!r}  value={value!r}")
                if tooltip:
                    tooltip_to_label[tooltip] = label
                if required == "true":
                    required_tabs.append({
                        "tab_id": tab_id, "tab_label": label, "tooltip": tooltip,
                        "kind": "prefill", "doc_id": doc_id,
                    })

    # Recipient tabs — fetch explicitly via list_tabs (they don't always come back on the template GET)
    print("\n=== Recipient Tabs (via list_tabs) ===")
    if template.recipients and template.recipients.signers:
        for s in template.recipients.signers:
            recipient_id = getattr(s, "recipient_id", "")
            print(f"\n  Signer (role={s.role_name!r}, order={s.routing_order}, recipient_id={recipient_id!r}):")
            try:
                recipient_tabs = templates_api.list_tabs(ACCOUNT_ID, recipient_id, TEMPLATE_ID)
            except Exception as e:
                print(f"    ERR fetching tabs: {type(e).__name__}: {str(e)[:100]}")
                continue

            for tab_kind in ("text_tabs", "sign_here_tabs", "initial_here_tabs", "date_signed_tabs"):
                items = getattr(recipient_tabs, tab_kind, None) or []
                for t in items:
                    tab_id = getattr(t, "tab_id", "") or ""
                    label = getattr(t, "tab_label", "") or ""
                    tooltip = (getattr(t, "tooltip", "") or "").strip()
                    required = str(getattr(t, "required", "false")).lower()
                    req_marker = "*REQ*" if required == "true" else "     "
                    print(f"    [{tab_kind}] {req_marker} tabId={tab_id!r}  tabLabel={label!r}  tooltip={tooltip!r}")
                    if tab_kind == "text_tabs" and tooltip:
                        tooltip_to_label[tooltip] = label
                    if required == "true":
                        required_tabs.append({
                            "tab_id": tab_id, "tab_label": label, "tooltip": tooltip,
                            "kind": tab_kind, "role": s.role_name,
                        })

    # Required-tabs summary — easy reference for debugging REQUIRED_TAB_INCOMPLETE errors
    print(f"\n=== Required Tabs Summary ({len(required_tabs)} total) ===")
    for rt in required_tabs:
        loc = rt.get("role") or f"document {rt.get('doc_id', '?')}"
        print(f"  tabId={rt['tab_id']:38s}  kind={rt['kind']:18s}  tooltip={rt['tooltip']!r:35s}  ({loc})")

    # Save mapping to cache (now includes required_tabs)
    CACHE_DIR.mkdir(exist_ok=True)
    with open(TABS_CACHE_PATH, "w") as f:
        json.dump({
            "template_id": TEMPLATE_ID,
            "tooltip_to_tab_label": tooltip_to_label,
            "required_tabs": required_tabs,
        }, f, indent=2)
    print(f"\nSaved tooltip -> tabLabel map and required_tabs list to {TABS_CACHE_PATH}")
    print(f"Found {len(tooltip_to_label)} mapped tooltips, {len(required_tabs)} required tabs.")


def load_tabs_map() -> dict[str, str]:
    """Load tooltip -> tabLabel map from cache. Falls back to identity map if cache missing."""
    if not TABS_CACHE_PATH.exists():
        print(f"WARNING: {TABS_CACHE_PATH} not found. Falling back to tooltip = tabLabel.")
        print(f"         Run with --inspect-template to populate the cache.\n")
        return {}
    with open(TABS_CACHE_PATH) as f:
        data = json.load(f)
    if data.get("template_id") != TEMPLATE_ID:
        print(f"WARNING: cached template_id mismatch. Re-run --inspect-template.\n")
    return data.get("tooltip_to_tab_label", {})


def build_deal_data(args: argparse.Namespace) -> dict[str, str]:
    """Map CLI args to all 36 tooltip-keyed prefill values. Empty strings for blanks."""
    today = date.today()
    close_date = date.fromisoformat(args.close_date) if args.close_date else today + timedelta(days=30)
    inspection_deadline = today + timedelta(days=args.inspection_days)
    termination_deadline = inspection_deadline + timedelta(days=1)
    acceptance_deadline = today + timedelta(days=args.acceptance_days)

    seller_mailing_street = args.seller_mailing_street or args.street
    seller_mailing_city = args.seller_mailing_city or args.city
    seller_mailing_state = args.seller_mailing_state or args.state
    seller_mailing_zip = args.seller_mailing_zip or args.zip_code
    title_co = args.title_company or DEFAULT_TITLE_CO

    balance = args.price - args.emd

    return {
        # Section 1 — Parties
        "seller_name": args.seller_name,
        "seller_tax_id": args.seller_tax_id or "",
        "seller_mailing_street": seller_mailing_street,
        "seller_mailing_city": seller_mailing_city,
        "seller_mailing_state": seller_mailing_state,
        "seller_mailing_zip": seller_mailing_zip,
        # Section 2 — Property
        "property_street": args.street,
        "property_city": args.city,
        "property_county": args.county or "",
        "property_state": args.state,
        "property_zip": args.zip_code,
        "legal_description": args.legal_description or "",
        # Section 3 — Personal property (usually blank)
        "additional_personal_property": "",
        "excluded_personal_property": "",
        # Section 4 — Money
        "purchase_price": f"${args.price:,}",
        "emd_amount": f"${args.emd:,}",
        "additional_deposit_amount": "",
        "financing_proceeds_amount": "",
        "seller_financing_amount": "",
        "other_payment_description": "",
        "other_payment_amount": "",
        "balance_at_closing_amount": f"${balance:,}",
        "total_price_amount": f"${args.price:,}",
        # Section 7 — Inspection
        "inspection_deadline_date": inspection_deadline.strftime("%B %d, %Y"),
        "termination_notice_deadline_date": termination_deadline.strftime("%B %d, %Y"),
        # Section 9 — Closing
        "closing_date": close_date.strftime("%B %d, %Y"),
        "title_escrow_company": title_co,
        # Section 18 — Addenda/Advisories (free-text names of attached docs, often blank)
        "addenda_1": getattr(args, "addenda_1", None) or "",
        "addenda_2": getattr(args, "addenda_2", None) or "",
        "advisory_1": getattr(args, "advisory_1", None) or "",
        "advisory_2": getattr(args, "advisory_2", None) or "",
        "advisory_3": getattr(args, "advisory_3", None) or "",
        "advisory_4": getattr(args, "advisory_4", None) or "",
        # Section 19 — Additional terms
        "additional_terms": args.additional_terms or "",
        # Section 28 — Time to accept
        "seller_acceptance_deadline": f"5:00 PM ET on {acceptance_deadline.strftime('%B %d, %Y')}",
    }


def build_text_tab_overrides(deal: dict[str, str], tabs_map: dict[str, str]) -> list[Text]:
    """Build Text tab override list. Maps tooltips to tabLabels using cache, falls back to tooltip-as-label."""
    overrides = []
    skipped = []
    for tooltip, value in deal.items():
        if not value:
            continue
        label = tabs_map.get(tooltip, tooltip)  # fall back to tooltip if no cached mapping
        overrides.append(Text(tab_label=label, value=value))
        if tooltip not in tabs_map:
            skipped.append(tooltip)
    if skipped:
        print(f"  NOTE: {len(skipped)} tooltips not in cache; using tooltip as tabLabel directly: {skipped[:5]}{'...' if len(skipped) > 5 else ''}")
    return overrides


def generate_envelope(api_client: ApiClient, args: argparse.Namespace) -> dict | None:
    """Build and send envelope. Honors --dryrun.

    Returns a dict with envelope_id + view_url on a successful send,
    None on dryrun.
    """
    # Validate required args for non-inspect modes
    required = {"street", "city", "zip_code", "price", "seller_name", "seller_email"}
    missing = [k for k in required if not getattr(args, k, None)]
    if missing:
        sys.exit(f"ERROR: missing required args: {missing}")

    deal = build_deal_data(args)

    print(f"Property:     {deal['property_street']}, {deal['property_city']}, {deal['property_state']} {deal['property_zip']}")
    print(f"Seller:       {deal['seller_name']} ({args.seller_email})")
    print(f"Price:        {deal['purchase_price']}  EMD: {deal['emd_amount']}  Balance: {deal['balance_at_closing_amount']}")
    print(f"Closing:      {deal['closing_date']}")
    print(f"Inspection:   {deal['inspection_deadline_date']}  Termination: {deal['termination_notice_deadline_date']}")
    print(f"Acceptance:   {deal['seller_acceptance_deadline']}")
    print(f"Title:        {deal['title_escrow_company'] or '(not set)'}")
    print()

    if args.dryrun:
        print("=== DRY RUN — full prefill payload ===")
        for tooltip, value in deal.items():
            display = value if value else "(blank)"
            print(f"  {tooltip:35s} = {display}")
        print()
        print("(Stopping here — no envelope created.)")
        return

    tabs_map = load_tabs_map()
    text_tab_overrides = build_text_tab_overrides(deal, tabs_map)

    envelopes_api = EnvelopesApi(api_client)

    # Per DocuSign docs: prefill tab values cannot be set at envelope creation. The flow is:
    # 1) create envelope as DRAFT (status="created"),
    # 2) update document prefill tabs on the draft,
    # 3) change envelope status to "sent" to actually send it.

    # Step 1: Create as draft.
    buyer_role = TemplateRole(role_name="Buyer", name=BUYER_NAME, email=BUYER_EMAIL)
    acq_role = TemplateRole(role_name="Acquisitions", name=ACQ_NAME, email=ACQ_EMAIL)
    seller_role = TemplateRole(role_name="Seller", name=args.seller_name, email=args.seller_email)

    # Auto-expire envelope after the same window as the seller acceptance deadline.
    # If acceptance-days = 1, envelope auto-voids in 24 hours; matches Section 28 text.
    notification = Notification(
        expirations=Expirations(
            expire_enabled="true",
            expire_after=str(args.acceptance_days),
            expire_warn="0",
        ),
    )

    draft_def = EnvelopeDefinition(
        template_id=TEMPLATE_ID,
        template_roles=[buyer_role, acq_role, seller_role],
        notification=notification,
        status="created",  # DRAFT
        email_subject=f"Purchase Agreement — {args.street}, {args.city}",
    )

    print("Creating draft envelope...")
    create_resp = envelopes_api.create_envelope(ACCOUNT_ID, envelope_definition=draft_def)
    envelope_id = create_resp.envelope_id
    print(f"  Draft envelope_id: {envelope_id}")

    # Step 2: Discover the envelope's document_id for PA TEMPLATE.pdf, then look up tab_ids
    # for our prefill tab overrides (matching by tab_label).
    print("Fetching envelope documents and prefill tabs...")
    envelope_docs = envelopes_api.list_documents(ACCOUNT_ID, envelope_id)
    pa_doc_id = None
    for doc in (envelope_docs.envelope_documents or []):
        doc_name = (getattr(doc, "name", "") or "").lower()
        if "pa template" in doc_name:
            pa_doc_id = doc.document_id
            break
    if not pa_doc_id:
        # Fall back to first non-summary document
        for doc in (envelope_docs.envelope_documents or []):
            if (getattr(doc, "type", "") or "") != "summary":
                pa_doc_id = doc.document_id
                break
    if not pa_doc_id:
        sys.exit("ERROR: could not find PA TEMPLATE document in envelope")
    print(f"  PA document_id in envelope: {pa_doc_id}")

    current_tabs = envelopes_api.get_document_tabs(ACCOUNT_ID, pa_doc_id, envelope_id)
    current_prefill = getattr(current_tabs, "prefill_tabs", None)
    current_prefill_text = (getattr(current_prefill, "text_tabs", None) or []) if current_prefill else []
    label_to_tab_id = {t.tab_label: t.tab_id for t in current_prefill_text}
    print(f"  Found {len(label_to_tab_id)} prefill text tabs in envelope")

    # Step 3: Build update payload using envelope tab_ids matched by tab_label.
    updates = []
    skipped = []
    for ovr in text_tab_overrides:
        tab_id = label_to_tab_id.get(ovr.tab_label)
        if not tab_id:
            skipped.append(ovr.tab_label)
            continue
        updates.append(Text(tab_id=tab_id, tab_label=ovr.tab_label, value=ovr.value))
    if skipped:
        print(f"  WARNING: {len(skipped)} tab_labels not found in envelope (will be blank)")

    update_tabs = Tabs(prefill_tabs=PrefillTabs(text_tabs=updates))
    print(f"Updating {len(updates)} prefill tab values...")
    envelopes_api.update_document_tabs(ACCOUNT_ID, pa_doc_id, envelope_id, tabs=update_tabs)
    print("  Tabs updated.")

    # Step 4: Send the envelope (change status from "created" to "sent").
    print("Sending envelope...")
    envelopes_api.update(ACCOUNT_ID, envelope_id, envelope=Envelope(status="sent"))

    view_url = f"https://app.docusign.com/envelope/{envelope_id}"
    print("\nEnvelope sent.")
    print(f"  Envelope ID: {envelope_id}")
    print(f"  View:        {view_url}")
    return {"envelope_id": envelope_id, "view_url": view_url, "skipped_tab_labels": skipped}


def main() -> None:
    args = parse_args()
    api_client = authenticate()

    if args.inspect_template:
        inspect_template(api_client)
    else:
        generate_envelope(api_client, args)


if __name__ == "__main__":
    main()
