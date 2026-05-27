import os
import time
import requests
from urllib.parse import quote
from dataclasses import dataclass, field

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
TIMEOUT = 90  # increased timeout for slower free model


@dataclass
class GeneratedImages:
    images: dict = field(default_factory=dict)  # filename → bytes
    logo_bytes: bytes = None
    logo_concepts: list = field(default_factory=list)  # list of bytes


def _build_prompts(company: str, industry: str, region: str, style: str) -> list:
    # Safe defaults so prompts are always meaningful
    company = company or "professional business"
    industry = industry or "professional services"
    region = region or "Germany"
    base = f"{industry} business {region}"
    style_hint = style if style else "professional modern clean"
    return [
        f"hero banner {base}, {style_hint}, wide angle, no text, photorealistic",
        f"team of professionals {base}, {style_hint}, office, smiling, no text",
        f"service detail {base}, close-up, high quality, {style_hint}, no text",
        f"happy customer {base}, satisfied client, {style_hint}, no text",
        f"modern workspace {base}, {style_hint}, interior, bright, no text",
        f"professional equipment tools {base}, {style_hint}, no text",
        f"aerial cityscape {region} Germany, beautiful, golden hour, no text",
        f"finished result {base}, before after quality, {style_hint}, no text",
        f"collaboration meeting {base}, {style_hint}, conference room, no text",
        f"abstract concept {industry}, modern, {style_hint}, minimal, no text",
    ]


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


def generate(data) -> GeneratedImages:
    result = GeneratedImages()
    prompts = _build_prompts(data.company_name, data.industry, data.region, data.style)

    for i, prompt in enumerate(prompts, start=1):
        filename = f"image-{i:02d}.jpg"
        encoded = quote(prompt)
        url = f"{POLLINATIONS_BASE}/{encoded}?width=1280&height=720&nologo=true&model=turbo"
        try:
            print(f"[image_generator] Generating {filename}...")
            img_bytes = _download(url)
            result.images[filename] = img_bytes
            time.sleep(1)  # be polite to the free API
        except Exception as e:
            print(f"[image_generator] Failed {filename}: {e}")

    # Download logo if URL provided
    if data.logo_url:
        try:
            print(f"[image_generator] Downloading logo from {data.logo_url}...")
            logo_bytes = _download(data.logo_url)
            # Skip SVG — can't reliably serve as a raster image
            stripped = logo_bytes[:100].lstrip()
            if stripped.startswith((b"<svg", b"<?xml", b"<SVG")):
                print("[image_generator] Logo is SVG, skipping (not raster-compatible)")
            else:
                result.logo_bytes = logo_bytes
                print(f"[image_generator] Logo downloaded ({len(logo_bytes):,} bytes)")
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
            logo_url = f"{POLLINATIONS_BASE}/{encoded}?width=512&height=512&nologo=true&model=turbo"
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
            url = f"{POLLINATIONS_BASE}/{encoded}?width=1024&height=512&nologo=true&model=turbo"
            try:
                print(f"[image_generator] Generating logo concept {i}...")
                logo_bytes = _download(url)
                result.logo_concepts.append((f"logo-concept-{i}.jpg", logo_bytes))
                time.sleep(1)
            except Exception as e:
                print(f"[image_generator] Logo concept {i} failed: {e}")

    return result
