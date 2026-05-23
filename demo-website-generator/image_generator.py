import os
import time
import requests
from urllib.parse import quote
from dataclasses import dataclass, field

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
TIMEOUT = 60


@dataclass
class GeneratedImages:
    images: dict = field(default_factory=dict)  # filename → bytes
    logo_bytes: bytes = None
    logo_concepts: list = field(default_factory=list)  # list of bytes


def _build_prompts(company: str, industry: str, region: str, style: str) -> list:
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
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.content


def generate(data) -> GeneratedImages:
    result = GeneratedImages()
    prompts = _build_prompts(data.company_name, data.industry, data.region, data.style)

    for i, prompt in enumerate(prompts, start=1):
        filename = f"image-{i:02d}.jpg"
        encoded = quote(prompt)
        url = f"{POLLINATIONS_BASE}/{encoded}?width=1280&height=720&nologo=true&model=flux"
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
            result.logo_bytes = _download(data.logo_url)
        except Exception as e:
            print(f"[image_generator] Logo download failed: {e}")

    # Generate logo concepts if facelift requested
    if data.logo_facelift:
        logo_prompts = [
            f"modern minimalist logo concept for {data.company_name} {data.industry}, vector style, clean, white background, no text",
            f"professional logo design {data.company_name} {data.industry}, bold typography style, white background, no text",
            f"creative logo concept {data.company_name} {data.industry}, icon + wordmark layout, white background, no text",
        ]
        for i, prompt in enumerate(logo_prompts, start=1):
            encoded = quote(prompt)
            url = f"{POLLINATIONS_BASE}/{encoded}?width=1024&height=512&nologo=true&model=flux"
            try:
                print(f"[image_generator] Generating logo concept {i}...")
                logo_bytes = _download(url)
                result.logo_concepts.append((f"logo-concept-{i}.jpg", logo_bytes))
                time.sleep(1)
            except Exception as e:
                print(f"[image_generator] Logo concept {i} failed: {e}")

    return result
