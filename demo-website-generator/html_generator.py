import re
import json
import time
from dataclasses import dataclass
import config

MODEL = "claude-haiku-4-5-20251001"

INDUSTRY_COLORS = {
    "garten": ("#16a34a", "#15803d"),
    "landschaft": ("#16a34a", "#15803d"),
    "bau": ("#78716c", "#57534e"),
    "restaurant": ("#ea580c", "#c2410c"),
    "bäckerei": ("#d97706", "#b45309"),
    "küche": ("#ea580c", "#c2410c"),
    "it": ("#2563eb", "#1d4ed8"),
    "tech": ("#2563eb", "#1d4ed8"),
    "software": ("#2563eb", "#1d4ed8"),
    "arzt": ("#0d9488", "#0f766e"),
    "zahnarzt": ("#0d9488", "#0f766e"),
    "pflege": ("#0d9488", "#0f766e"),
    "beauty": ("#e11d48", "#be123c"),
    "friseur": ("#db2777", "#be185d"),
    "immobilien": ("#475569", "#334155"),
    "reinigung": ("#0891b2", "#0e7490"),
    "handwerk": ("#92400e", "#78350f"),
    "elektro": ("#1d4ed8", "#1e3a8a"),
    "maler": ("#7c3aed", "#6d28d9"),
    "sanitär": ("#0369a1", "#075985"),
}


def _get_colors(industry: str, style: str = "") -> tuple:
    text = (industry + " " + style).lower()
    for key, colors in INDUSTRY_COLORS.items():
        if key in text:
            return colors
    return ("#2563eb", "#1d4ed8")


def _get_initials(name: str) -> str:
    words = name.strip().split()
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return name[:2].upper()


def _choose_variant(industry: str, style: str) -> str:
    """Choose one of three distinct layout/feel variants based on industry and style."""
    text = (industry + " " + style).lower()
    elegant_keys = ["beauty", "spa", "wellness", "hotel", "café", "cafe", "friseur",
                    "hochzeit", "blumen", "mode", "schmuck", "kosmetik", "luxus",
                    "restaurant", "bäckerei", "konditorei", "massage"]
    bold_keys = ["it", "tech", "software", "bau", "handwerk", "elektro", "sanitär",
                 "reinigung", "auto", "logistik", "industrie", "sicherheit", "dach",
                 "garten", "landschaft", "maler", "gerüst", "transport", "lager"]
    for k in elegant_keys:
        if k in text:
            return "elegant"
    for k in bold_keys:
        if k in text:
            return "bold"
    return "classic"


def _parse_json_safe(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    try:
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            return json.loads(m.group(0))
    except json.JSONDecodeError:
        pass
    try:
        fixed = re.sub(r',\s*}', '}', raw)
        fixed = re.sub(r',\s*]', ']', fixed)
        fixed = fixed.replace('‘', "'").replace('’', "'")
        fixed = fixed.replace('“', '"').replace('”', '"')
        m = re.search(r'\{[\s\S]*\}', fixed)
        if m:
            return json.loads(m.group(0))
    except json.JSONDecodeError:
        pass
    raise ValueError(f"Could not parse JSON: {raw[:300]}")


def _call_claude(system_prompt: str, user_prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    for attempt in range(5):
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return msg.content[0].text.strip()
        except anthropic.RateLimitError:
            wait = 10 * (attempt + 1)
            print(f"[html_generator] Rate limit, waiting {wait}s...")
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            if e.status_code in (529, 503):
                wait = 10 * (attempt + 1)
                print(f"[html_generator] Overloaded, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise Exception("Claude API failed after 5 retries")


_JSON_SCHEMA = """{
  "meta_title": "Company – Hauptleistung | Stadt (max 60 Zeichen)",
  "meta_description": "SEO-Beschreibung mit lokalen Keywords (max 155 Zeichen)",
  "schema_type": "LocalBusiness",
  "slogan": "Starke H1-Überschrift für den Hero (8-12 Wörter)",
  "hero_subtitle": "Unterstützender Satz 12-18 Wörter",
  "about": "3-4 Sätze über das Unternehmen mit echten Fakten",
  "about_bullets": ["Stärke 1", "Stärke 2", "Stärke 3"],
  "years_experience": "Zahl als String z.B. 25",
  "stats": [
    {"number": "X+", "label": "Abgeschlossene Projekte"},
    {"number": "X+", "label": "Jahre Erfahrung"},
    {"number": "X+", "label": "Zufriedene Kunden"}
  ],
  "services": [
    {"name": "Name", "description": "Satz max 15 Wörter", "details": ["Detail 1", "Detail 2", "Detail 3"]},
    {"name": "Name", "description": "Satz max 15 Wörter", "details": ["Detail 1", "Detail 2", "Detail 3"]},
    {"name": "Name", "description": "Satz max 15 Wörter", "details": ["Detail 1", "Detail 2", "Detail 3"]},
    {"name": "Name", "description": "Satz max 15 Wörter", "details": ["Detail 1", "Detail 2", "Detail 3"]},
    {"name": "Name", "description": "Satz max 15 Wörter", "details": ["Detail 1", "Detail 2", "Detail 3"]},
    {"name": "Name", "description": "Satz max 15 Wörter", "details": ["Detail 1", "Detail 2", "Detail 3"]}
  ],
  "extra_sections": [
    {
      "title": "Abschnittstitel z.B. Unser Sortiment",
      "intro": "Einleitender Satz für diesen Abschnitt",
      "items": [
        {"name": "Produkt oder Leistungsname", "description": "kurze Beschreibung"}
      ]
    }
  ],
  "testimonials": [
    {"name": "Vollständiger Name", "role": "Kundentyp", "text": "1-2 Sätze Bewertung"},
    {"name": "Vollständiger Name", "role": "Kundentyp", "text": "1-2 Sätze Bewertung"},
    {"name": "Vollständiger Name", "role": "Kundentyp", "text": "1-2 Sätze Bewertung"}
  ],
  "address": "Straße + Hausnummer, PLZ Stadt",
  "phone": "+49 ...",
  "email": "..."
}"""


def _get_industry_content_rules(industry: str) -> str:
    text = industry.lower()
    if any(k in text for k in ["baumschule", "baum", "bäume", "pflanzen", "staude", "gehölz", "nursery"]):
        return (
            "INDUSTRY: Baumschule / Nursery. schema_type='GardenStore'.\n"
            "extra_sections MUST include 'Unser Sortiment' with relevant plant group items:\n"
            "Bäume, Sträucher, Heckenpflanzen, Obstgehölze, Rosen, Stauden, Solitärpflanzen,\n"
            "Formgehölze, Nadelgehölze, Laubgehölze, Kletterpflanzen, Containerpflanzen, Ballenware.\n"
            "Only include groups actually mentioned or strongly implied from the content."
        )
    elif any(k in text for k in ["galabau", "landschaft", "gartenbau", "außenanlage"]):
        return (
            "INDUSTRY: GaLaBau / Landscaping. schema_type='HomeAndConstructionBusiness'.\n"
            "extra_sections MUST include 'Leistungsübersicht' with relevant service items:\n"
            "Gartengestaltung, Gartenplanung, Pflasterarbeiten, Terrassenbau, Wege und Einfahrten,\n"
            "Natursteinarbeiten, Pflanzarbeiten, Beetgestaltung, Rasenanlage, Rasenpflege,\n"
            "Hecken- und Gehölzschnitt, Baumpflege, Teichbau, Bewässerungsanlagen,\n"
            "Gartenpflege, Objektpflege, Grabpflege, Winterdienst.\n"
            "Only include services relevant to this specific company."
        )
    elif any(k in text for k in ["florist", "blumen", "floristi"]):
        return (
            "INDUSTRY: Floristik / Florist. schema_type='Florist'.\n"
            "extra_sections MUST include 'Unser Blumenangebot' with items:\n"
            "Schnittblumen, Topfpflanzen, Hochzeitsfloristik, Trauerfloristik,\n"
            "Dekorationen, Florale Geschenke, Grabbepflanzung, Saisonpflanzen,\n"
            "Dekoartikel, Keramik und Schalen, Blumenerden und Dünger.\n"
            "Only include items relevant to this company."
        )
    elif any(k in text for k in ["garten", "gärtnerei"]):
        return (
            "INDUSTRY: Garten / Garden. schema_type='GardenStore'.\n"
            "extra_sections should reflect the actual garden business areas found."
        )
    elif any(k in text for k in ["restaurant", "gastro", "café", "küche", "gaststätte", "bistro"]):
        return (
            "INDUSTRY: Restaurant / Gastronomy. schema_type='Restaurant'.\n"
            "extra_sections should include cuisine specialties and occasion types."
        )
    elif any(k in text for k in ["bäcker", "bäckerei", "konditor", "backwaren"]):
        return (
            "INDUSTRY: Bäckerei / Bakery. schema_type='Bakery'.\n"
            "extra_sections should include bread varieties, confectionery and catering offer."
        )
    elif any(k in text for k in ["arzt", "zahnarzt", "praxis", "medizin", "therapie"]):
        return (
            "INDUSTRY: Medical / Healthcare. schema_type='MedicalClinic'.\n"
            "extra_sections should include treatment areas and patient information."
        )
    elif any(k in text for k in ["handwerk", "sanitär", "heizung", "elektro", "maler", "tischler", "schlosser"]):
        return (
            "INDUSTRY: Handwerk / Trades. schema_type='HomeAndConstructionBusiness'.\n"
            "extra_sections should include a detailed service breakdown for this trade."
        )
    elif any(k in text for k in ["immobilien", "makler", "vermieten"]):
        return (
            "INDUSTRY: Real Estate. schema_type='RealEstateAgent'.\n"
            "extra_sections should include property types and service areas."
        )
    else:
        return (
            "INDUSTRY: General Business. schema_type='LocalBusiness'.\n"
            "Add 1-2 extra_sections for the company's main product/service areas if distinct. "
            "Otherwise extra_sections = []."
        )


def _try_generate(system: str, prompt: str, max_tokens: int) -> dict:
    for attempt in range(3):
        try:
            raw = _call_claude(system, prompt, max_tokens=max_tokens, temperature=0)
            return _parse_json_safe(raw)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"[html_generator] JSON parse failed (attempt {attempt+1}): {e}")
            if attempt == 2:
                raise
    raise Exception("Failed to get valid JSON after 3 attempts")


def _generate_content_with_website(data, crawled) -> dict:
    """Path A: company has a website — deep analysis of real scraped content."""
    contact_rules = []
    if crawled.contact_phone:
        contact_rules.append(f"phone MUST be exactly: {crawled.contact_phone}")
    if crawled.contact_email:
        contact_rules.append(f"email MUST be exactly: {crawled.contact_email}")
    if crawled.contact_address:
        contact_rules.append(f"address MUST be exactly: {crawled.contact_address}")
    if not contact_rules:
        contact_rules.append("invent realistic contact details for the region")
    contact_block = "\n".join(f"- {r}" for r in contact_rules)
    industry_rules = _get_industry_content_rules(data.industry)

    system = (
        "You are an expert German web copywriter, SEO specialist and content strategist. "
        "You deeply analyse existing websites to extract real business information and create "
        "compelling, highly specific content — never generic. "
        "Return ONLY valid JSON — no explanation, no markdown fences."
    )
    prompt = (
        f"COMPANY: {data.company_name}\n"
        f"INDUSTRY: {data.industry}\n"
        f"REGION: {data.region or 'Deutschland'}\n\n"
        f"INDUSTRY CONTENT RULES (follow strictly):\n{industry_rules}\n\n"
        "TASK: Deeply analyse ALL scraped content and create rich, specific website content "
        "using the company's REAL information. Do not reduce complex businesses to generic phrases.\n\n"
        "CRITICAL RULES:\n"
        "1. Use ACTUAL service/product names from the scraped content — not invented generic ones\n"
        "2. Improve writing quality but preserve all real facts, numbers, history, specialties\n"
        "3. For 'services': extract the 6 most important real services/products this company offers\n"
        "4. For each service 'details': add 3 specific sub-points (what exactly is included)\n"
        "5. For 'extra_sections': follow INDUSTRY CONTENT RULES — create detailed industry-specific "
        "sections that reflect what this business ACTUALLY offers\n"
        "6. Contact details:\n"
        f"{contact_block}\n"
        "7. meta_title: company name + main service + city (max 60 chars, German)\n"
        "8. meta_description: compelling local SEO description with service + location keywords "
        "(max 155 chars, German)\n"
        "9. All text in professional German — specific, trustworthy, locally relevant\n"
        "10. Testimonials: 3 realistic German customer reviews matching the real services\n\n"
        "=== SCRAPED WEBSITE CONTENT ===\n"
        f"{crawled.full_text[:6000]}\n\n"
        "=== EMAIL DATA ===\n"
        f"Additional services: {data.services or 'see website'}\n"
        f"Target audience: {data.target_audience or 'infer from content'}\n"
        f"Style: {data.style or 'professional modern'}\n\n"
        f"Return ONLY this JSON:\n{_JSON_SCHEMA}"
    )
    return _try_generate(system, prompt, max_tokens=3500)


def _generate_content_without_website(data) -> dict:
    """Path B: no website — generate compelling content from available data (may be sparse)."""
    known_parts = []
    if data.company_name:
        known_parts.append(f"Company name: {data.company_name}")
    if data.industry:
        known_parts.append(f"Industry: {data.industry}")
    if data.region:
        known_parts.append(f"Region: {data.region}")
    if data.services:
        known_parts.append(f"Services: {data.services}")
    if data.target_audience:
        known_parts.append(f"Target audience: {data.target_audience}")
    if data.style:
        known_parts.append(f"Style: {data.style}")
    available = "\n".join(known_parts) if known_parts else "Infer everything from the company name."
    industry_rules = _get_industry_content_rules(data.industry)

    system = (
        "You are an expert German web copywriter and SEO specialist. "
        "Create authentic, highly specific website content — never generic placeholders. "
        "Return ONLY valid JSON — no explanation, no markdown fences."
    )
    prompt = (
        f"COMPANY: {data.company_name}\n"
        f"INDUSTRY: {data.industry}\n"
        f"REGION: {data.region or 'Deutschland'}\n\n"
        f"INDUSTRY CONTENT RULES (follow strictly):\n{industry_rules}\n\n"
        "TASK: Create compelling, authentic website content. "
        "Infer intelligently from available info. Content must feel specific and real.\n\n"
        "=== AVAILABLE INFORMATION ===\n"
        f"{available}\n\n"
        "RULES:\n"
        "- industry missing → infer precisely from company name\n"
        "- services missing → infer from industry, produce 6 highly specific relevant services\n"
        "- for each service 'details' → 3 specific sub-points showing competence\n"
        "- extra_sections → follow INDUSTRY CONTENT RULES strictly\n"
        "- region missing → omit location references in text\n"
        "- meta_title → company + main service + region (max 60 chars, German)\n"
        "- meta_description → compelling local SEO description (max 155 chars, German)\n"
        "- All text in professional German — specific, never generic\n"
        "- Complete all fields — never leave values empty\n\n"
        f"Return ONLY this JSON:\n{_JSON_SCHEMA}"
    )
    return _try_generate(system, prompt, max_tokens=3500)


def _generate_content(data, crawled) -> dict:
    if hasattr(crawled, "found") and crawled.found:
        return _generate_content_with_website(data, crawled)
    return _generate_content_without_website(data)


# ─── HTML building helpers ────────────────────────────────────────────────────

def _star_svg(color: str) -> str:
    return (
        f'<svg class="w-4 h-4" style="fill:{color}" viewBox="0 0 20 20">'
        '<path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462'
        "c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921"
        "-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838"
        "-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81"
        '.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>'
        '</svg>'
    )


def _build_stats_html(stats: list, variant: str = "classic") -> str:
    lbl_cls = "text-white/60" if variant in ("elegant", "bold") else "text-gray-400"
    bdr_cls = "border-r border-white/20" if variant in ("elegant", "bold") else "border-r border-gray-700"
    items = []
    for i, s in enumerate(stats[:3]):
        border = "" if i == len(stats[:3]) - 1 else bdr_cls
        items.append(f"""
      <div class="{border} px-4">
        <p class="font-display text-4xl md:text-5xl font-black text-white">{s['number']}</p>
        <p class="{lbl_cls} text-xs mt-2 uppercase tracking-widest">{s['label']}</p>
      </div>""")
    return "\n".join(items)


def _build_bullets_html(bullets: list, primary: str) -> str:
    items = []
    check = (
        f'<span class="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center mt-0.5" '
        f'style="background:{primary}22">'
        f'<svg class="w-3 h-3" fill="none" stroke="{primary}" stroke-width="3" viewBox="0 0 24 24">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg></span>'
    )
    for b in bullets[:3]:
        items.append(
            f'<li class="flex items-start gap-3">'
            f'{check}'
            f'<span class="text-gray-700 font-medium text-sm leading-relaxed">{b}</span>'
            f'</li>'
        )
    return "\n".join(items)


def _build_service_cards(services: list, primary: str) -> str:
    images = ["image-02.jpg", "image-03.jpg", "image-04.jpg",
              "image-05.jpg", "image-08.jpg", "image-09.jpg"]
    arrow = (
        '<svg class="w-4 h-4 transition-transform group-hover:translate-x-1" '
        'fill="none" stroke="currentColor" viewBox="0 0 24 24">'
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>'
        '</svg>'
    )
    cards = []
    for i, svc in enumerate(services[:6]):
        img = images[i % len(images)]
        details = svc.get("details", [])
        details_html = ""
        if details:
            details_html = (
                '<ul class="mt-3 pt-3 border-t border-gray-100 space-y-1">' +
                "".join(
                    f'<li class="flex items-center gap-2 text-xs text-gray-400">'
                    f'<span class="w-1.5 h-1.5 rounded-full flex-shrink-0" style="background:{primary}60"></span>'
                    f'{d}</li>'
                    for d in details[:3]
                ) +
                '</ul>'
            )
        cards.append(f"""        <div class="group bg-white rounded-2xl overflow-hidden shadow-md border border-gray-100 hover:-translate-y-1 hover:shadow-xl transition-all duration-300">
          <div class="aspect-video overflow-hidden">
            <img src="{img}" alt="{svc['name']}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500">
          </div>
          <div class="p-6">
            <h3 class="font-display text-xl font-bold text-gray-900 mb-2">{svc['name']}</h3>
            <p class="text-gray-500 text-sm leading-relaxed">{svc['description']}</p>
            {details_html}
            <a href="angebot.html" class="inline-flex items-center gap-1.5 text-sm font-semibold mt-5" style="color:{primary}">
              Mehr erfahren {arrow}
            </a>
          </div>
        </div>""")
    return "\n".join(cards)


def _build_testimonial_cards(testimonials: list, primary: str) -> str:
    five_stars = "".join(_star_svg(primary) for _ in range(5))
    quote_svg = (
        f'<svg class="w-9 h-9 mb-3 opacity-15" style="fill:{primary}" viewBox="0 0 32 32">'
        '<path d="M10 8C6.7 8 4 10.7 4 14v10h10V14H7c0-1.7 1.3-3 3-3V8z'
        'M28 8c-3.3 0-6 2.7-6 6v10h10V14h-7c0-1.7 1.3-3 3-3V8z"/></svg>'
    )
    cards = []
    for t in testimonials[:3]:
        initials = _get_initials(t.get("name", "KK"))
        cards.append(f"""        <div class="bg-white rounded-2xl p-8 shadow-sm border border-gray-100">
          <div class="flex gap-0.5 mb-5">{five_stars}</div>
          {quote_svg}
          <p class="text-gray-600 text-sm leading-relaxed mb-6 italic">"{t['text']}"</p>
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center text-white text-sm font-bold" style="background:{primary}">
              {initials}
            </div>
            <div>
              <p class="font-semibold text-gray-900 text-sm">{t['name']}</p>
              <p class="text-gray-400 text-xs mt-0.5">{t['role']}</p>
            </div>
          </div>
        </div>""")
    return "\n".join(cards)


def _build_extra_sections_html(extra_sections: list, primary: str) -> str:
    """Render industry-specific extra sections (assortment, full service list, etc.)."""
    if not extra_sections:
        return ""
    out = []
    bg_cycle = ["bg-gray-50", "bg-white"]
    for idx, section in enumerate(extra_sections[:3]):
        bg = bg_cycle[idx % 2]
        title = section.get("title", "")
        intro = section.get("intro", "")
        items = section.get("items", [])
        if not items:
            continue
        intro_html = (
            f'<p class="text-gray-500 text-lg mt-4 max-w-2xl mx-auto leading-relaxed">{intro}</p>'
            if intro else ""
        )
        items_html = ""
        for item in items[:16]:
            name = item.get("name", item) if isinstance(item, dict) else str(item)
            desc = item.get("description", "") if isinstance(item, dict) else ""
            desc_html = f'<p class="text-gray-400 text-xs mt-0.5">{desc}</p>' if desc else ""
            items_html += (
                f'<div class="flex items-start gap-3 bg-white rounded-xl border border-gray-100 '
                f'shadow-sm p-4 hover:shadow-md transition-shadow">'
                f'<span class="w-2 h-2 rounded-full flex-shrink-0 mt-1.5" style="background:{primary}"></span>'
                f'<div><p class="font-semibold text-gray-900 text-sm">{name}</p>'
                f'{desc_html}'
                f'</div></div>\n'
            )
        out.append(f"""
  <!-- ── {title.upper()} ── -->
  <section class="{bg} py-20 px-6">
    <div class="max-w-6xl mx-auto">
      <div class="text-center mb-12">
        <p class="label mb-4">Im Überblick</p>
        <h2 class="text-4xl md:text-5xl font-bold text-gray-900">{title}</h2>
        {intro_html}
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {items_html}
      </div>
    </div>
  </section>""")
    return "\n".join(out)


# ─── Page builders ────────────────────────────────────────────────────────────

def _build_index_html(data, content: dict, primary: str, primary_dark: str) -> str:
    # Show logo.png when we have a URL to download from OR when we're generating one
    has_logo = bool(data.logo_url) or bool(getattr(data, "generate_logo", False))

    # ── Design variant ────────────────────────────────────────────────────────
    variant = _choose_variant(data.industry, data.style)

    if variant == "bold":
        # Left-aligned hero, primary-coloured stats bar, strong typography
        hero_section_cls = "hero-bg flex flex-col justify-center text-white px-8 sm:px-20"
        hero_inner_cls = "max-w-3xl"
        hero_h1_cls = "a2 text-5xl md:text-7xl font-black leading-none tracking-tight mb-6"
        hero_slogan_cls = "a3 text-xl md:text-2xl font-light text-white/80 max-w-xl mb-4 leading-snug"
        hero_sub_cls = "a3 text-base font-light text-white/55 max-w-lg mb-12 leading-relaxed"
        hero_btn_cls = "a4 flex flex-col sm:flex-row gap-4"
        stats_open = f'<div style="background:{primary}" class="py-12 px-6">'
        about_img_cls = ""
        about_txt_cls = ""
    elif variant == "elegant":
        # Centered hero, gradient stats bar, image on right side of about
        hero_section_cls = "hero-bg flex flex-col items-center justify-center text-white text-center px-6"
        hero_inner_cls = "max-w-4xl mx-auto"
        hero_h1_cls = "a2 text-5xl md:text-7xl font-black leading-none tracking-tight mb-6"
        hero_slogan_cls = "a3 text-2xl md:text-3xl font-light text-white/80 max-w-2xl mx-auto mb-4 leading-snug"
        hero_sub_cls = "a3 text-base md:text-lg font-light text-white/55 max-w-xl mx-auto mb-12 leading-relaxed"
        hero_btn_cls = "a4 flex flex-col sm:flex-row gap-4 justify-center"
        stats_open = f'<div style="background:linear-gradient(135deg,{primary},{primary_dark})" class="py-12 px-6">'
        about_img_cls = "md:order-last"
        about_txt_cls = "md:order-first"
    else:  # classic
        hero_section_cls = "hero-bg flex flex-col items-center justify-center text-white text-center px-6"
        hero_inner_cls = "max-w-4xl mx-auto"
        hero_h1_cls = "a2 text-6xl md:text-8xl font-black leading-none tracking-tight mb-6"
        hero_slogan_cls = "a3 text-2xl md:text-3xl font-light text-white/80 max-w-2xl mx-auto mb-4 leading-snug"
        hero_sub_cls = "a3 text-base md:text-lg font-light text-white/55 max-w-xl mx-auto mb-12 leading-relaxed"
        hero_btn_cls = "a4 flex flex-col sm:flex-row gap-4 justify-center"
        stats_open = '<div class="bg-gray-950 py-12 px-6">'
        about_img_cls = ""
        about_txt_cls = ""

    # Pre-compute all dynamic values before entering the f-string
    if has_logo:
        # Try SVG first (crawled logos), fall back to PNG (AI-generated), then hide
        _logo_onerror_nav = (
            "if(this.src.endsWith('.svg')){this.src='logo.png'}else{this.style.display='none'}"
        )
        _logo_onerror_footer = (
            "if(this.src.endsWith('.svg')){this.src='logo.png'}else{this.style.display='none'}"
        )
        logo_nav = (
            f'<img src="logo.svg" alt="{data.company_name}" '
            f'class="h-10 w-auto object-contain" onerror="{_logo_onerror_nav}">'
        )
        logo_footer = (
            f'<img src="logo.svg" alt="{data.company_name}" '
            f'class="h-8 w-auto object-contain" onerror="{_logo_onerror_footer}">'
        )
    else:
        ini = _get_initials(data.company_name)
        logo_nav = (
            f'<div class="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm flex-shrink-0"'
            f' style="background:{primary}">{ini}</div>'
        )
        logo_footer = (
            f'<div class="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-xs flex-shrink-0"'
            f' style="background:{primary}">{ini}</div>'
        )

    slogan = content.get("slogan", data.company_name)
    hero_subtitle = content.get("hero_subtitle", "")
    about = content.get("about", "")
    years = content.get("years_experience", "10")
    region = data.region or "Deutschland"
    phone = content.get("phone", "")
    phone_link = re.sub(r"[^0-9+]", "", phone)
    email = content.get("email", "")
    address = content.get("address", "")

    meta_title = content.get("meta_title") or f"{data.company_name} – {slogan}"
    meta_desc = content.get("meta_description") or f"Professionelle {data.industry}-Leistungen in {region}. Kontaktieren Sie {data.company_name} für ein persönliches Angebot."
    schema_type = content.get("schema_type", "LocalBusiness")
    schema_json = json.dumps({
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": data.company_name,
        "description": meta_desc,
        "url": "",
        "telephone": phone,
        "email": email,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": address,
            "addressLocality": region,
            "addressCountry": "DE"
        }
    }, ensure_ascii=False, indent=2)

    stats_html = _build_stats_html(content.get("stats", [
        {"number": "100+", "label": "Projekte"},
        {"number": "10+", "label": "Jahre Erfahrung"},
        {"number": "100+", "label": "Kunden"},
    ]), variant=variant)
    bullets_html = _build_bullets_html(content.get("about_bullets", []), primary)
    service_cards = _build_service_cards(content.get("services", []), primary)
    extra_sections_html = _build_extra_sections_html(content.get("extra_sections", []), primary)
    testimonial_cards = _build_testimonial_cards(content.get("testimonials", []), primary)

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{meta_title}</title>
  <meta name="description" content="{meta_desc}">
  <script type="application/ld+json">{schema_json}</script>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;0,900;1,400&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{ font-family: 'Inter', system-ui, -apple-system, Arial, sans-serif; -webkit-font-smoothing: antialiased; color: #1f2937; }}
    h1, h2, h3, .font-display {{ font-family: 'Playfair Display', Georgia, 'Times New Roman', serif; }}
    /* Primary color utilities */
    .text-primary {{ color: {primary}; }}
    .bg-primary {{ background-color: {primary}; }}
    .btn-primary {{ background-color: {primary}; color: #fff; transition: background 0.2s, transform 0.2s, box-shadow 0.2s; }}
    .btn-primary:hover {{ background-color: {primary_dark}; transform: translateY(-2px); box-shadow: 0 12px 28px rgba(0,0,0,0.22); }}
    /* Hero */
    .hero-bg {{
      background: linear-gradient(135deg, rgba(0,0,0,0.68) 0%, rgba(0,0,0,0.38) 100%),
                  url('image-01.jpg') center / cover no-repeat;
      min-height: 100vh;
      position: relative;
    }}
    /* Nav — starts with subtle dark glass, turns white on scroll */
    #nav {{ background: rgba(0,0,0,0.35); backdrop-filter: blur(8px); transition: background 0.35s, box-shadow 0.35s; }}
    #nav.scrolled {{ background: rgba(255,255,255,0.97); backdrop-filter: blur(14px); box-shadow: 0 2px 24px rgba(0,0,0,0.08); }}
    /* Section label */
    .label {{ font-size: 0.68rem; letter-spacing: 0.2em; text-transform: uppercase; font-weight: 700; color: {primary}; }}
    /* Service / testimonial cards */
    .card {{ transition: transform 0.3s ease, box-shadow 0.3s ease; }}
    .card:hover {{ transform: translateY(-8px); box-shadow: 0 28px 52px rgba(0,0,0,0.11); }}
    /* Animations */
    @keyframes up {{ from {{ opacity:0; transform:translateY(32px); }} to {{ opacity:1; transform:translateY(0); }} }}
    .a1 {{ animation: up 0.7s ease 0.1s both; }}
    .a2 {{ animation: up 0.7s ease 0.3s both; }}
    .a3 {{ animation: up 0.7s ease 0.5s both; }}
    .a4 {{ animation: up 0.7s ease 0.7s both; }}
  </style>
</head>
<body class="bg-white">

  <!-- ── NAVIGATION ── -->
  <nav id="nav" class="fixed top-0 inset-x-0 z-50 py-4 px-6">
    <div class="max-w-7xl mx-auto flex items-center justify-between">
      <a href="index.html" class="flex items-center gap-3">
        {logo_nav}
        <span id="nav-brand" class="font-display text-xl font-bold text-white transition-colors duration-300">{data.company_name}</span>
      </a>
      <div class="hidden md:flex items-center gap-8">
        <a href="#ueber-uns" class="nav-lnk text-white/80 hover:text-white text-sm font-medium transition-colors">Über uns</a>
        <a href="#leistungen" class="nav-lnk text-white/80 hover:text-white text-sm font-medium transition-colors">Leistungen</a>
        <a href="#galerie" class="nav-lnk text-white/80 hover:text-white text-sm font-medium transition-colors">Galerie</a>
        <a href="#kontakt" class="nav-lnk text-white/80 hover:text-white text-sm font-medium transition-colors">Kontakt</a>
        <a href="angebot.html" class="btn-primary px-6 py-2.5 rounded-full text-sm font-semibold shadow-md">Anfragen</a>
      </div>
      <!-- Hamburger button (mobile only) -->
      <button id="menu-btn" class="md:hidden flex flex-col gap-1.5 p-2 ml-2" aria-label="Menü öffnen" aria-expanded="false">
        <span id="hb1" class="block w-6 h-0.5 bg-white transition-all duration-300 origin-center"></span>
        <span id="hb2" class="block w-6 h-0.5 bg-white transition-all duration-300"></span>
        <span id="hb3" class="block w-6 h-0.5 bg-white transition-all duration-300 origin-center"></span>
      </button>
    </div>
    <!-- Mobile dropdown menu -->
    <div id="mobile-menu" class="md:hidden hidden bg-white rounded-2xl shadow-xl mt-3 mx-0 px-6 py-5 space-y-1">
      <a href="#ueber-uns" class="mobile-nav-lnk block text-gray-700 hover:text-gray-900 font-medium py-2.5 border-b border-gray-100">Über uns</a>
      <a href="#leistungen" class="mobile-nav-lnk block text-gray-700 hover:text-gray-900 font-medium py-2.5 border-b border-gray-100">Leistungen</a>
      <a href="#galerie" class="mobile-nav-lnk block text-gray-700 hover:text-gray-900 font-medium py-2.5 border-b border-gray-100">Galerie</a>
      <a href="#kontakt" class="mobile-nav-lnk block text-gray-700 hover:text-gray-900 font-medium py-2.5">Kontakt</a>
      <a href="angebot.html" class="btn-primary block text-center px-6 py-3 rounded-full text-sm font-semibold shadow-md mt-3">Anfragen</a>
    </div>
  </nav>

  <!-- ── HERO ── -->
  <section class="{hero_section_cls}">
    <div class="{hero_inner_cls}">
      <p class="a1 label text-white/50 mb-5">{data.industry} &bull; {region}</p>
      <h1 class="{hero_h1_cls}">{data.company_name}</h1>
      <p class="{hero_slogan_cls}">{slogan}</p>
      <p class="{hero_sub_cls}">{hero_subtitle}</p>
      <div class="{hero_btn_cls}">
        <a href="angebot.html" class="btn-primary px-11 py-4 rounded-full text-base font-semibold shadow-2xl">
          Kostenlos anfragen
        </a>
        <a href="#leistungen" class="border border-white/30 bg-white/10 backdrop-blur-sm text-white px-11 py-4 rounded-full text-base font-semibold hover:bg-white/20 transition-all">
          Unsere Leistungen
        </a>
      </div>
    </div>
    <div class="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
      <svg class="w-5 h-5 text-white/35" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
      </svg>
    </div>
  </section>

  <!-- ── STATS BAR ── -->
  {stats_open}
    <div class="max-w-3xl mx-auto grid grid-cols-3 gap-4 text-center">
      {stats_html}
    </div>
  </div>

  <!-- ── ABOUT ── -->
  <section id="ueber-uns" class="py-28 px-6 bg-white">
    <div class="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-16 items-center">
      <!-- Image column -->
      <div class="relative {about_img_cls}">
        <img src="image-06.jpg" alt="Über {data.company_name}" class="w-full h-[300px] md:h-[440px] object-cover rounded-3xl shadow-2xl">
        <div class="absolute -bottom-5 -right-5 text-white rounded-2xl px-8 py-5 shadow-xl" style="background:{primary}">
          <p class="font-display text-5xl font-black leading-none">{years}+</p>
          <p class="text-xs font-semibold mt-2 uppercase tracking-widest opacity-80">Jahre Erfahrung</p>
        </div>
      </div>
      <!-- Text column -->
      <div class="{about_txt_cls}">
        <p class="label mb-4">Über uns</p>
        <h2 class="text-4xl md:text-5xl font-bold text-gray-900 leading-tight mb-6">
          Ihre Experten<br>in {region}
        </h2>
        <p class="text-gray-500 text-lg leading-relaxed mb-8">{about}</p>
        <ul class="space-y-3.5 mb-10">
          {bullets_html}
        </ul>
        <a href="angebot.html" class="btn-primary inline-block px-9 py-3.5 rounded-full text-sm font-semibold">
          Kontakt aufnehmen &rarr;
        </a>
      </div>
    </div>
  </section>

  <!-- ── SERVICES ── -->
  <section id="leistungen" class="py-28 px-6 bg-gray-50">
    <div class="max-w-6xl mx-auto">
      <div class="text-center mb-16">
        <p class="label mb-4">Was wir anbieten</p>
        <h2 class="text-4xl md:text-5xl font-bold text-gray-900">Unsere Leistungen</h2>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
{service_cards}
      </div>
      <div class="text-center mt-14">
        <a href="angebot.html" class="btn-primary inline-block px-11 py-4 rounded-full text-base font-semibold shadow-lg">
          Alle Leistungen anfragen
        </a>
      </div>
    </div>
  </section>

  {extra_sections_html}

  <!-- ── GALLERY ── -->
  <section id="galerie" class="py-28 px-6 bg-white">
    <div class="max-w-6xl mx-auto">
      <div class="text-center mb-16">
        <p class="label mb-4">Unsere Arbeit</p>
        <h2 class="text-4xl md:text-5xl font-bold text-gray-900">Einblicke in unsere Projekte</h2>
      </div>
      <!-- Uniform gallery grid: 2 columns on mobile, 3 on desktop, 16:9 aspect ratio -->
      <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div class="aspect-video overflow-hidden rounded-2xl shadow-sm hover:shadow-md hover:scale-[1.02] transition-all duration-300"><img src="image-07.jpg" alt="Projekt" class="w-full h-full object-cover"></div>
        <div class="aspect-video overflow-hidden rounded-2xl shadow-sm hover:shadow-md hover:scale-[1.02] transition-all duration-300"><img src="image-08.jpg" alt="Projekt" class="w-full h-full object-cover"></div>
        <div class="aspect-video overflow-hidden rounded-2xl shadow-sm hover:shadow-md hover:scale-[1.02] transition-all duration-300 hidden md:block"><img src="image-09.jpg" alt="Projekt" class="w-full h-full object-cover"></div>
        <div class="aspect-video overflow-hidden rounded-2xl shadow-sm hover:shadow-md hover:scale-[1.02] transition-all duration-300"><img src="image-05.jpg" alt="Projekt" class="w-full h-full object-cover"></div>
        <div class="aspect-video overflow-hidden rounded-2xl shadow-sm hover:shadow-md hover:scale-[1.02] transition-all duration-300"><img src="image-10.jpg" alt="Projekt" class="w-full h-full object-cover"></div>
        <div class="aspect-video overflow-hidden rounded-2xl shadow-sm hover:shadow-md hover:scale-[1.02] transition-all duration-300 hidden md:block"><img src="image-03.jpg" alt="Projekt" class="w-full h-full object-cover"></div>
      </div>
    </div>
  </section>

  <!-- ── TESTIMONIALS ── -->
  <section class="py-28 px-6 bg-gray-50">
    <div class="max-w-6xl mx-auto">
      <div class="text-center mb-16">
        <p class="label mb-4">Kundenstimmen</p>
        <h2 class="text-4xl md:text-5xl font-bold text-gray-900">Was unsere Kunden sagen</h2>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
{testimonial_cards}
      </div>
    </div>
  </section>

  <!-- ── CTA BANNER ── -->
  <section class="py-24 px-6 text-center text-white relative overflow-hidden" style="background:{primary}">
    <div class="absolute inset-0" style="background:url('image-01.jpg') center/cover;opacity:0.07;filter:grayscale(100%)"></div>
    <div class="relative max-w-2xl mx-auto">
      <p class="text-xs uppercase tracking-widest text-white/50 font-semibold mb-6">Kostenloses Erstgespräch</p>
      <h2 class="text-5xl font-black mb-6 leading-tight">Bereit für Ihr Projekt?</h2>
      <p class="text-lg opacity-75 leading-relaxed mb-10 max-w-lg mx-auto">
        Kontaktieren Sie uns — wir beraten Sie gerne unverbindlich und erstellen ein individuelles Angebot.
      </p>
      <a href="angebot.html" class="bg-white inline-block px-12 py-5 rounded-full text-base font-bold hover:bg-gray-100 transition-all shadow-2xl" style="color:{primary}">
        Jetzt kostenlos anfragen
      </a>
    </div>
  </section>

  <!-- ── FOOTER ── -->
  <footer id="kontakt" class="bg-gray-950 text-gray-400 pt-16 pb-8 px-6">
    <div class="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-10 pb-12 border-b border-gray-800/60">
      <!-- Brand -->
      <div class="md:col-span-2">
        <div class="flex items-center gap-3 mb-4">
          {logo_footer}
          <span class="font-display text-lg font-bold text-white">{data.company_name}</span>
        </div>
        <p class="text-sm text-gray-500 leading-relaxed max-w-xs mb-6">{slogan}</p>
        <a href="angebot.html" class="btn-primary inline-block text-xs px-5 py-2.5 rounded-full font-semibold">
          Website anfragen
        </a>
      </div>
      <!-- Links -->
      <div>
        <h4 class="text-white font-semibold text-sm mb-5">Navigation</h4>
        <ul class="space-y-3 text-sm">
          <li><a href="#ueber-uns" class="hover:text-white transition-colors">Über uns</a></li>
          <li><a href="#leistungen" class="hover:text-white transition-colors">Leistungen</a></li>
          <li><a href="#galerie" class="hover:text-white transition-colors">Galerie</a></li>
          <li><a href="angebot.html" class="hover:text-white transition-colors">Website anfragen</a></li>
          <li><a href="impressum.html" class="hover:text-white transition-colors">Impressum</a></li>
        </ul>
      </div>
      <!-- Contact -->
      <div>
        <h4 class="text-white font-semibold text-sm mb-5">Kontakt</h4>
        <ul class="space-y-3 text-sm">
          <li class="text-gray-500 leading-relaxed">{address}</li>
          <li><a href="tel:{phone_link}" class="hover:text-white transition-colors">{phone}</a></li>
          <li><a href="mailto:{email}" class="hover:text-white transition-colors">{email}</a></li>
        </ul>
      </div>
    </div>
    <div class="max-w-6xl mx-auto pt-8 flex flex-col md:flex-row justify-between items-center gap-3 text-xs text-gray-600">
      <p>&copy; 2025 {data.company_name}. Alle Rechte vorbehalten.</p>
      <p>Demo erstellt von <a href="angebot.html" class="text-gray-500 hover:text-white transition-colors">Hannah&apos;s Webdesign</a></p>
    </div>
  </footer>

  <!-- Nav scroll behaviour + hamburger toggle -->
  <script>
    (function () {{
      var nav = document.getElementById('nav');
      var brand = document.getElementById('nav-brand');
      var links = document.querySelectorAll('.nav-lnk');
      var menuBtn = document.getElementById('menu-btn');
      var mobileMenu = document.getElementById('mobile-menu');
      var hb1 = document.getElementById('hb1');
      var hb2 = document.getElementById('hb2');
      var hb3 = document.getElementById('hb3');
      var isOpen = false;

      function update() {{
        var scrolled = window.scrollY > 70;
        nav.classList.toggle('scrolled', scrolled);
        brand.style.color = scrolled ? '#111827' : '#ffffff';
        links.forEach(function (l) {{ l.style.color = scrolled ? '#4b5563' : 'rgba(255,255,255,0.80)'; }});
        if (!isOpen) {{
          var c = scrolled ? '#111827' : '#ffffff';
          hb1.style.background = c; hb2.style.background = c; hb3.style.background = c;
        }}
      }}

      menuBtn.addEventListener('click', function () {{
        isOpen = !isOpen;
        mobileMenu.classList.toggle('hidden', !isOpen);
        menuBtn.setAttribute('aria-expanded', isOpen);
        if (isOpen) {{
          hb1.style.transform = 'rotate(45deg) translate(4px, 4px)';
          hb2.style.opacity = '0';
          hb3.style.transform = 'rotate(-45deg) translate(4px, -4px)';
          hb1.style.background = '#111827'; hb2.style.background = '#111827'; hb3.style.background = '#111827';
        }} else {{
          hb1.style.transform = ''; hb2.style.opacity = '1'; hb3.style.transform = '';
          update();
        }}
      }});

      document.querySelectorAll('.mobile-nav-lnk').forEach(function (l) {{
        l.addEventListener('click', function () {{
          isOpen = false;
          mobileMenu.classList.add('hidden');
          menuBtn.setAttribute('aria-expanded', 'false');
          hb1.style.transform = ''; hb2.style.opacity = '1'; hb3.style.transform = '';
          update();
        }});
      }});

      window.addEventListener('scroll', update, {{ passive: true }});
    }})();
  </script>
</body>
</html>"""


def _build_angebot_html(data, content: dict, primary: str, primary_dark: str) -> str:
    slogan = content.get("slogan", "")
    features = [
        "Individuelles professionelles Design",
        "Mobile-optimiert & blitzschnell",
        "SEO-Grundoptimierung inklusive",
        "Kontaktformular & Google Maps",
        "Lieferung innerhalb weniger Tage",
        "Support & Nachbetreuung inklusive",
    ]
    check = (
        f'<svg class="w-5 h-5 flex-shrink-0 mt-0.5" style="color:{primary}" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>'
    )
    feature_items = "\n".join(
        f'<li class="flex items-start gap-3 text-gray-700 text-sm font-medium">{check}<span>{f}</span></li>'
        for f in features
    )

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ihre Website – Hannah's Webdesign</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Inter', system-ui, -apple-system, Arial, sans-serif; -webkit-font-smoothing: antialiased; }}
    h1, h2 {{ font-family: 'Playfair Display', Georgia, 'Times New Roman', serif; }}
    .btn {{ background: {primary}; color: #fff; transition: background 0.2s, transform 0.2s; }}
    .btn:hover {{ background: {primary_dark}; transform: translateY(-2px); }}
    input:focus, textarea:focus {{ outline: none; border-color: {primary}; box-shadow: 0 0 0 3px {primary}33; }}
  </style>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen">

  <!-- Top bar -->
  <div class="text-white text-center text-xs py-2.5 font-semibold tracking-wide" style="background:{primary}">
    Diese Demo wurde exklusiv für {data.company_name} erstellt
  </div>

  <!-- Nav -->
  <header class="bg-white border-b border-gray-100 px-6 py-4">
    <div class="max-w-4xl mx-auto flex justify-between items-center">
      <span class="font-display text-lg font-bold text-gray-900">Hannah's Webdesign</span>
      <a href="index.html" class="text-gray-500 hover:text-gray-800 text-sm font-medium transition-colors">
        &larr; Demo ansehen
      </a>
    </div>
  </header>

  <!-- Hero -->
  <main class="max-w-3xl mx-auto px-6 py-20">
    <div class="text-center mb-14">
      <div class="inline-flex items-center justify-center w-20 h-20 rounded-2xl mb-8 shadow-lg text-4xl" style="background:{primary}22">&#127942;</div>
      <h1 class="text-4xl md:text-5xl font-black text-gray-900 leading-tight mb-5">
        {data.company_name} verdient<br>eine Top-Website
      </h1>
      <p class="text-lg text-gray-500 max-w-xl mx-auto leading-relaxed">
        Professionell, modern und auf Ihre Branche zugeschnitten — fertig in wenigen Tagen.
      </p>
    </div>

    <!-- Preview hint -->
    <div class="rounded-2xl overflow-hidden shadow-xl mb-12 border border-gray-100">
      <img src="image-01.jpg" alt="Demo Preview" class="w-full h-52 object-cover">
      <div class="bg-white px-8 py-5 flex items-center justify-between">
        <div>
          <p class="font-bold text-gray-900 text-sm">{data.company_name}</p>
          <p class="text-gray-400 text-xs mt-0.5">{slogan}</p>
        </div>
        <span class="text-xs font-semibold px-3 py-1.5 rounded-full text-white" style="background:{primary}">Demo aktiv</span>
      </div>
    </div>

    <!-- Features -->
    <div class="bg-white rounded-3xl shadow-sm border border-gray-100 p-10 mb-10">
      <h2 class="text-2xl font-bold text-gray-900 mb-7">Was Sie bekommen</h2>
      <ul class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {feature_items}
      </ul>
    </div>

    <!-- Price hint -->
    <div class="text-center bg-white rounded-2xl shadow-sm border border-gray-100 p-8 mb-10">
      <p class="text-gray-400 text-xs uppercase tracking-widest font-semibold mb-3">Ihr Investment</p>
      <p class="font-display text-5xl font-black text-gray-900 mb-2">ab 599 €</p>
      <p class="text-gray-400 text-sm">Einmalig &bull; Keine versteckten Kosten &bull; Zahlbar nach Fertigstellung</p>
    </div>

    <!-- CTA Contact Form -->
    <div class="bg-white rounded-3xl shadow-sm border border-gray-100 p-10">
      <h2 class="text-2xl font-bold text-gray-900 mb-7 text-center">Jetzt kostenlos anfragen</h2>
      <form action="https://formsubmit.co/hallo@hannahs-webdesign.de" method="POST" class="space-y-5">
        <input type="hidden" name="_subject" value="Website-Anfrage: {data.company_name}">
        <input type="hidden" name="_captcha" value="false">
        <input type="hidden" name="_next" value="https://www.hannahs-webdesign.de/danke/">
        <div>
          <label class="block text-sm font-semibold text-gray-700 mb-2" for="f-name">Ihr Name *</label>
          <input id="f-name" type="text" name="name" required placeholder="Max Mustermann"
            class="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm transition-all">
        </div>
        <div>
          <label class="block text-sm font-semibold text-gray-700 mb-2" for="f-email">E-Mail-Adresse *</label>
          <input id="f-email" type="email" name="email" required placeholder="max@mustermann.de"
            class="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm transition-all">
        </div>
        <div>
          <label class="block text-sm font-semibold text-gray-700 mb-2" for="f-msg">Nachricht</label>
          <textarea id="f-msg" name="message" rows="4" placeholder="Erzählen Sie uns von Ihrem Projekt..."
            class="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm transition-all resize-none"></textarea>
        </div>
        <button type="submit" class="btn w-full py-4 rounded-full text-base font-bold shadow-xl">
          Anfrage absenden
        </button>
      </form>
      <p class="text-center text-gray-400 text-sm mt-5">
        Oder direkt: <a href="mailto:hallo@hannahs-webdesign.de" class="underline hover:text-gray-600">hallo@hannahs-webdesign.de</a>
      </p>
    </div>
  </main>

  <footer class="text-center text-gray-400 text-xs py-8 border-t border-gray-100">
    &copy; 2025 Hannah's Webdesign &bull; Professionelle Websites für Ihr Unternehmen
  </footer>

</body>
</html>"""


def _build_impressum_html(data, content: dict, primary: str) -> str:
    company = data.company_name or "Ihr Unternehmen"
    address = content.get("address", "")
    phone = content.get("phone", "")
    email = content.get("email", "")
    phone_link = re.sub(r"[^0-9+]", "", phone)
    phone_html = (
        f'Telefon: <a href="tel:{phone_link}" class="text-blue-600 hover:underline">{phone}</a><br>'
        if phone else ""
    )
    email_html = (
        f'E-Mail: <a href="mailto:{email}" class="text-blue-600 hover:underline">{email}</a>'
        if email else ""
    )
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Impressum – {company}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Inter', system-ui, -apple-system, Arial, sans-serif; -webkit-font-smoothing: antialiased; }}
    h1, h2 {{ font-family: 'Playfair Display', Georgia, serif; }}
  </style>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen">
  <div class="text-white text-center text-xs py-2.5 font-semibold tracking-wide" style="background:{primary}">
    Demo erstellt von Hannah's Webdesign
  </div>
  <header class="bg-white border-b border-gray-100 px-6 py-4">
    <div class="max-w-4xl mx-auto flex justify-between items-center">
      <span class="font-display text-lg font-bold text-gray-900">{company}</span>
      <a href="index.html" class="text-gray-500 hover:text-gray-800 text-sm font-medium transition-colors">&larr; Zur Website</a>
    </div>
  </header>
  <main class="max-w-2xl mx-auto px-6 py-16">
    <h1 class="text-4xl font-bold text-gray-900 mb-10">Impressum</h1>
    <section class="mb-8">
      <h2 class="text-lg font-bold text-gray-900 mb-3">Angaben gemäß § 5 TMG</h2>
      <p class="text-gray-700 leading-relaxed">{company}<br>{address}</p>
    </section>
    <section class="mb-8">
      <h2 class="text-lg font-bold text-gray-900 mb-3">Kontakt</h2>
      <p class="text-gray-700 leading-relaxed">{phone_html}{email_html}</p>
    </section>
    <section class="mb-8">
      <h2 class="text-lg font-bold text-gray-900 mb-3">Haftungsausschluss</h2>
      <p class="text-gray-600 text-sm leading-relaxed">
        Die Inhalte dieser Demo-Website wurden mit größtmöglicher Sorgfalt erstellt.
        Für die Richtigkeit, Vollständigkeit und Aktualität der Inhalte können wir jedoch keine Gewähr übernehmen.
        Diese Seite ist eine Demo, erstellt von Hannah's Webdesign.
      </p>
    </section>
    <section class="mb-8">
      <h2 class="text-lg font-bold text-gray-900 mb-3">Urheberrecht</h2>
      <p class="text-gray-600 text-sm leading-relaxed">
        Die durch die Seitenbetreiber erstellten Inhalte und Werke auf diesen Seiten unterliegen dem deutschen Urheberrecht.
        Die Vervielfältigung, Bearbeitung, Verbreitung und jede Art der Verwertung außerhalb der Grenzen des Urheberrechtes
        bedürfen der schriftlichen Zustimmung des jeweiligen Autors bzw. Erstellers.
      </p>
    </section>
    <div class="mt-12 pt-8 border-t border-gray-200 text-center">
      <a href="index.html" class="inline-block px-8 py-3 rounded-full text-sm font-semibold text-white" style="background:{primary}">
        Zurück zur Startseite
      </a>
    </div>
  </main>
  <footer class="text-center text-gray-400 text-xs py-8 border-t border-gray-100">
    &copy; 2025 {company} &bull;
    <a href="angebot.html" class="hover:text-gray-600">Demo von Hannah's Webdesign</a>
  </footer>
</body>
</html>"""


# ─── Main dataclass + entry point ────────────────────────────────────────────

@dataclass
class GeneratedSite:
    index_html: str
    angebot_html: str
    impressum_html: str
    styles_css: str
    outreach_email: str


def _generate_outreach_email(data, content: dict, primary: str, has_website: bool) -> str:
    if has_website:
        context = (
            "Hannah's Webdesign hat Ihre bestehende Website analysiert und eine professionellere "
            "Neugestaltung als kostenlose Demo erstellt — mit modernem Design und besserer Struktur."
        )
    else:
        context = (
            "Hannah's Webdesign hat eine kostenlose Demo-Website speziell für Ihr Unternehmen erstellt — "
            "professionell gestaltet, obwohl Sie noch keine eigene Website haben."
        )

    system = "Du bist ein erfahrener Vertriebstexter. Schreibe präzise Akquise-E-Mails auf Deutsch."
    prompt = (
        f"Schreibe eine kurze, professionelle Akquise-E-Mail von Hannah's Webdesign an {data.company_name}.\n\n"
        f"Kontext: {context}\n\n"
        "Details:\n"
        f"- Branche: {data.industry}\n"
        f"- Region: {data.region or 'Deutschland'}\n"
        f"- Demo-URL: {config.PREVIEW_BASE_URL}/{data.slug}/\n"
        f"- Slogan der Demo: {content.get('slogan', '')}\n\n"
        "Anforderungen:\n"
        "- Erste Zeile: Betreff (mit 'Betreff: ' Prefix)\n"
        "- 120-150 Wörter\n"
        "- Persönlich, branchenspezifisch, nicht generisch\n"
        "- Demo-Link klar einbauen\n"
        "- CTA: Termin oder Rückruf\n"
        "- Unterschrift: Hannah Müller, Hannah's Webdesign, hallo@hannahs-webdesign.de"
    )
    return _call_claude(system, prompt, max_tokens=600)


def generate(data, crawled) -> GeneratedSite:
    # Safety fallbacks — parser should fill these, but guard against edge cases
    if not data.company_name:
        data.company_name = "Ihr Unternehmen"
    if not data.industry:
        data.industry = "professionelles Unternehmen"

    primary, primary_dark = _get_colors(data.industry, data.style)
    has_website = hasattr(crawled, "found") and crawled.found

    if has_website:
        print("[html_generator] Path A: generating content from existing website via Claude...")
    else:
        print("[html_generator] Path B: generating content from email data via Claude...")

    content = _generate_content(data, crawled)

    print("[html_generator] Building HTML templates...")
    index_html = _build_index_html(data, content, primary, primary_dark)
    angebot_html = _build_angebot_html(data, content, primary, primary_dark)
    impressum_html = _build_impressum_html(data, content, primary)
    styles_css = "/* Styles embedded via Tailwind CDN */"

    print("[html_generator] Generating outreach email...")
    outreach_email = _generate_outreach_email(data, content, primary, has_website)

    return GeneratedSite(
        index_html=index_html,
        angebot_html=angebot_html,
        impressum_html=impressum_html,
        styles_css=styles_css,
        outreach_email=outreach_email,
    )
