import re
import json
import requests
from dataclasses import dataclass

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"


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


def _extract_sender_address(raw_from: str) -> str:
    m = re.search(r"<([^>]+)>", raw_from)
    if m:
        return m.group(1).strip()
    return raw_from.strip()


def _parse_with_groq(body: str, api_key: str) -> dict:
    system_prompt = (
        "You are a data extraction assistant. Extract information from the email body and return ONLY a valid JSON object. "
        "No explanation, no markdown, just the raw JSON."
    )
    user_prompt = f"""Extract the following fields from this email body. Return a JSON object with exactly these keys:
- company_name: the business/company name (string)
- industry: the business industry or type (string)
- website_url: the website URL if mentioned, empty string if not (string, must start with http if present)
- logo_url: a direct URL to a logo image if mentioned, empty string if not available (string)
- logo_facelift: whether a logo redesign/facelift is requested (boolean true/false)
- region: city, region or location of the business (string, empty if not mentioned)
- services: list of services or offerings as a comma-separated string (string, empty if not mentioned)
- target_audience: who their customers are (string, empty if not mentioned)
- style: design style preferences like colors, mood, aesthetic (string, empty if not mentioned)

Email body:
{body}

Return ONLY the JSON object, nothing else."""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 1000,
        "temperature": 0,
    }

    for attempt in range(5):
        resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=60)
        if resp.status_code == 429:
            import time
            wait = 10 * (attempt + 1)
            print(f"[email_parser] Groq rate limit, waiting {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown fences if present
        content = re.sub(r"^```[a-z]*\n?", "", content)
        content = re.sub(r"\n?```$", "", content).strip()
        return json.loads(content)

    raise Exception("Groq API failed after 5 retries")


def parse(email_data: dict) -> JobData:
    import config
    body = email_data.get("body", "")
    raw_sender = email_data.get("sender", "")

    print("[email_parser] Using Groq to parse email fields...")
    extracted = _parse_with_groq(body, config.GROQ_API_KEY)

    company = extracted.get("company_name", "").strip()
    industry = extracted.get("industry", "").strip()
    website = extracted.get("website_url", "").strip()
    logo_url = extracted.get("logo_url", "").strip()
    logo_facelift = bool(extracted.get("logo_facelift", False))
    region = extracted.get("region", "").strip()
    services = extracted.get("services", "").strip()
    target = extracted.get("target_audience", "").strip()
    style = extracted.get("style", "").strip()

    # Validate website URL
    if not website.startswith("http"):
        website = ""

    # Validate logo URL
    if not logo_url.startswith("http"):
        logo_url = ""

    slug = _slugify(company) if company else "demo"

    print(f"[email_parser] Extracted: company='{company}', industry='{industry}', website='{website}', facelift={logo_facelift}")

    return JobData(
        company_name=company,
        slug=slug,
        industry=industry,
        website_url=website,
        logo_url=logo_url,
        logo_facelift=logo_facelift,
        region=region,
        services=services,
        target_audience=target,
        style=style,
        sender_email=_extract_sender_address(raw_sender),
    )
