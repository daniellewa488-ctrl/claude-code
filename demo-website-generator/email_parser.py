import re
import json
import time
from dataclasses import dataclass
import anthropic
import config

MODEL = "claude-haiku-4-5-20251001"


@dataclass
class JobData:
    company_name: str = ""
    slug: str = ""
    industry: str = ""
    website_url: str = ""
    logo_url: str = ""
    logo_facelift: bool = False
    generate_logo: bool = False   # True when they want an AI logo created from scratch
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


def _parse_with_claude(body: str) -> dict:
    system_prompt = (
        "You are a smart assistant for a German web design agency. "
        "Your job is to read incoming emails and extract business information so we can build a demo website. "
        "Emails can be formal or informal, in German or English, complete or very brief. "
        "Always extract what you can and INFER the rest intelligently from context. "
        "Return ONLY a valid JSON object — no explanation, no markdown fences."
    )
    user_prompt = f"""Read this email carefully and extract business info for building a demo website.
The email may be missing many fields — that is fine. Infer what you can from context.

FIELD RULES:
- company_name: The business name. Infer from context, email signature, descriptions, or the sender address. If truly unknown, use "Unbekanntes Unternehmen".
- industry: Business type/sector. ALWAYS fill this — infer from company name, services, descriptions, or any context clue. Never leave empty.
- website_url: Set ONLY if a full http/https URL is clearly given. Otherwise empty string.
- logo_url: Set ONLY if a direct image URL (jpg/png/svg/gif) is explicitly given. Otherwise empty string.
- logo_facelift: true ONLY if they explicitly ask for a redesign of their EXISTING logo.
- generate_logo: true if they mention needing a new logo created/designed (and have no logo URL). false if logo_url is set, they say no logo, or there is no mention of logo at all.
- region: City or region. Infer from context or email address domain if possible. Empty string only if truly no indication.
- services: What they offer. Infer from industry if not mentioned. Never leave empty — always provide something relevant.
- target_audience: Their customers. Infer from industry if not mentioned.
- style: Design mood/colors/feeling. Infer from industry if not stated (e.g. bakery → warm, cosy, amber; law firm → serious, navy; garden → natural, green).

EMAIL:
{body}

Return ONLY this JSON object:
{{
  "company_name": "...",
  "industry": "...",
  "website_url": "...",
  "logo_url": "...",
  "logo_facelift": false,
  "generate_logo": false,
  "region": "...",
  "services": "...",
  "target_audience": "...",
  "style": "..."
}}"""

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    for attempt in range(5):
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=1200,
                temperature=0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = msg.content[0].text.strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
            return json.loads(raw)
        except anthropic.RateLimitError:
            wait = 10 * (attempt + 1)
            print(f"[email_parser] Rate limit, waiting {wait}s...")
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            if e.status_code in (529, 503):
                wait = 10 * (attempt + 1)
                print(f"[email_parser] Overloaded, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
        except json.JSONDecodeError as e:
            print(f"[email_parser] JSON parse error (attempt {attempt+1}): {e}")
            if attempt == 4:
                raise

    raise Exception("Claude API failed after 5 retries")


def parse(email_data: dict) -> JobData:
    body = email_data.get("body", "")
    raw_sender = email_data.get("sender", "")

    print("[email_parser] Using Claude to parse email fields...")
    extracted = _parse_with_claude(body)

    company = extracted.get("company_name", "").strip()
    industry = extracted.get("industry", "").strip()
    website = extracted.get("website_url", "").strip()
    logo_url = extracted.get("logo_url", "").strip()
    logo_facelift = bool(extracted.get("logo_facelift", False))
    generate_logo = bool(extracted.get("generate_logo", False))
    region = extracted.get("region", "").strip()
    services = extracted.get("services", "").strip()
    target = extracted.get("target_audience", "").strip()
    style = extracted.get("style", "").strip()

    if not website.startswith("http"):
        website = ""
    if not logo_url.startswith("http"):
        logo_url = ""
    if logo_url:
        generate_logo = False

    slug = _slugify(company) if company else f"anfrage-{int(time.time())}"

    print(
        f"[email_parser] Extracted: company='{company}', industry='{industry}', "
        f"website='{website}', logo_url={bool(logo_url)}, "
        f"generate_logo={generate_logo}, facelift={logo_facelift}"
    )

    return JobData(
        company_name=company,
        slug=slug,
        industry=industry,
        website_url=website,
        logo_url=logo_url,
        logo_facelift=logo_facelift,
        generate_logo=generate_logo,
        region=region,
        services=services,
        target_audience=target,
        style=style,
        sender_email=_extract_sender_address(raw_sender),
    )
