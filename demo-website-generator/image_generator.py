import io
import re
import json
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

# ── Image generation rules passed to Claude ──────────────────────────────────
_IMAGE_RULES = """
You are an expert website photography art director generating image prompts for a professional demo website.

CORE RULES — never violate:
- Every image must be realistic, spacious, correctly cropped, and visually unique
- Never generate squeezed, stretched, distorted, repetitive, badly cropped, or overcrowded images
- Never use generic images that do not match the specific business
- Every image must match a different service, section, or business story

SECTION REQUIREMENTS:
1. Hero (16:9) — wide, premium establishing shot, strong first impression, clearly represents the industry
2. About (4:3) — realistic work environment or team, professional and trustworthy, not generic
3–6. Service cards (4:3 each) — ONE image per service, must match that EXACT service title, visually different from all others
7–9. Gallery/projects (4:3 each) — look like separate completed projects, different types, angles, results
10. CTA/background (16:9) — atmospheric wide shot suitable as subtle overlay background

SERVICE IMAGE RULE: Every service image must match the exact service it represents. A visitor must understand the service from the image alone without reading text. For landscaping: Gartengestaltung=garden design/layout, Terrassenbau=terrace/paving, Rasenneuanlage=turf laying, Baumfällung=tree work, Heckenschnitt=hedge trimming, Gartenpflege=maintenance.

NO REPETITION RULE: Every image must be unique in scene, angle, subject, background, composition, and service focus. Reject any image that looks like a duplicate of another.

HUMAN IMAGE RULE: Only include humans when they look natural and realistic. Reject if face/hands/fingers/body look distorted or fake. Prefer wide/medium shots where the work scene matters more than the face. A clean project result image is always better than a bad AI-generated human.

AVOID FAKE CREDIBILITY: Do not invent project counts, awards, or statistics not found in the business data.

PROMPT FORMAT for each image:
"Realistic professional website photography for [industry]. Scene: [specific scene matching this section and service]. Location/context: [region]. Composition: spacious, clean, well-balanced, main subject clearly visible, no crowding, no distortion, natural perspective. Lighting: natural daylight, premium commercial look. Style: modern business website, realistic, high quality, sharp but natural. Avoid: text, watermark, logo, distorted objects, unrealistic AI look, overcrowded composition, squeezed framing, duplicate composition."
"""


@dataclass
class GeneratedImages:
    images: dict = field(default_factory=dict)  # filename → bytes
    logo_bytes: bytes = None
    logo_filename: str = "logo.png"   # "logo.svg" or "logo.png"
    logo_concepts: list = field(default_factory=list)


def _get_industry_scenes(industry: str, company: str, region: str) -> list:
    """Return 8 visually distinct, industry-specific scene descriptions."""
    ind = industry.lower()
    if any(k in ind for k in ["galabau", "garten", "landschaft", "landscap", "außenanlage"]):
        return [
            "premium completed private garden with stone pathway, manicured lawn, terrace and decorative plants, wide establishing shot",
            "professional landscapers working neatly in a residential garden, planting and shaping hedges, natural daylight",
            "modern stone paving and terrace construction in progress, precise laying work, professional tools visible",
            "lush garden border with mixed perennials and ornamental grasses, soft natural light, spacious framing",
            "garden irrigation system being installed, clean professional pipe work, organized site",
            "beautiful finished outdoor relaxation terrace with seating area, warm evening light, premium feel",
            "aerial-style wide view of a landscaped residential property, garden design visible, spacious composition",
            "close detail of high-quality natural stonework and planting combination, craftsmanship focus",
        ]
    elif any(k in ind for k in ["baumschule", "nursery", "pflanzen", "gärtnerei"]):
        return [
            "wide view of outdoor nursery with rows of healthy trees and container shrubs, organized professional display",
            "expert nursery worker caring for container plants, hands-on professional scene, natural light",
            "large specimen trees with root balls ready for sale, premium quality display",
            "colorful seasonal flowers and perennials in organized display beds, vibrant and spacious",
            "customer consulting with nursery expert, plant selection in progress, welcoming atmosphere",
            "greenhouse interior with propagation trays and young plants, clean and professional",
            "freshly potted shrubs and trees lined up outdoors, symmetrical clean composition",
            "detail of healthy plant root ball and soil, quality and care focus",
        ]
    elif any(k in ind for k in ["bäcker", "bäckerei", "bakery", "konditor"]):
        return [
            "wide bakery counter display with artisan breads, pastries and cakes, warm inviting light",
            "baker shaping dough on flour-dusted wooden board, natural light, authentic craft",
            "golden brown fresh-baked loaves just out of the oven, steam rising, premium food photography",
            "elegant celebration cake being decorated with precision, professional kitchen background",
            "organized bakery display window with seasonal pastries and rolls, warm interior light",
            "croissants and rolls arranged beautifully on rustic wooden boards, appetizing close-up",
            "professional baker at work in clean bright kitchen, confident and skilled action shot",
            "fresh ingredients: flour, eggs, butter arranged professionally on counter, clean composition",
        ]
    elif any(k in ind for k in ["restaurant", "gastro", "café", "küche", "bistro", "gaststätte"]):
        return [
            "elegant restaurant interior with laid tables, warm candlelight, sophisticated atmosphere",
            "chef plating a signature dish with precision in a professional kitchen, action shot",
            "beautifully presented main course on white plate, professional food photography, natural light",
            "welcoming café exterior with outdoor seating, warm morning light, inviting atmosphere",
            "fresh seasonal ingredients arranged on a marble counter, colors and textures visible",
            "sommelier presenting wine selection to guests at a laid table, professional service",
            "kitchen team working efficiently in a clean professional kitchen, organized and skilled",
            "dessert presentation: elegant plated dessert with garnish, appetizing close-up",
        ]
    elif any(k in ind for k in ["it", "tech", "software", "digital", "web"]):
        return [
            "modern office workspace with dual monitors showing clean code, natural daylight, professional",
            "team collaboration meeting around large screen with project data, engaged and professional",
            "developer working focused at clean desk with equipment, bright modern office",
            "close-up of hands on laptop keyboard with screen content visible, sharp and professional",
            "client presentation in bright modern meeting room, confident and clear communication",
            "server room or network infrastructure, clean organized cabling, professional facility",
            "team standup meeting in modern open-plan office, collaborative and dynamic",
            "UX design work on tablet and whiteboard, creative professional environment",
        ]
    elif any(k in ind for k in ["bau", "hochbau", "tiefbau", "construction"]):
        return [
            "wide shot of modern construction site with professional team and equipment, organized and active",
            "freshly completed residential building exterior, clean architectural facade, natural daylight",
            "precision bricklaying or concrete work in progress, skilled craftsmen visible",
            "construction team reviewing blueprints on site, professional and organized safety gear",
            "structural steel or framework installation, industrial wide angle, impressive scale",
            "site manager overseeing clean organized work site, leadership and expertise visible",
            "newly completed building detail: clean render, windows, entrance, premium quality",
            "foundation or infrastructure work in progress, professional excavation and groundwork",
        ]
    elif any(k in ind for k in ["maler", "anstrich", "farbe", "paint"]):
        return [
            "professional painter applying smooth coat on interior wall, clean roller technique, bright room",
            "beautifully painted bright room with crisp edges and premium finish, interior reveal",
            "exterior facade being painted on a residential building, scaffolding and professionals visible",
            "decorator masking edges precisely before painting, detail craftsmanship focus",
            "before and after wall comparison showing transformation, striking clean result",
            "paint color selection consultation, professional showing samples to client",
            "professional spray painting equipment in use, clean and modern technique",
            "freshly painted exterior detail: shutters, trim, facade, premium finish quality",
        ]
    elif any(k in ind for k in ["elektro", "electric", "strom", "licht"]):
        return [
            "licensed electrician working on a modern electrical panel, professional and focused",
            "smart home installation in progress, clean organized wiring and modern devices",
            "outdoor facade lighting installation complete on a building, warm evening atmosphere",
            "electrician consulting with client in bright modern interior, friendly professional",
            "clean completed switchboard installation, tidy and precisely labeled, quality result",
            "solar panel installation on rooftop, professional team working, wide angle",
            "modern EV charging station installation in a garage, clean and professional",
            "interior recessed lighting installation complete, dramatic and elegant result",
        ]
    elif any(k in ind for k in ["sanitär", "plumbing", "heizung", "klempner", "bad"]):
        return [
            "professional plumber installing premium bathroom fixtures, clean modern bathroom",
            "new central heating system installation, neat organized pipework, professional quality",
            "luxury bathroom renovation reveal, premium tiles and fixtures, natural light",
            "plumber working efficiently under sink, professional tools organized, confident expert",
            "underfloor heating installation in progress, clean pipe laying on insulation",
            "modern boiler and heating system neatly installed in utility room",
            "bathroom design consultation with client, tile samples and plans visible",
            "completed outdoor drainage or pipe installation, professional and clean result",
        ]
    elif any(k in ind for k in ["florist", "blumen", "floral"]):
        return [
            "professional florist creating elegant floral arrangement, natural studio lighting",
            "premium wedding bouquet in soft natural light, beautiful floral photography",
            "colorful flower shop interior with fresh seasonal blooms in display, inviting",
            "florist carefully selecting and trimming stems, focused expert craft",
            "completed event table decoration with floral centerpieces, sophisticated space",
            "seasonal outdoor flower arrangement display at entrance, vibrant and welcoming",
            "close detail of fresh flower petals and textures, macro beauty photography",
            "florist workshop with tools and materials arranged professionally, creative space",
        ]
    elif any(k in ind for k in ["beauty", "kosmetik", "friseur", "wellness", "spa"]):
        return [
            "professional beauty treatment in a clean modern salon, relaxed and premium atmosphere",
            "stylish salon interior with natural light, elegant minimal decor, inviting space",
            "expert stylist working carefully with a client, skilled and attentive",
            "premium beauty products and tools neatly displayed on white surface, clean aesthetic",
            "relaxing treatment room with soft lighting, natural elements, serene atmosphere",
            "manicure or nail treatment close-up, precision and care, premium feel",
            "hair styling result reveal, client looking confident, bright natural light",
            "reception area of beauty salon, welcoming and elegant first impression",
        ]
    elif any(k in ind for k in ["reinigung", "cleaning", "gebäude", "hausmeister"]):
        return [
            "professional cleaning team working efficiently in a large commercial space",
            "spotless clean office or facility after professional cleaning, pristine bright result",
            "window cleaning on commercial building facade, professional equipment, safe and skilled",
            "industrial cleaning machine in use in a wide commercial floor space",
            "detail of perfectly cleaned surface reflecting light, quality standard result",
            "cleaning professional organizing and stocking supplies in a utility area",
            "before and after comparison of a cleaned commercial kitchen, dramatic result",
            "team of uniformed cleaning professionals arriving at a building, professional appearance",
        ]
    elif any(k in ind for k in ["immobilien", "makler", "real estate"]):
        return [
            "modern residential property exterior in warm natural daylight, inviting and premium",
            "bright spacious living room interior, professionally staged, large windows",
            "estate agent warmly presenting a property to interested buyers, professional",
            "aerial or elevated view of residential property with landscaped garden",
            "premium apartment interior with high-end finishes, clean and desirable",
            "modern kitchen interior staging, clean design, professional real estate photography",
            "property exterior at golden hour, warm light on facade, premium curb appeal",
            "estate agent at desk consulting with clients, professional welcoming office",
        ]
    else:
        return [
            f"professional team providing expert {industry} services, modern clean environment",
            f"skilled {industry} professional at work, confident and focused, natural light",
            f"completed high-quality {industry} project result, impressive and professional",
            f"customer consultation for {industry} services, welcoming professional atmosphere",
            f"professional workspace and equipment for {industry}, organized and impressive",
            f"team meeting and planning for {industry} project, collaborative and dynamic",
            f"quality detail of {industry} work, craftsmanship and expertise visible",
            f"wide view of {industry} project in progress, professional team and environment",
        ]


def _build_prompts(company: str, industry: str, region: str, style: str) -> list:
    co = company or "local business"
    ind = industry or "professional services"
    reg = region or "Germany"

    avoid = (
        "Avoid: text in image, watermark, logo, distorted people or objects, "
        "unrealistic AI-look, overcrowded composition, squeezed or stretched framing, "
        "blurry subjects, generic stock-photo feel, duplicate scenes."
    )
    quality = (
        "Composition: spacious, clean, well-balanced, main subject clearly visible, "
        "rule of thirds, breathing room around subject, no crowding. "
        "Lighting: natural daylight, soft shadows, premium commercial look. "
        "Style: realistic professional website photography, sharp but natural, high quality."
    )

    scenes = _get_industry_scenes(ind, co, reg)

    section_labels = [
        "hero section — wide 16:9 establishing shot, strong first impression, spacious landscape",
        "about section — 4:3 professional team or work environment, authentic human element",
        "service card 1 — 4:3 medium shot, single clear subject, visually unique",
        "service card 2 — 4:3 different angle and subject from previous service image",
        "service card 3 — 4:3 visually distinct scene, shows different aspect of the business",
        "service card 4 — 4:3 detail or craft focus, quality and expertise close-up",
        "gallery image 1 — 4:3 completed project wide view, impressive full result",
        "gallery image 2 — 4:3 project from different perspective, variety in composition",
        "gallery image 3 — 4:3 customer or result in context, warm and authentic",
        "CTA background — 16:9 atmospheric wide shot, suitable as subtle overlay background",
    ]

    prompts = []
    for i, (scene, label) in enumerate(zip(scenes, section_labels)):
        prompt = (
            f"Realistic professional website photography for {ind} company in {reg}. "
            f"Website section: {label}. "
            f"Scene: {scene}. "
            f"Location/context: {reg} region, relevant professional environment. "
            f"{quality} {avoid}"
        )
        prompts.append(prompt)

    return prompts


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


def _generate_prompts_with_claude(data, crawled=None) -> list:
    """Ask Claude to generate 10 business-specific, rule-compliant image prompts."""
    import anthropic
    import config

    context_parts = [
        f"Company name: {data.company_name}",
        f"Industry: {data.industry}",
        f"Region: {data.region or 'Deutschland'}",
        f"Services: {data.services or 'see website content below'}",
        f"Target audience: {data.target_audience or 'general customers'}",
        f"Visual style: {data.style or 'professional modern'}",
    ]
    if crawled and getattr(crawled, "found", False) and crawled.full_text:
        context_parts.append(f"\nWebsite content (crawled):\n{crawled.full_text[:3000]}")

    context = "\n".join(context_parts)

    user_prompt = (
        f"Business data:\n{context}\n\n"
        "Generate exactly 10 image prompts for these website sections in this order:\n"
        "1. Hero image (16:9) — wide premium establishing shot\n"
        "2. About section (4:3) — realistic team or work environment\n"
        "3. Service image 1 (4:3) — matches the company's first/main service exactly\n"
        "4. Service image 2 (4:3) — matches second service, visually distinct\n"
        "5. Service image 3 (4:3) — matches third service, visually distinct\n"
        "6. Service image 4 (4:3) — craft/detail/quality focus\n"
        "7. Gallery image 1 (4:3) — completed project, wide view\n"
        "8. Gallery image 2 (4:3) — different project, different angle\n"
        "9. Gallery image 3 (4:3) — result or outcome shown in context\n"
        "10. CTA background (16:9) — atmospheric, suitable as subtle overlay\n\n"
        "Return ONLY a valid JSON array of exactly 10 strings. No explanation, no markdown."
    )

    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2500,
            temperature=0.7,
            system=_IMAGE_RULES,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
        prompts = json.loads(raw)
        if isinstance(prompts, list) and len(prompts) >= 10:
            print(f"[image_generator] Claude generated {len(prompts)} custom image prompts")
            return prompts[:10]
    except Exception as e:
        print(f"[image_generator] Claude prompt generation failed ({e}), using fallback prompts")

    return None  # caller falls back to _build_prompts()


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
        # Ask Claude to generate business-specific prompts following the image rules
        prompts = _generate_prompts_with_claude(data, crawled) or \
                  _build_prompts(data.company_name, data.industry, data.region, data.style)
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
