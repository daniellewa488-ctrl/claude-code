import re
import time
import requests
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DemoBot/1.0; +https://hannahs-webdesign.de)"}
TIMEOUT = 12

# Page paths we want to crawl first — most likely to have useful content
PRIORITY_KEYWORDS = [
    "galerie", "gallery", "bilder", "fotos", "portfolio", "referenzen", "projekte",
    "ueber-uns", "uber-uns", "about", "about-us", "ueber", "wir",
    "leistungen", "services", "dienstleistungen", "angebote", "produkte",
    "kontakt", "contact",
    "team", "profil", "unternehmen",
]


@dataclass
class CrawledData:
    found: bool = False
    full_text: str = ""                           # Combined structured text from all pages (fed to Claude)
    contact_phone: str = ""                       # Extracted phone number
    contact_email: str = ""                       # Extracted email
    contact_address: str = ""                     # Extracted street address
    logo_url: str = ""                            # Absolute URL of the logo image
    company_image_urls: list = field(default_factory=list)  # Real photos found on their website


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


def _find_images(soup: BeautifulSoup, base_url: str, seen_urls: set, max_images: int = 5) -> list:
    """Extract real content photos from the page — skip logos, icons, and tiny images."""
    found = []

    # Also check CSS background-image in style attributes
    candidates = soup.find_all("img")

    for img in candidates:
        src = img.get("src", "").strip()
        if not src or src.startswith("data:"):
            continue
        if not re.search(r"\.(jpe?g|png|webp)(\?.*)?$", src, re.I):
            continue

        full = urljoin(base_url, src)
        clean = urlparse(full).scheme + "://" + urlparse(full).netloc + urlparse(full).path
        if clean in seen_urls:
            continue

        # Skip logos, icons, sprites, and navigation graphics
        haystack = " ".join([
            src.lower(),
            img.get("alt", "").lower(),
            " ".join(img.get("class", [])).lower(),
            img.get("id", "").lower(),
        ])
        if any(w in haystack for w in ("logo", "icon", "sprite", "avatar", "pixel", "placeholder", "banner-logo")):
            continue

        # Skip images that are tiny based on explicit dimensions
        for attr in ("width", "height"):
            val = img.get(attr, "")
            try:
                if int(str(val).replace("px", "")) < 150:
                    continue
            except (ValueError, TypeError):
                pass

        seen_urls.add(clean)
        found.append(full)
        if len(found) >= max_images:
            break

    return found


def _extract_contact(html_text: str, soup: BeautifulSoup = None) -> dict:
    """
    Extract phone, email, and address from a page.
    Priority: structured HTML tags → regex fallback.
    """
    phone = email = address = ""

    # ── 1. Structured HTML extraction (most reliable) ────────────────────────
    if soup:
        # tel: links give the exact formatted number
        for a in soup.find_all("a", href=re.compile(r"^tel:", re.I)):
            raw = a["href"].replace("tel:", "").strip()
            if raw:
                # Prefer the visible text (better formatted), fall back to href value
                visible = a.get_text(strip=True)
                phone = visible if visible else raw
                break

        # mailto: links give the exact email
        for a in soup.find_all("a", href=re.compile(r"^mailto:", re.I)):
            raw = a["href"].replace("mailto:", "").split("?")[0].strip()
            if raw and "@" in raw:
                email = raw
                break

        # <address> tag or elements with class/id containing "kontakt"/"address"/"footer"
        search_zones = []
        addr_el = soup.find("address")
        if addr_el:
            search_zones.append(addr_el.get_text(" ", strip=True))
        for cls_hint in ("kontakt", "contact", "footer", "address", "impressum"):
            for el in soup.find_all(class_=re.compile(cls_hint, re.I)):
                search_zones.append(el.get_text(" ", strip=True))
        footer = soup.find("footer")
        if footer:
            search_zones.append(footer.get_text(" ", strip=True))

        addr_pattern = re.compile(
            r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]+"
            r"(?:straße|strasse|str\.|weg|allee|platz|gasse|ring|damm|chaussee)"
            r"\s+\d+[a-zA-Z]?,?\s*\d{5}\s+[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\s\-]+",
            re.IGNORECASE,
        )
        for zone in search_zones:
            m = addr_pattern.search(zone)
            if m:
                address = re.sub(r"\s+", " ", m.group(0)).strip()
                break

    # ── 2. Regex fallback on raw HTML ─────────────────────────────────────────
    if not phone:
        m = re.search(
            r"(\+49[\s\-\.]?\(?\d+\)?[\d\s\-\.\/]{5,20}"
            r"|0\d{2,5}[\s\/\-\.]?\d{3,8}[\d\s\-\.]*"
            r"|01[567]\d[\s\-\.]?\d{3,4}[\s\-\.]?\d{3,4})",  # mobile
            html_text,
        )
        if m:
            phone = re.sub(r"\s+", " ", m.group(0)).strip()

    if not email:
        m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,6}", html_text)
        if m:
            email = m.group(0).strip()

    if not address:
        m = re.search(
            r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]+"
            r"(?:straße|strasse|str\.|weg|allee|platz|gasse|ring|damm|chaussee)"
            r"\s+\d+[a-zA-Z]?,?\s*\d{5}\s+[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\s\-]+",
            html_text,
            re.IGNORECASE,
        )
        if m:
            address = re.sub(r"\s+", " ", m.group(0)).strip()

    return {"phone": phone, "email": email, "address": address}


def crawl(url: str) -> CrawledData:
    if not url:
        return CrawledData(found=False)

    result = CrawledData()
    combined_html = ""
    parts = []
    seen_image_urls: set = set()

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

        # Collect content images from homepage
        homepage_imgs = _find_images(soup, resp.url, seen_image_urls, max_images=4)
        result.company_image_urls.extend(homepage_imgs)

        text = _clean_text(soup, 5000)
        if text:
            parts.append(f"=== Startseite ===\n{text}")

        # Collect subpages to crawl
        subpages = _internal_links(soup, resp.url, max_links=12)
        print(f"[website_crawler] Found {len(subpages)} subpages to crawl")

        for link in subpages[:10]:
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

                # Collect content images — gallery/portfolio pages can contribute more
                is_gallery = any(kw in link.lower() for kw in ("galerie", "gallery", "bilder", "fotos", "portfolio", "referenz", "projekt"))
                page_max_imgs = 6 if is_gallery else 3
                page_imgs = _find_images(sub_soup, link, seen_image_urls, max_images=page_max_imgs)
                result.company_image_urls.extend(page_imgs)

                page_label = urlparse(link).path.strip("/").split("/")[-1].replace("-", " ").title() or "Seite"
                sub_text = _clean_text(sub_soup, 3000)
                if sub_text:
                    parts.append(f"=== {page_label} ===\n{sub_text}")

                time.sleep(0.4)
            except Exception as e:
                print(f"[website_crawler] Skipped {link}: {e}")

        result.found = True
        result.full_text = "\n\n".join(parts)

        # Contact extraction — pass homepage soup for structured tag scanning first
        contact = _extract_contact(combined_html, soup)
        result.contact_phone = contact["phone"]
        result.contact_email = contact["email"]
        result.contact_address = contact["address"]

        print(
            f"[website_crawler] Done: {len(parts)} pages crawled | "
            f"images found: {len(result.company_image_urls)} | "
            f"phone={'yes' if result.contact_phone else 'no'} | "
            f"email={'yes' if result.contact_email else 'no'} | "
            f"address={'yes' if result.contact_address else 'no'} | "
            f"logo={'yes' if result.logo_url else 'no'}"
        )

    except Exception as e:
        print(f"[website_crawler] Could not crawl {url}: {e}")

    return result
