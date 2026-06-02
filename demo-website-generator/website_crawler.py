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
    "kontakt", "contact", "impressum",              # contact pages first
    "galerie", "gallery", "bilder", "fotos", "portfolio", "referenzen", "projekte",
    "ueber-uns", "uber-uns", "about", "about-us", "ueber", "wir",
    "leistungen", "services", "dienstleistungen", "angebote", "produkte",
    "team", "profil", "unternehmen",
]


@dataclass
class CrawledData:
    found: bool = False
    full_text: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    contact_address: str = ""
    logo_url: str = ""
    company_image_urls: list = field(default_factory=list)


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
        clean = parsed.scheme + "://" + parsed.netloc + parsed.path.rstrip("/")
        if clean in seen or clean == base_url.rstrip("/"):
            continue
        seen.add(clean)
        (priority if _is_priority(full) else others).append(full)

    return (priority + others)[:max_links]


def _clean_text(html: str, max_chars: int = 3500) -> str:
    """Extract structured readable text — works on raw HTML string to avoid mutating shared soup."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "head",
                     "button", "form", "input", "select", "textarea",
                     "nav", "header", "footer", "aside"]):
        tag.decompose()

    lines = []
    for el in soup.find_all(["h1", "h2", "h3", "p", "li", "address", "span", "div"]):
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
    domain = urlparse(base_url).netloc

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

    for container in soup.find_all(class_=re.compile(r"logo", re.I)):
        img = container.find("img")
        if img and img.get("src") and not img["src"].startswith("data:"):
            return urljoin(base_url, img["src"].strip())
    for container in soup.find_all(id=re.compile(r"logo", re.I)):
        img = container.find("img")
        if img and img.get("src") and not img["src"].startswith("data:"):
            return urljoin(base_url, img["src"].strip())

    for tag in ("nav", "header"):
        el = soup.find(tag)
        if el:
            for img in el.find_all("img"):
                src = img.get("src", "").strip()
                if src and not src.startswith("data:") and not src.lower().endswith(".gif"):
                    return urljoin(base_url, src)

    for a in soup.find_all("a", href=True):
        target = urljoin(base_url, a["href"])
        if urlparse(target).netloc == domain and urlparse(target).path.rstrip("/") in ("", "/"):
            img = a.find("img")
            if img and img.get("src") and not img["src"].startswith("data:"):
                return urljoin(base_url, img["src"].strip())

    return ""


def _find_images(soup: BeautifulSoup, base_url: str, seen_urls: set, max_images: int = 5) -> list:
    found = []
    for img in soup.find_all("img"):
        src = img.get("src", "").strip()
        if not src or src.startswith("data:"):
            continue
        if not re.search(r"\.(jpe?g|png|webp)(\?.*)?$", src, re.I):
            continue

        full = urljoin(base_url, src)
        clean = urlparse(full).scheme + "://" + urlparse(full).netloc + urlparse(full).path
        if clean in seen_urls:
            continue

        haystack = " ".join([
            src.lower(),
            img.get("alt", "").lower(),
            " ".join(img.get("class", [])).lower(),
            img.get("id", "").lower(),
        ])
        if any(w in haystack for w in ("logo", "icon", "sprite", "avatar", "pixel", "placeholder", "banner-logo")):
            continue

        skip = False
        for attr in ("width", "height"):
            val = img.get(attr, "")
            try:
                if int(str(val).replace("px", "")) < 150:
                    skip = True
                    break
            except (ValueError, TypeError):
                pass
        if skip:
            continue

        seen_urls.add(clean)
        found.append(full)
        if len(found) >= max_images:
            break

    return found


def _extract_contact(all_page_html: list) -> dict:
    """
    Extract phone, email, and address from a list of raw HTML strings (one per page).
    Works on fresh soup objects — never on a soup already mutated by _clean_text.

    Strategy per field:
      phone  → <a href="tel:..."> across all pages, then regex
      email  → <a href="mailto:..."> across all pages, then regex
      address → <address> tag, then footer/kontakt zone regex, then full-page regex
    """
    phone = email = address = ""

    addr_pattern = re.compile(
        r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]+"
        r"(?:straße|strasse|str\.|weg|allee|platz|gasse|ring|damm|chaussee)"
        r"\s+\d+[a-zA-Z]?,?\s*\d{5}\s+[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\s\-]+",
        re.IGNORECASE,
    )

    for raw_html in all_page_html:
        soup = BeautifulSoup(raw_html, "html.parser")

        # ── Phone from tel: links ───────────────────────────────────────────
        if not phone:
            for a in soup.find_all("a", href=re.compile(r"^tel:", re.I)):
                raw = a["href"].replace("tel:", "").strip()
                if raw:
                    visible = a.get_text(strip=True)
                    phone = visible if re.search(r"\d{4,}", visible) else raw
                    break

        # ── Email from mailto: links ────────────────────────────────────────
        if not email:
            for a in soup.find_all("a", href=re.compile(r"^mailto:", re.I)):
                raw = a["href"].replace("mailto:", "").split("?")[0].strip()
                if raw and "@" in raw:
                    email = raw
                    break

        # ── Address from <address> tag ──────────────────────────────────────
        if not address:
            addr_el = soup.find("address")
            if addr_el:
                txt = re.sub(r"\s+", " ", addr_el.get_text(" ", strip=True))
                m = addr_pattern.search(txt)
                if m:
                    address = re.sub(r"\s+", " ", m.group(0)).strip()

        # ── Address from footer / kontakt zones ────────────────────────────
        if not address:
            zones = []
            footer = soup.find("footer")
            if footer:
                zones.append(footer.get_text(" ", strip=True))
            for cls in ("kontakt", "contact", "footer", "address", "impressum"):
                for el in soup.find_all(class_=re.compile(cls, re.I)):
                    zones.append(el.get_text(" ", strip=True))
            for zone in zones:
                m = addr_pattern.search(re.sub(r"\s+", " ", zone))
                if m:
                    address = re.sub(r"\s+", " ", m.group(0)).strip()
                    break

        if phone and email and address:
            break  # all found — stop scanning pages

    # ── Regex fallback across combined raw HTML ─────────────────────────────
    combined = "\n".join(all_page_html)

    if not phone:
        m = re.search(
            r"(\+49[\s\-\.]?\(?\d+\)?[\d\s\-\.\/]{5,20}"
            r"|0\d{2,5}[\s\/\-\.]?\d{3,8}[\d\s\-\.]*"
            r"|01[5679]\d[\s\-\.]?\d{3,4}[\s\-\.]?\d{3,4})",
            combined,
        )
        if m:
            phone = re.sub(r"\s+", " ", m.group(0)).strip()

    if not email:
        m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,6}", combined)
        if m:
            email = m.group(0).strip()

    if not address:
        m = addr_pattern.search(combined)
        if m:
            address = re.sub(r"\s+", " ", m.group(0)).strip()

    return {"phone": phone, "email": email, "address": address}


def crawl(url: str) -> CrawledData:
    if not url:
        return CrawledData(found=False)

    result = CrawledData()
    all_page_html: list = []   # raw HTML per page — kept intact for contact extraction
    parts = []
    seen_image_urls: set = set()

    try:
        print(f"[website_crawler] Fetching homepage: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        all_page_html.append(resp.text)
        soup = BeautifulSoup(resp.text, "html.parser")

        logo = _find_logo(soup, resp.url)
        if logo:
            result.logo_url = logo
            print(f"[website_crawler] Found logo: {logo}")

        homepage_imgs = _find_images(soup, resp.url, seen_image_urls, max_images=4)
        result.company_image_urls.extend(homepage_imgs)

        # _clean_text now takes raw HTML string — soup stays untouched
        text = _clean_text(resp.text, 5000)
        if text:
            parts.append(f"=== Startseite ===\n{text}")

        subpages = _internal_links(soup, resp.url, max_links=12)
        print(f"[website_crawler] Found {len(subpages)} subpages to crawl")

        for link in subpages[:10]:
            try:
                sub_resp = requests.get(link, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
                sub_resp.raise_for_status()
                all_page_html.append(sub_resp.text)
                sub_soup = BeautifulSoup(sub_resp.text, "html.parser")

                if not result.logo_url:
                    logo = _find_logo(sub_soup, link)
                    if logo:
                        result.logo_url = logo

                is_gallery = any(kw in link.lower() for kw in ("galerie", "gallery", "bilder", "fotos", "portfolio", "referenz", "projekt"))
                page_max_imgs = 6 if is_gallery else 3
                page_imgs = _find_images(sub_soup, link, seen_image_urls, max_images=page_max_imgs)
                result.company_image_urls.extend(page_imgs)

                page_label = urlparse(link).path.strip("/").split("/")[-1].replace("-", " ").title() or "Seite"
                sub_text = _clean_text(sub_resp.text, 3000)
                if sub_text:
                    parts.append(f"=== {page_label} ===\n{sub_text}")

                time.sleep(0.4)
            except Exception as e:
                print(f"[website_crawler] Skipped {link}: {e}")

        result.found = True
        result.full_text = "\n\n".join(parts)

        # Contact extraction uses fresh soups from raw HTML — not the decomposed ones
        contact = _extract_contact(all_page_html)
        result.contact_phone = contact["phone"]
        result.contact_email = contact["email"]
        result.contact_address = contact["address"]

        print(
            f"[website_crawler] Done: {len(parts)} pages | "
            f"images: {len(result.company_image_urls)} | "
            f"phone: {result.contact_phone or '(not found)'} | "
            f"email: {result.contact_email or '(not found)'} | "
            f"address: {result.contact_address or '(not found)'} | "
            f"logo: {'yes' if result.logo_url else 'no'}"
        )

    except Exception as e:
        print(f"[website_crawler] Could not crawl {url}: {e}")

    return result
