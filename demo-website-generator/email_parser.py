import re
from dataclasses import dataclass, field


@dataclass
class JobData:
    company_name: str = ""
    slug: str = ""
    industry: str = ""
    website_url: str = ""
    logo_url: str = ""
    logo_facelift: bool = False
    region: str = ""
    services: str = ""
    target_audience: str = ""
    style: str = ""
    sender_email: str = ""


def _slugify(text: str) -> str:
    text = text.lower()
    replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "à": "a", "á": "a",
                    "â": "a", "è": "e", "é": "e", "ê": "e", "ì": "i", "í": "i",
                    "î": "i", "ò": "o", "ó": "o", "ô": "o", "ù": "u", "ú": "u", "û": "u"}
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text


def _extract(body: str, *keys: str) -> str:
    """Try each key variant (case-insensitive) and return the first match."""
    for key in keys:
        pattern = rf"(?im)^{re.escape(key)}\s*:\s*(.+)$"
        m = re.search(pattern, body)
        if m:
            return m.group(1).strip()
    return ""


def _extract_sender_address(raw_from: str) -> str:
    m = re.search(r"<([^>]+)>", raw_from)
    if m:
        return m.group(1).strip()
    return raw_from.strip()


def parse(email_data: dict) -> JobData:
    body = email_data.get("body", "")
    raw_sender = email_data.get("sender", "")

    company = _extract(body, "Unternehmensname", "Firma", "Company")
    industry = _extract(body, "Branche", "Industrie", "Industry")
    website = _extract(body, "Website", "Webseite", "URL")
    logo = _extract(body, "Logo")
    facelift_raw = _extract(body, "Logo-Facelift", "LogoFacelift", "Facelift")
    region = _extract(body, "Region", "Standort", "Ort")
    services = _extract(body, "Leistungen", "Services", "Angebote")
    target = _extract(body, "Zielgruppe", "Zielkunden", "Target")
    style = _extract(body, "Stil", "Style", "Design")

    # Normalize website: treat "keine", "nein", "-", empty as no URL
    if website.lower() in ("keine", "nein", "-", "n/a", ""):
        website = ""

    facelift = facelift_raw.lower() in ("ja", "yes", "true", "1")

    slug = _slugify(company) if company else "demo"

    data = JobData(
        company_name=company,
        slug=slug,
        industry=industry,
        website_url=website,
        logo_url=logo if logo.startswith("http") else "",
        logo_facelift=facelift,
        region=region,
        services=services,
        target_audience=target,
        style=style,
        sender_email=_extract_sender_address(raw_sender),
    )
    return data
