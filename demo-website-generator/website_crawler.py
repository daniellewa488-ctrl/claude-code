import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DemoBot/1.0)"
}
TIMEOUT = 10


def _clean_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _internal_links(soup: BeautifulSoup, base_url: str) -> list:
    domain = urlparse(base_url).netloc
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc != domain:
            continue
        path = parsed.path.lower()
        if re.search(r"\.(jpg|jpeg|png|gif|svg|pdf|zip|css|js)$", path):
            continue
        if full not in links and full != base_url:
            links.append(full)
        if len(links) >= 3:
            break
    return links


def crawl(url: str) -> str:
    if not url:
        return ""

    parts = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        homepage_text = _clean_text(soup)[:5000]
        parts.append(f"=== Startseite ({url}) ===\n{homepage_text}")

        subpages = _internal_links(soup, url)
        if subpages:
            try:
                sub_resp = requests.get(subpages[0], headers=HEADERS, timeout=TIMEOUT)
                sub_resp.raise_for_status()
                sub_soup = BeautifulSoup(sub_resp.text, "html.parser")
                sub_text = _clean_text(sub_soup)[:2000]
                parts.append(f"=== Unterseite ({subpages[0]}) ===\n{sub_text}")
            except Exception:
                pass
    except Exception as e:
        print(f"[website_crawler] Could not crawl {url}: {e}")
        return ""

    return "\n\n".join(parts)
