"""One-time OneDrive OAuth helper — device code flow, captures refresh token.

Run this ONCE on your local machine after registering the Azure AD app.
Prints a user code to enter at microsoft.com/devicelogin, polls Microsoft
for consent, then prints the refresh token to add to Actor input.

Why device code flow: no redirect URI, no client secret, no local HTTP
server. Works from any machine even headless. The trade-off is that YOU
(the account owner) have to authenticate interactively once. After that
the refresh token works indefinitely as long as it's used within the
inactivity window (90 days for work/school accounts, 24 months for
personal).

Usage:
    python scripts/onedrive_auth.py <CLIENT_ID>

After it succeeds, add to your Actor input (input.cloud.json) AND .env:
    MS_GRAPH_CLIENT_ID=<the same client id>
    MS_GRAPH_REFRESH_TOKEN=<the long opaque token printed below>
"""
from __future__ import annotations

import sys
import time

import httpx

DEVICE_CODE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
SCOPES = "Files.ReadWrite.All offline_access User.Read"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip())
        print("\nError: missing CLIENT_ID argument", file=sys.stderr)
        return 2

    client_id = sys.argv[1].strip()
    if not client_id:
        print("Error: empty CLIENT_ID", file=sys.stderr)
        return 2

    with httpx.Client(timeout=30.0) as client:
        # Step 1: ask Microsoft for a device code
        r = client.post(
            DEVICE_CODE_URL,
            data={"client_id": client_id, "scope": SCOPES},
        )
        if r.status_code != 200:
            print(f"devicecode request failed: HTTP {r.status_code}\n{r.text}",
                  file=sys.stderr)
            return 1
        body = r.json()
        device_code = body["device_code"]
        user_code = body["user_code"]
        verification_uri = body["verification_uri"]
        interval = int(body.get("interval", 5))

        print()
        print("=" * 70)
        print(f"  Open this URL in a browser:  {verification_uri}")
        print(f"  Enter this code:             {user_code}")
        print("=" * 70)
        print()
        print("Waiting for you to sign in...  (poll interval: %ss)" % interval)

        # Step 2: poll token endpoint until user completes auth
        deadline = time.time() + int(body.get("expires_in", 900))
        while time.time() < deadline:
            time.sleep(interval)
            t = client.post(
                TOKEN_URL,
                data={
                    "client_id": client_id,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                },
            )
            if t.status_code == 200:
                break
            err = t.json().get("error", "")
            if err == "authorization_pending":
                continue
            if err == "slow_down":
                interval += 5
                continue
            print(f"auth failed: {err}: {t.json().get('error_description','')}",
                  file=sys.stderr)
            return 1
        else:
            print("timed out waiting for device code entry", file=sys.stderr)
            return 1

        # Step 3: extract refresh token
        tok = t.json()
        refresh_token = tok.get("refresh_token")
        if not refresh_token:
            print("Microsoft returned no refresh_token. Missing "
                  "'offline_access' scope on the app registration?",
                  file=sys.stderr)
            return 1

        print()
        print("Signed in as:", tok.get("id_token") and "(see id_token)" or "?")
        print()
        print("=" * 70)
        print("  SUCCESS — copy these two values into Apify Actor input and .env:")
        print("=" * 70)
        print()
        print(f"MS_GRAPH_CLIENT_ID={client_id}")
        print(f"MS_GRAPH_REFRESH_TOKEN={refresh_token}")
        print()
        print("(Access token expires in %ss; refresh token is long-lived.)"
              % tok.get("expires_in", "?"))
        return 0


if __name__ == "__main__":
    sys.exit(main())
