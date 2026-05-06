"""
Web form for generating DocuSign Purchase Agreements.

Run locally:
    pip install -r requirements.txt
    streamlit run streamlit_pa_app.py

Deploy to Streamlit Cloud:
    1. Push this repo to GitHub
    2. Go to share.streamlit.io -> New app -> point at streamlit_pa_app.py
    3. Add Secrets in the Streamlit Cloud dashboard:
        DOCUSIGN_INTEGRATION_KEY = "..."
        DOCUSIGN_USER_ID = "..."
        DOCUSIGN_ACCOUNT_ID = "..."
        DOCUSIGN_PA_TEMPLATE_ID = "..."
        DOCUSIGN_BASE_URL = "https://account.docusign.com"
        DOCUSIGN_API_BASE_URL = "https://na4.docusign.net/restapi"
        ALWORTH_BUYER_NAME = "Sean Jones"
        ALWORTH_BUYER_EMAIL = "sean@alworthhomes.com"
        ALWORTH_ACQ_NAME = "Zane Stacy"
        ALWORTH_ACQ_EMAIL = "zane@alworthhomes.com"
        ALWORTH_DEFAULT_TITLE_CO = "Ticor Title"
        DOCUSIGN_PRIVATE_KEY_PEM = '''-----BEGIN RSA PRIVATE KEY-----
        ...full PEM content...
        -----END RSA PRIVATE KEY-----'''
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from argparse import Namespace
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

# --- Bridge Streamlit secrets to env vars BEFORE importing generate_pa ---
try:
    for k, v in dict(st.secrets).items():
        os.environ.setdefault(k, str(v))
except Exception:
    pass  # No secrets configured (local dev — .env will be loaded by generate_pa.py)

# Materialize the private key from secrets to a temp file (DocuSign SDK reads from a file path)
if "DOCUSIGN_PRIVATE_KEY_PEM" in os.environ and "DOCUSIGN_PRIVATE_KEY_PATH" not in os.environ:
    pem_path = Path(tempfile.gettempdir()) / "docusign_private_key.pem"
    pem_path.write_text(os.environ["DOCUSIGN_PRIVATE_KEY_PEM"])
    os.environ["DOCUSIGN_PRIVATE_KEY_PATH"] = str(pem_path)

# Add scripts/ to path and import the generator
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from generate_pa import authenticate, generate_envelope  # noqa: E402

# --- Page config ---
st.set_page_config(page_title="Generate PA — Alworth Homes", page_icon="📄", layout="centered")
st.title("📄 Generate Purchase Agreement")
st.caption("Alworth Homes — DocuSign envelope generator")


# --- Password gate ---
def _check_password() -> bool:
    """Gate the app behind APP_PASSWORD (set via Streamlit Cloud secrets or .env).
    If APP_PASSWORD is unset, no gate is enforced (local dev convenience).
    """
    expected = os.environ.get("APP_PASSWORD", "")
    if not expected:
        return True  # No password configured — open access (local dev)

    if st.session_state.get("authenticated"):
        return True

    with st.form("login_form", clear_on_submit=False):
        st.markdown("### 🔒 Login required")
        pw = st.text_input("Password", type="password")
        login_submit = st.form_submit_button("Log in", type="primary")
    if login_submit:
        if pw == expected:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("❌ Incorrect password")
    return False


if not _check_password():
    st.stop()


# --- Form ---
with st.form("pa_form", clear_on_submit=False):
    st.subheader("Property")
    col1, col2 = st.columns([3, 2])
    with col1:
        street = st.text_input("Street Address *", placeholder="51 Kuder Ave")
        city = st.text_input("City *", placeholder="Akron")
    with col2:
        state = st.text_input("State *", value="OH", max_chars=2, help="2-letter state abbreviation").upper()
        zip_code = st.text_input("ZIP *", placeholder="44303", max_chars=5)
    county = st.text_input("County", placeholder="Summit")
    legal_description = st.text_area(
        "Legal Description / Parcel ID *",
        placeholder="STARK MARSHALL LOTS 9 M 50FT E OF S 50FT...",
        height=80,
    )

    st.subheader("Seller")
    col1, col2 = st.columns(2)
    with col1:
        seller_name = st.text_input("Seller Name *", placeholder="John Doe")
    with col2:
        seller_email = st.text_input("Seller Email *", placeholder="john@example.com")

    st.markdown("**Seller mailing address** — leave blank to copy from property address above.")
    seller_mailing_street = st.text_input("Seller Mailing Street", placeholder="(blank = use property street)")
    col1, col2, col3 = st.columns([3, 1, 2])
    with col1:
        seller_mailing_city = st.text_input("Seller Mailing City", placeholder="(blank = use property city)")
    with col2:
        seller_mailing_state = st.text_input("State", max_chars=2, placeholder="OH")
    with col3:
        seller_mailing_zip = st.text_input("ZIP", placeholder="(blank = property)")

    st.subheader("Deal Terms")
    col1, col2 = st.columns(2)
    with col1:
        price = st.number_input("Purchase Price ($) *", min_value=1, value=50000, step=1000, format="%d")
        emd = st.number_input("EMD ($)", min_value=0, value=100, step=50, format="%d",
                               help="We open escrow as low as possible — $50-$100 typical. Default $100.")
        title_company = st.text_input(
            "Title Company",
            value=os.environ.get("ALWORTH_DEFAULT_TITLE_CO", ""),
        )
    with col2:
        close_date_input = st.date_input("Closing Date", value=date.today() + timedelta(days=30))
        inspection_days = st.number_input(
            "Inspection Days",
            min_value=1, max_value=60, value=21,
            help="Days from today until inspection deadline. Rule of thumb: ~70% of days-to-close (e.g., 21 for a 30-day close).",
        )
        acceptance_days = st.number_input(
            "Seller Acceptance (days)",
            min_value=1, max_value=14, value=1,
            help="How long seller has to accept. Default 1 = 24 hours. Envelope auto-expires after this window.",
        )

    additional_terms = st.text_area("Additional Terms (Section 19, optional)", height=80,
                                     help="Extra contingencies beyond the printed 'Contingent Clear title and Investor approval'")

    with st.expander("Addenda & Advisories (Section 18, optional)"):
        st.caption("Names of additional documents attached to the agreement. Leave blank if none.")
        col1, col2 = st.columns(2)
        with col1:
            addenda_1 = st.text_input("Addenda 1", placeholder="e.g., Lead-Based Paint Disclosure")
            advisory_1 = st.text_input("Advisory 1", placeholder="e.g., Mold Advisory")
            advisory_3 = st.text_input("Advisory 3")
        with col2:
            addenda_2 = st.text_input("Addenda 2")
            advisory_2 = st.text_input("Advisory 2")
            advisory_4 = st.text_input("Advisory 4")

    submit = st.form_submit_button("Send Envelope", type="primary", use_container_width=True)

# --- Submit handler ---
if submit:
    missing = []
    for value, label in [
        (street, "Street Address"),
        (city, "City"),
        (zip_code, "ZIP"),
        (legal_description, "Legal Description"),
        (seller_name, "Seller Name"),
        (seller_email, "Seller Email"),
    ]:
        if not value or not str(value).strip():
            missing.append(label)
    if missing:
        st.error(f"Missing required fields: {', '.join(missing)}")
        st.stop()

    args = Namespace(
        inspect_template=False,
        dryrun=False,
        # Property
        street=street.strip(),
        city=city.strip(),
        state=state,
        zip_code=zip_code.strip(),
        county=(county.strip() or None) if county else None,
        legal_description=legal_description.strip() or None,
        # Seller
        seller_name=seller_name.strip(),
        seller_email=seller_email.strip(),
        seller_tax_id=None,
        seller_mailing_street=seller_mailing_street,
        seller_mailing_city=seller_mailing_city,
        seller_mailing_state=seller_mailing_state,
        seller_mailing_zip=seller_mailing_zip,
        # Deal
        price=int(price),
        emd=int(emd),
        close_date=close_date_input.isoformat(),
        inspection_days=int(inspection_days),
        acceptance_days=int(acceptance_days),
        title_company=(title_company.strip() or None) if title_company else None,
        additional_terms=additional_terms.strip() or None,
        # Section 18 — Addenda & Advisories
        addenda_1=addenda_1.strip() or None,
        addenda_2=addenda_2.strip() or None,
        advisory_1=advisory_1.strip() or None,
        advisory_2=advisory_2.strip() or None,
        advisory_3=advisory_3.strip() or None,
        advisory_4=advisory_4.strip() or None,
    )

    with st.spinner("Authenticating + creating envelope..."):
        try:
            api_client = authenticate()
            result = generate_envelope(api_client, args)
        except Exception as e:
            st.error(f"Failed to send envelope: {type(e).__name__}: {e}")
            with st.expander("Full error details"):
                st.code(traceback.format_exc(), language="text")
            st.stop()

    if result and result.get("envelope_id"):
        st.success("Envelope sent! 🎉")
        st.markdown(f"**Envelope ID:** `{result['envelope_id']}`")
        st.markdown(f"**Tracking URL:** [{result['view_url']}]({result['view_url']})")
        if result.get("skipped_tab_labels"):
            st.warning(
                f"{len(result['skipped_tab_labels'])} tab labels not found in the envelope (left blank). "
                "If a field looks empty, run `--inspect-template` to refresh the cache."
            )
        st.markdown(
            "**What happens next:**\n"
            "1. Sean (Buyer) gets the first signing email at `sean@alworthhomes.com`\n"
            "2. After he signs, Zane (Acquisitions) gets it at `zane@alworthhomes.com` — "
            "tap the single Initial during the seller phone call to release\n"
            "3. Then the seller signs at the email above\n"
            "4. Executed PDF arrives in everyone's inbox when complete"
        )
    else:
        st.warning("Envelope flow returned no result — check logs.")
