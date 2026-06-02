import io
import re
import json
import time
import random
import requests
from urllib.parse import quote
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    from PIL import Image as _PILImage
    _PILLOW_OK = True
except ImportError:
    _PILLOW_OK = False

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
TIMEOUT = 120

# ── Image generation rules passed to Claude ──────────────────────────────────
_IMAGE_RULES = """
You are a professional photo director creating DSLR photography prompts for a premium business website.
The target quality is: photorealistic, sharp, beautiful depth of field with soft bokeh background — exactly like high-end stock photography shot on a Canon EOS R5 or Sony A7R.

CORE RULES — never violate:
- Every prompt must produce a PHOTOGRAPH, not an illustration or rendering
- Every image must be unique in scene, angle, subject, and composition
- Every image must match the exact business and section it represents
- No humans unless the scene truly needs them — prefer results/environments/objects
- If humans are needed: wide or medium shot only, face not the focus, no distorted hands/fingers

SECTION REQUIREMENTS:
1. Hero (16:9) — cinematic wide establishing shot, golden hour or bright natural light, premium first impression
2. About (4:3) — authentic workplace or environment, warm and trustworthy, real-feeling
3–6. Service cards (4:3 each) — one image per service, scene unmistakably matches that service, bokeh background
7–9. Gallery/projects (4:3 each) — completed project result, different angles and compositions
10. CTA/background (16:9) — atmospheric, slightly soft, works as page background with text overlay

PHOTOGRAPHY PROMPT FORMAT (use for every image):
"[Specific detailed scene]. [Location/environment details]. DSLR photograph, Canon EOS R5, 35mm lens, f/2.8 aperture, shallow depth of field, soft bokeh background, natural daylight, sharp subject, photorealistic, high-end commercial photography. No text, no watermark, no logo, no distortion."

QUALITY REQUIREMENTS:
- Subject must be sharp, background softly blurred (bokeh)
- Natural daylight or warm golden hour lighting — never flat or studio-lit
- Spacious composition with breathing room — never cramped or overcrowded
- Colours vivid but natural — not oversaturated
- No AI artefacts, no plastic-looking textures, no unnatural geometry
"""


@dataclass
class GeneratedImages:
    images: dict = field(default_factory=dict)  # filename → bytes
    logo_bytes: bytes = None
    logo_filename: str = "logo.png"   # "logo.svg" or "logo.png"
    logo_concepts: list = field(default_factory=list)


def _get_industry_scenes(industry: str, company: str, region: str) -> list:
    """Return 8 visually distinct, industry-specific scene descriptions for DSLR photography prompts."""
    ind = industry.lower()
    if any(k in ind for k in ["galabau", "garten", "landschaft", "landscap", "außenanlage"]):
        return [
            "sweeping view of a beautifully landscaped private garden with curved stone pathway, manicured lawn, shaped hedges and flowering borders, golden afternoon light",
            "lush private garden with active sprinkler system watering a perfect green lawn, colorful flower beds in background, shallow depth of field",
            "freshly laid natural stone terrace with modern garden furniture, surrounding plants, warm sunlight, residential home visible in soft background",
            "close-up of healthy ornamental shrubs and perennial border planting, rich green tones, soft bokeh background, natural morning light",
            "professional hedge trimming result — perfectly geometric dark green hedges bordering a residential property, sharp lines, blue sky background",
            "garden pathway lined with mature plants and ornamental grasses, soft evening golden hour light, leading-line composition",
            "completed landscaping project: full garden transformation with lawn, borders, stone path and seating area, wide residential view",
            "premium stone and paving craftsmanship detail — natural stone surface with plant border, sharp foreground, soft green background bokeh",
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

    suffix = (
        "DSLR photograph, Canon EOS R5, 35mm lens, f/2.8 aperture, "
        "shallow depth of field, soft bokeh background, natural daylight, "
        "sharp subject, photorealistic, high-end commercial photography. "
        "No text, no watermark, no logo, no distortion."
    )

    scenes = _get_industry_scenes(ind, co, reg)

    section_contexts = [
        f"Wide establishing shot of a premium {ind} environment in {reg}, cinematic composition, golden hour light",
        f"Authentic {ind} workplace or professional environment, warm and trustworthy atmosphere, {reg}",
        f"Close-medium shot clearly showing the first main service of a {ind} business, sharp subject with bokeh",
        f"Different angle — second distinct service of {ind}, unique scene from previous images, {reg}",
        f"Third service area of {ind} clearly visible, different subject and environment from previous",
        f"Detail/craftsmanship close-up for {ind}, texture and quality visible, sharp foreground bokeh background",
        f"Completed project result for {ind} business, wide view, impressive outcome, {reg}",
        f"Same project type but different angle and composition, variety, {reg}",
        f"Finished result in real-world context, authentic environment, warm light, {reg}",
        f"Atmospheric wide shot for {ind}, soft natural light, works as website background, {reg}",
    ]

    prompts = []
    for scene, context in zip(scenes, section_contexts):
        prompt = f"{context}. {scene}. {suffix}"
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


def _download(url: str, retries: int = 2) -> bytes:
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            if attempt < retries - 1:
                print(f"[image_generator] Retrying after error: {e}")
                time.sleep(3)
            else:
                raise


# ── FLUX.1-schnell via official HF Space (100% free, no API key needed) ──────

def _flux_space_generate(prompt: str, width: int, height: int, seed: int) -> bytes:
    """
    Free FLUX.1-schnell via the official Black Forest Labs HF Space.
    Authenticating with a free HF token gives enough ZeroGPU quota.
    """
    from gradio_client import Client
    import config as _cfg

    # Cap to safe dimensions for speed
    w = min(width, 1360)
    h = min(height, 768)

    token = _cfg.HF_TOKEN or None  # free HF token = more ZeroGPU quota
    client = Client("black-forest-labs/FLUX.1-schnell", hf_token=token, verbose=False)
    result = client.predict(
        prompt=prompt,
        seed=seed,
        randomize_seed=False,
        width=w,
        height=h,
        num_inference_steps=4,
        api_name="/infer",
    )
    # result is (image_path, seed_used)
    image_path = result[0] if isinstance(result, (list, tuple)) else result
    with open(image_path, "rb") as f:
        return f.read()


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

    dslr_suffix = (
        "DSLR photograph, Canon EOS R5, 35mm lens, f/2.8 aperture, "
        "shallow depth of field, soft bokeh background, natural daylight, "
        "sharp subject, photorealistic, high-end commercial photography. "
        "No text, no watermark, no logo, no distortion."
    )
    user_prompt = (
        f"Business data:\n{context}\n\n"
        "Generate exactly 10 DSLR photography prompts for these website sections in this order.\n"
        "Every prompt MUST end with this exact suffix:\n"
        f'"{dslr_suffix}"\n\n'
        "Sections:\n"
        "1. Hero image (16:9) — cinematic wide establishing shot, golden hour light, premium first impression\n"
        "2. About section (4:3) — authentic workplace or environment, warm trustworthy feel\n"
        "3. Service image 1 (4:3) — scene unmistakably shows the company's FIRST service, bokeh background\n"
        "4. Service image 2 (4:3) — scene unmistakably shows the SECOND service, different from image 3\n"
        "5. Service image 3 (4:3) — scene unmistakably shows the THIRD service, unique composition\n"
        "6. Service image 4 (4:3) — craftsmanship or quality detail close-up, sharp foreground bokeh background\n"
        "7. Gallery image 1 (4:3) — completed finished project result, wide view\n"
        "8. Gallery image 2 (4:3) — different project, different angle and composition from image 7\n"
        "9. Gallery image 3 (4:3) — finished result in real context, warm natural light\n"
        "10. CTA background (16:9) — atmospheric, slightly soft, suitable as page background with text overlay\n\n"
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

    # ── Step 1: Download company website photos in parallel ───────────────────
    company_image_urls = getattr(crawled, "company_image_urls", []) if crawled else []
    accepted_company: dict[int, bytes] = {}  # index → bytes (preserves order)
    if company_image_urls:
        print(f"[image_generator] Downloading {min(len(company_image_urls), 10)} company images in parallel...")
        urls_to_try = company_image_urls[:10]

        def _fetch_company(idx_url):
            idx, url = idx_url
            try:
                b = _download(url)
                if _is_quality_image(b):
                    print(f"[image_generator] Accepted company image {idx+1}: {url}")
                    return (idx, b)
                else:
                    print(f"[image_generator] Rejected low-quality company image {idx+1}")
            except Exception as e:
                print(f"[image_generator] Failed company image {idx+1}: {e}")
            return (idx, None)

        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = {ex.submit(_fetch_company, (i, u)): i for i, u in enumerate(urls_to_try)}
            for fut in as_completed(futures):
                idx, b = fut.result()
                if b is not None:
                    accepted_company[idx] = b

    # Assign accepted company images to slots in original order
    company_slots = 0
    for idx in sorted(accepted_company.keys()):
        slot = company_slots + 1
        result.images[f"image-{slot:02d}.jpg"] = accepted_company[idx]
        company_slots += 1

    # ── Step 2: Fill remaining slots with AI-generated images in parallel ──────
    remaining = 10 - company_slots
    if remaining > 0:
        prompts = _generate_prompts_with_claude(data, crawled) or \
                  _build_prompts(data.company_name, data.industry, data.region, data.style)

        # Build (prompt_idx, prompt, slot, dims, seed) for each needed AI image
        tasks = []
        ai_count = 0
        for i, prompt in enumerate(prompts, start=1):
            if ai_count >= remaining:
                break
            slot = company_slots + ai_count + 1
            dims = "width=1280&height=720" if i in (1, 10) else "width=1024&height=768"
            seed = base_seed + i
            tasks.append((i, prompt, slot, dims, seed))
            ai_count += 1

        print(f"[image_generator] Generating {len(tasks)} AI images via FLUX.1-schnell HF Space (free, 5 threads)...")

        def _fetch_ai(task):
            i, prompt, slot, dims, seed = task
            filename = f"image-{slot:02d}.jpg"
            w = int(dims.split("width=")[1].split("&")[0])
            h = int(dims.split("height=")[1])
            try:
                print(f"[image_generator] Requesting {filename} ({w}x{h}, seed={seed})...")
                b = _flux_space_generate(prompt, w, h, seed)
                print(f"[image_generator] ✓ {filename} ({len(b):,} bytes)")
                return (slot, filename, b)
            except Exception as e:
                print(f"[image_generator] ✗ {filename}: {e}")
                return (slot, filename, None)

        with ThreadPoolExecutor(max_workers=5) as ex:
            for slot, filename, b in ex.map(_fetch_ai, tasks):
                if b is not None:
                    result.images[filename] = b

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
            result.logo_bytes = _flux_space_generate(logo_prompt, 512, 512, base_seed)
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
