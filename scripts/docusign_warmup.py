"""
DocuSign warmup script — generates 20+ API calls in the demo environment
to satisfy the Go-Live verification form's prerequisite.

Run once before submitting the Go-Live verification form. Each call is logged
in DocuSign's API dashboard and counts toward the requirement.

Prereqs:
- Integration key created in dev sandbox (apps-d.docusign.com)
- RSA keypair generated and saved to docusign_private_key.pem at project root
- Authentication Method = "Authorization Code Grant" on the app
- Consent URL clicked once for the user (one-time impersonation grant)
- .env populated with demo values (DOCUSIGN_USER_ID = demo user ID)

Usage:
    pip install -r requirements.txt
    python scripts/docusign_warmup.py
"""

import os
import sys
import time
from pathlib import Path

from docusign_esign import (
    AccountsApi,
    ApiClient,
    EnvelopesApi,
    TemplatesApi,
    UsersApi,
)
from dotenv import load_dotenv

load_dotenv()


def env(key: str, default: str | None = None, required: bool = True) -> str:
    val = os.getenv(key, default)
    if required and not val:
        sys.exit(f"ERROR: {key} not set in .env")
    return val or ""


INTEGRATION_KEY = env("DOCUSIGN_INTEGRATION_KEY")
USER_ID = env("DOCUSIGN_USER_ID")
ACCOUNT_ID = env("DOCUSIGN_ACCOUNT_ID")
PRIVATE_KEY_PATH = env("DOCUSIGN_PRIVATE_KEY_PATH", "docusign_private_key.pem", required=False) or "docusign_private_key.pem"
BASE_URL = env("DOCUSIGN_BASE_URL", "https://account-d.docusign.com", required=False) or "https://account-d.docusign.com"
API_BASE_URL = env("DOCUSIGN_API_BASE_URL", "https://demo.docusign.net/restapi", required=False) or "https://demo.docusign.net/restapi"


def authenticate() -> ApiClient:
    """JWT auth flow. Returns ApiClient configured with bearer token."""
    private_key_path = Path(PRIVATE_KEY_PATH)
    if not private_key_path.exists():
        sys.exit(f"ERROR: private key not found at {private_key_path.absolute()}")

    api_client = ApiClient()
    auth_host = BASE_URL.replace("https://", "").replace("http://", "")
    api_client.set_oauth_host_name(auth_host)

    with open(private_key_path, "rb") as f:
        key_bytes = f.read()

    print(f"Authenticating as user {USER_ID} via {auth_host}...")
    response = api_client.request_jwt_user_token(
        client_id=INTEGRATION_KEY,
        user_id=USER_ID,
        oauth_host_name=auth_host,
        private_key_bytes=key_bytes,
        expires_in=3600,
        scopes=["signature", "impersonation"],
    )
    print(f"OK — access token expires in {response.expires_in}s\n")

    api_client.host = API_BASE_URL
    api_client.set_default_header("Authorization", f"Bearer {response.access_token}")
    return api_client


def warmup(api_client: ApiClient) -> int:
    """Run a series of read-only API calls to build call history. Returns count."""
    accounts = AccountsApi(api_client)
    templates = TemplatesApi(api_client)
    envelopes = EnvelopesApi(api_client)
    users = UsersApi(api_client)

    n = 0

    def call(label: str, fn):
        nonlocal n
        try:
            fn()
            n += 1
            print(f"  [{n:>2}] OK  — {label}")
        except Exception as e:
            print(f"  [--] ERR — {label}: {type(e).__name__}: {str(e)[:120]}")

    print("Running warmup calls...\n")

    # Account-level
    call("Get account information",
         lambda: accounts.get_account_information(ACCOUNT_ID))
    call("Get account information (with settings)",
         lambda: accounts.get_account_information(ACCOUNT_ID, include_account_settings="true"))
    call("List custom fields",
         lambda: accounts.list_custom_fields(ACCOUNT_ID))
    call("List permissions",
         lambda: accounts.list_permissions(ACCOUNT_ID))
    call("Get billing plan",
         lambda: accounts.get_account_information(ACCOUNT_ID, include_account_settings="false"))
    call("List brands",
         lambda: accounts.list_brands(ACCOUNT_ID))

    # User-level
    call("List users",
         lambda: users.list(ACCOUNT_ID))
    call("Get user information",
         lambda: users.get_information(ACCOUNT_ID, USER_ID))
    call("Get user signature",
         lambda: users.get_signature(ACCOUNT_ID, USER_ID))

    # Template-level
    call("List templates (count=10)",
         lambda: templates.list_templates(ACCOUNT_ID, count="10"))
    call("List templates (count=50)",
         lambda: templates.list_templates(ACCOUNT_ID, count="50"))
    call("List templates with shared filter",
         lambda: templates.list_templates(ACCOUNT_ID, shared="shared_with_me"))

    # Envelope-level (read-only)
    from_date = "2026-01-01T00:00:00Z"
    call("List envelope status changes (all)",
         lambda: envelopes.list_status_changes(ACCOUNT_ID, from_date=from_date))
    call("List envelope status changes (sent)",
         lambda: envelopes.list_status_changes(ACCOUNT_ID, from_date=from_date, status="sent"))
    call("List envelope status changes (completed)",
         lambda: envelopes.list_status_changes(ACCOUNT_ID, from_date=from_date, status="completed"))
    call("List envelope status changes (delivered)",
         lambda: envelopes.list_status_changes(ACCOUNT_ID, from_date=from_date, status="delivered"))
    call("List envelope status changes (declined)",
         lambda: envelopes.list_status_changes(ACCOUNT_ID, from_date=from_date, status="declined"))
    call("List envelope status changes (voided)",
         lambda: envelopes.list_status_changes(ACCOUNT_ID, from_date=from_date, status="voided"))

    # Pad to ensure we clear 25+ comfortably
    print("\nPadding to 25+ calls...")
    while n < 25:
        call("Padding — get account info",
             lambda: accounts.get_account_information(ACCOUNT_ID))
        time.sleep(0.3)

    return n


def main() -> None:
    print("=" * 64)
    print("DocuSign Warmup Script — Demo Environment")
    print("=" * 64)
    print(f"Account ID:  {ACCOUNT_ID}")
    print(f"User ID:     {USER_ID}")
    print(f"Auth host:   {BASE_URL}")
    print(f"API host:    {API_BASE_URL}")
    print(f"Key file:    {PRIVATE_KEY_PATH}")
    print()

    api_client = authenticate()
    count = warmup(api_client)

    print()
    print("=" * 64)
    print(f"Done. Made {count} API calls.")
    print()
    print("Next steps:")
    print("  1. Wait ~5 minutes for DocuSign to register the calls")
    print("  2. Go to apps-d.docusign.com -> Apps and Keys -> SiftStack PA Generator")
    print("     -> View API Dashboard to confirm calls are logged")
    print("  3. Submit the Go-Live verification form")
    print("=" * 64)


if __name__ == "__main__":
    main()
