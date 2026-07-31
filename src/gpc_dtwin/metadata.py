"""Application identity and attribution metadata."""

from __future__ import annotations

APP_NAME = "GPC-DTwin"
APP_EDITION = "Materials Analytics"
APP_DESCRIPTION = (
    "A desktop platform for structured geopolymer-concrete analytics, "
    "uncertainty-aware modelling, optimization, active learning, and reproducibility."
)
ORGANIZATION_NAME = "Dr. Suman Jana"
SETTINGS_APPLICATION = "GPC-DTwin"
COPYRIGHT_YEAR = 2026
COPYRIGHT_HOLDER = "Dr. Suman Jana"
COPYRIGHT_TEXT = f"Copyright © {COPYRIGHT_YEAR} {COPYRIGHT_HOLDER}. All rights reserved."
ORCID_ID = "0000-0002-9850-2169"
ORCID_URL = f"https://orcid.org/{ORCID_ID}"


def attribution_html() -> str:
    """Return a reusable rich-text attribution block."""
    return (
        f"<b>{APP_NAME}</b><br>"
        f"{COPYRIGHT_TEXT}<br>"
        f'ORCID: <a href="{ORCID_URL}">{ORCID_ID}</a>'
    )
