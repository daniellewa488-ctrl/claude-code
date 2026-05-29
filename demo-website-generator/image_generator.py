import io
import time
import random
import requests
from urllib.parse import quote
from dataclasses import dataclass, field
try:
    from PIL import Image as _PILImage
    _PILLOW_OK = True
except ImportError:
    _PILLOW_OK = False

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
TIMEOUT = 90  # increased timeout for slower free model


@dataclass
class GeneratedImages:
    images: dict = field(default_factory=dict)  # filename → bytes
    logo_bytes: bytes = None
    logo_filename: str = "logo.png"   # "logo.svg" or "logo.png"
    logo_concepts: list = field(default_factory=list)


def _build_prompts(company: str, industry: str, region: str, style: str) -> list:
    co = company or "local business"
    industry = industry or "professional services"
    region = region or "Germany"
    style_hint = style if style else "professional modern clean"
    return [
        f"{industry} in {region}, exterior building facade, professional signage for {co}, wide angle, photorealistic, golden hour, no text",
        f"{industry} workers at {co} in {region}, skilled craftspeople on the job, {style_hint}, natural daylight, no text, photorealistic",
        f"close-up of high-quality {industry} work by {co}, craftsmanship detail, {style_hint}, sharp focus, no text, photorealistic",
        f"satisfied customer reviewing completed {industry} work, smiling, residential setting in {region}, {style_hint}, no text, photorealistic",
        f"{industry} project in progress, professional team at work, {region}, {style_hint}, wide shot, no text, photorealistic",
        f"professional tools and materials for {industry}, neatly arranged, {style_hint}, studio quality, no text, photorealistic",
        f"beautiful residential outdoor area in {region}, lush surroundings, warm light, cinematic, no text, photorealistic",
        f"impressive finished {industry} project result, before-after quality, {co}, {style_hint}, no text, photorealistic",
        f"team of {industry} professionals consulting with homeowner in {region}, {style_hint}, no text, photorealistic",
        f"{industry} showcase, completed project by {co}, premium quality, {style_hint}, clean composition, no text",
    ]


def _is_quality_image(img_bytes: bytes, min_width: int = 400, min_height: int = 280) -> bool:
    """Return True if image meets minimum pixel dimensions for use on the website."""
    if not _PILLOW_OK:
        return len(img_bytes) > 20000  # fallback: file size proxy
    try:
        img = _PILImage.open(io.BytesIO(img_bytes))
        w, h = img.size
        if w < min_width or h < min_height:
            print(f"[image_generator] Quality reject: {w}x{h} < {min_width}x{min_height}")
            return False
        return True
    except Exception:
        return False


def _download(url: str) -> bytes:
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            if attempt < 2:
                print(f"[image_generator] Retrying after error: {e}")
                time.sleep(5)
            else:
                raise


def generate(data, crawled=None) -> GeneratedImages:
    result = GeneratedImages()
    base_seed = random.randint(1, 999999)

    # ── Step 1: Use company's own website photos first ────────────────────────
    company_slots = 0
    company_image_urls = getattr(crawled, "company_image_urls", []) if crawled else []
    if company_image_urls:
        print(f"[image_generator] Found {len(company_image_urls)} company images to use first")
    for img_url in company_image_urls:
        if company_slots >= 10:
            break
        slot = company_slots + 1
        filename = f"image-{slot:02d}.jpg"
        try:
            print(f"[image_generator] Downloading company image → {filename}: {img_url}")
            img_bytes = _download(img_url)
            if _is_quality_image(img_bytes):
                result.images[filename] = img_bytes
                company_slots += 1
                print(f"[image_generator] Accepted company image {filename}")
            else:
                print(f"[image_generator] Rejected low-quality company image, will use AI instead")
        except Exception as e:
            print(f"[image_generator] Failed company image {img_url}: {e}")

    # ── Step 2: Fill remaining slots with AI-generated images ─────────────────
    remaining = 10 - company_slots
    if remaining > 0:
        prompts = _build_prompts(data.company_name, data.industry, data.region, data.style)
        ai_count = 0
        for i, prompt in enumerate(prompts, start=1):
            if ai_count >= remaining:
                break
            slot = company_slots + ai_count + 1
            filename = f"image-{slot:02d}.jpg"
            encoded = quote(prompt)
            seed = base_seed + i
            url = f"{POLLINATIONS_BASE}/{encoded}?width=1280&height=720&nologo=true&model=turbo&seed={seed}"
            try:
                print(f"[image_generator] Generating AI image {filename} (seed={seed})...")
                img_bytes = _download(url)
                result.images[filename] = img_bytes
                ai_count += 1
                time.sleep(1)
            except Exception as e:
                print(f"[image_generator] Failed {filename}: {e}")

    # Download logo if URL provided
    if data.logo_url:
        try:
            print(f"[image_generator] Downloading logo from {data.logo_url}...")
            logo_bytes = _download(data.logo_url)
            stripped = logo_bytes[:200].lstrip()
            if stripped.startswith((b"<svg", b"<?xml", b"<SVG")):
                # SVG logo — serve as logo.svg (browsers handle it perfectly in <img>)
                result.logo_bytes = logo_bytes
                result.logo_filename = "logo.svg"
                print(f"[image_generator] SVG logo accepted ({len(logo_bytes):,} bytes) → logo.svg")
            elif len(logo_bytes) > 100:
                result.logo_bytes = logo_bytes
                result.logo_filename = "logo.png"
                print(f"[image_generator] Logo downloaded ({len(logo_bytes):,} bytes) → logo.png")
            else:
                print("[image_generator] Logo response too small, ignoring")
        except Exception as e:
            print(f"[image_generator] Logo download failed: {e}")

    # Generate a brand-new AI logo if requested and no logo was downloaded
    if getattr(data, 'generate_logo', False) and not result.logo_bytes:
        try:
            co = data.company_name or "professional business"
            ind = data.industry or "professional services"
            print(f"[image_generator] Generating AI logo for '{co}'...")
            style_hint = data.style or "professional modern clean"
            logo_prompt = (
                f"professional minimalist logo icon for {co}, "
                f"{ind} company, {style_hint}, "
                "clean vector illustration style, white background, "
                "no text labels, suitable as brand mark, high quality"
            )
            encoded = quote(logo_prompt)
            logo_url = f"{POLLINATIONS_BASE}/{encoded}?width=512&height=512&nologo=true&model=turbo&seed={base_seed}"
            result.logo_bytes = _download(logo_url)
            print(f"[image_generator] AI logo generated ({len(result.logo_bytes):,} bytes)")
        except Exception as e:
            print(f"[image_generator] AI logo generation failed: {e}")

    # Generate logo concepts if facelift requested
    if data.logo_facelift:
        logo_prompts = [
            f"modern minimalist logo concept for {data.company_name} {data.industry}, vector style, clean, white background, no text",
            f"professional logo design {data.company_name} {data.industry}, bold typography style, white background, no text",
            f"creative logo concept {data.company_name} {data.industry}, icon + wordmark layout, white background, no text",
        ]
        for i, prompt in enumerate(logo_prompts, start=1):
            encoded = quote(prompt)
            url = f"{POLLINATIONS_BASE}/{encoded}?width=1024&height=512&nologo=true&model=turbo&seed={base_seed + 100 + i}"
            try:
                print(f"[image_generator] Generating logo concept {i}...")
                logo_bytes = _download(url)
                result.logo_concepts.append((f"logo-concept-{i}.jpg", logo_bytes))
                time.sleep(1)
            except Exception as e:
                print(f"[image_generator] Logo concept {i} failed: {e}")

    return result
