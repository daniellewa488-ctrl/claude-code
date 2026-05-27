import re
import time
import requests
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DemoBot/1.0; +https://hannahs-webdesign.de)"}
TIMEOUT = 12

# Page paths we want to crawl first — most likely to have useful content
PRIORITY_KEYWORDS = [
    "ueber-uns", "uber-uns", "about", "about-us", "ueber", "wir",
    "leistungen", "services", "dienstleistungen", "angebote", "produkte",
    "kontakt", "contact", "impressum",
    "team", "profil", "unternehmen",
]


@dataclass
class CrawledData:
    found: bool = False
    full_text: str = ""       # Combined structured text from all pages (fed to Claude)
    contact_phone: str = ""   # Extracted phone number
    contact_email: str = ""   # Extracted email
    contact_address: str = "" # Extracted street address
    logo_url: str = ""        # Absolute URL of the logo image


def _is_priority(url: str) -> bool:
    path = urlparse(url).path.lower().replace("-", "").replace("_", "")
    return any(kw.replace("-", "") in path for kw in PRIORITY_KEYWORDS)


def _internal_links(soup: BeautifulSoup, base_url: str, max_links: int = 8) -> list:
    domain = urlparse(base_url).netloc
    seen = set()
    priority = []
    others = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc != domain:
            continue
        if re.search(r"\.(jpg|jpeg|png|gif|svg|pdf|zip|css|js|ico|woff|xml)$", parsed.path, re.I):
            continue
        # Strip query string / fragment for dedup
        clean = parsed.scheme + "://" + parsed.netloc + parsed.path.rstrip("/")
        if clean in seen or clean == base_url.rstrip("/"):
            continue
        seen.add(clean)
        (priority if _is_priority(full) else others).append(full)

    return (priority + others)[:max_links]


def _clean_text(soup: BeautifulSoup, max_chars: int = 3500) -> str:
    """Extract structured readable text from a page."""
    for tag in soup(["script", "style", "noscript", "svg", "head",
                     "button", "form", "input", "select", "textarea",
                     "nav", "header", "footer", "aside"]):
        tag.decompose()

    lines = []
    for el in soup.find_all(["h1", "h2", "h3", "p", "li", "address", "span", "div"]):
        # Skip tiny snippets and deeply nested containers
        if el.find(["h1", "h2", "h3", "p"]):
            continue
        text = el.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        if len(text) < 25:
            continue
        if el.name == "h1":
            lines.append(f"\n## {text}")
        elif el.name in ("h2", "h3"):
            lines.append(f"\n# {text}")
        elif el.name == "li":
            lines.append(f"• {text}")
        else:
            lines.append(text)

    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result[:max_chars]


def _find_logo(soup: BeautifulSoup, base_url: str) -> str:
    """Look for a logo image using progressively wider patterns."""
    domain = urlparse(base_url).netloc

    # 1. Any <img> whose src / alt / class / id contains "logo"
    for img in soup.find_all("img"):
        src = img.get("src", "").strip()
        if not src or src.startswith("data:"):
            continue
        haystack = " ".join([
            src.lower(),
            img.get("alt", "").lower(),
            " ".join(img.get("class", [])).lower(),
            img.get("id", "").lower(),
        ])
        if "logo" in haystack:
            return urljoin(base_url, src)

    # 2. <img> inside a container whose class or id contains "logo"
    for container in soup.find_all(class_=re.compile(r"logo", re.I)):
        img = container.find("img")
        if img and img.get("src") and not img["src"].startswith("data:"):
            return urljoin(base_url, img["src"].strip())
    for container in soup.find_all(id=re.compile(r"logo", re.I)):
        img = container.find("img")
        if img and img.get("src") and not img["src"].startswith("data:"):
            return urljoin(base_url, img["src"].strip())

    # 3. First <img> inside <nav> or <header> (very commonly the logo)
    for tag in ("nav", "header"):
        el = soup.find(tag)
        if el:
            for img in el.find_all("img"):
                src = img.get("src", "").strip()
                if src and not src.startswith("data:") and not src.lower().endswith(".gif"):
                    return urljoin(base_url, src)

    # 4. First <img> inside a link pointing to the homepage root
    for a in soup.find_all("a", href=True):
        target = urljoin(base_url, a["href"])
        if urlparse(target).netloc == domain and urlparse(target).path.rstrip("/") in ("", "/"):
            img = a.find("img")
            if img and img.get("src") and not img["src"].startswith("data:"):
                return urljoin(base_url, img["src"].strip())

    return ""


def _extract_contact(html_text: str) -> dict:
    """Regex-scan raw HTML for phone, email, and German street address."""
    phone_match = re.search(
        r"(\+49[\d\s\-\/()]{5,20}|\(0\d{2,5}\)\s*[\d\s\-]{4,12}|0\d{2,5}[\s\/\-]?\d{3,8}[\d\s\-]*)",
        html_text,
    )
    email_match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,6}", html_text)
    # German address pattern: "Musterstraße 12, 12345 Stadt"
    addr_match = re.search(
        r"[A-ZÄÖÜ][a-zäöüß]+(straße|strasse|str\.|weg|allee|platz|gasse|ring|damm|chaussee)\s+\d+[a-zA-Z]?"
        r",?\s*\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+",
        html_text,
        re.IGNORECASE,
    )
    return {
        "phone": phone_match.group(0).strip() if phone_match else "",
        "email": email_match.group(0).strip() if email_match else "",
        "address": addr_match.group(0).strip() if addr_match else "",
    }


def crawl(url: str) -> CrawledData:
    if not url:
        return CrawledData(found=False)

    result = CrawledData()
    combined_html = ""
    parts = []

    try:
        print(f"[website_crawler] Fetching homepage: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        combined_html += resp.text
        soup = BeautifulSoup(resp.text, "html.parser")

        # Logo detection from homepage
        logo = _find_logo(soup, resp.url)
        if logo:
            result.logo_url = logo
            print(f"[website_crawler] Found logo: {logo}")

        text = _clean_text(soup, 4000)
        if text:
            parts.append(f"=== Startseite ===\n{text}")

        # Collect subpages to crawl
        subpages = _internal_links(soup, resp.url)
        print(f"[website_crawler] Found {len(subpages)} subpages to crawl")

        for link in subpages[:5]:
            try:
                sub_resp = requests.get(link, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
                sub_resp.raise_for_status()
                combined_html += sub_resp.text
                sub_soup = BeautifulSoup(sub_resp.text, "html.parser")

                # Pick up logo from subpages too if not found yet
                if not result.logo_url:
                    logo = _find_logo(sub_soup, link)
                    if logo:
                        result.logo_url = logo

                page_label = urlparse(link).path.strip("/").split("/")[-1].replace("-", " ").title() or "Seite"
                sub_text = _clean_text(sub_soup, 2500)
                if sub_text:
                    parts.append(f"=== {page_label} ===\n{sub_text}")

                time.sleep(0.4)
            except Exception as e:
                print(f"[website_crawler] Skipped {link}: {e}")

        result.found = True
        result.full_text = "\n\n".join(parts)

        # Contact extraction from all HTML collected
        contact = _extract_contact(combined_html)
        result.contact_phone = contact["phone"]
        result.contact_email = contact["email"]
        result.contact_address = contact["address"]

        print(
            f"[website_crawler] Done: {len(parts)} pages crawled | "
            f"phone={'yes' if result.contact_phone else 'no'} | "
            f"email={'yes' if result.contact_email else 'no'} | "
            f"address={'yes' if result.contact_address else 'no'} | "
            f"logo={'yes' if result.logo_url else 'no'}"
        )

    except Exception as e:
        print(f"[website_crawler] Could not crawl {url}: {e}")

    return result
