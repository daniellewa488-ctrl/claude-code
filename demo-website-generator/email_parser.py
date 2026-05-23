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

    # Support both old format (Unternehmensname) and new format (Firmenname)
    company = _extract(body, "Firmenname", "Unternehmensname", "Firma", "Company")
    industry = _extract(body, "Branche", "Industrie", "Industry")

    # Support both: "Aktuelle Domain: url" and "Website: url"
    website = _extract(body, "Aktuelle Domain", "Domain", "Website", "Webseite", "URL")

    # Support "Website vorhanden: Nein" to explicitly disable crawling
    website_vorhanden = _extract(body, "Website vorhanden")
    if website_vorhanden.lower() in ("nein", "no", "false", "0"):
        website = ""

    # Normalize website: treat "keine", "nein", "-", empty as no URL
    if website.lower() in ("keine", "nein", "-", "n/a", ""):
        website = ""

    # Logo: support direct URL or "Logo vorhanden: Ja/Nein"
    logo = _extract(body, "Logo URL", "Logo-URL", "Logo")
    logo_vorhanden = _extract(body, "Logo vorhanden")
    # Only use logo as URL if it actually starts with http
    logo_url = logo if logo.startswith("http") else ""

    # Facelift: support "Logo-Facelift gewünscht" and "Logo-Facelift"
    facelift_raw = _extract(body, "Logo-Facelift gewünscht", "Logo-Facelift", "LogoFacelift", "Facelift")
    facelift = facelift_raw.lower() in ("ja", "yes", "true", "1")

    # Optional detail fields — left empty if not provided, Groq will infer from crawled site
    region = _extract(body, "Region", "Standort", "Ort", "Stadt")
    services = _extract(body, "Leistungen", "Services", "Angebote")
    target = _extract(body, "Zielgruppe", "Zielkunden", "Target")
    style = _extract(body, "Stil", "Style", "Design", "Wunschdesign")

    slug = _slugify(company) if company else "demo"

    data = JobData(
        company_name=company,
        slug=slug,
        industry=industry,
        website_url=website,
        logo_url=logo_url,
        logo_facelift=facelift,
        region=region,
        services=services,
        target_audience=target,
        style=style,
        sender_email=_extract_sender_address(raw_sender),
    )
    return data
