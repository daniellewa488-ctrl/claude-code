import re
import json
import time
from dataclasses import dataclass
import config

MODEL = "claude-haiku-4-5-20251001"

INDUSTRY_COLORS = {
    "garten": ("green", "#15803d", "#16a34a"),
    "landschaft": ("green", "#15803d", "#16a34a"),
    "bau": ("stone", "#57534e", "#78716c"),
    "restaurant": ("orange", "#c2410c", "#ea580c"),
    "bäckerei": ("amber", "#b45309", "#d97706"),
    "küche": ("orange", "#c2410c", "#ea580c"),
    "it": ("blue", "#1d4ed8", "#2563eb"),
    "tech": ("blue", "#1d4ed8", "#2563eb"),
    "arzt": ("teal", "#0f766e", "#0d9488"),
    "zahnarzt": ("teal", "#0f766e", "#0d9488"),
    "pflege": ("teal", "#0f766e", "#0d9488"),
    "beauty": ("rose", "#be123c", "#e11d48"),
    "friseur": ("pink", "#be185d", "#db2777"),
    "immobilien": ("slate", "#334155", "#475569"),
    "reinigung": ("cyan", "#0e7490", "#0891b2"),
}


def _get_colors(industry: str, style: str = "") -> tuple:
    text = (industry + " " + style).lower()
    for key, colors in INDUSTRY_COLORS.items():
        if key in text:
            return colors
    return ("blue", "#1d4ed8", "#2563eb")


def _parse_json_safe(raw: str) -> dict:
    """Try multiple strategies to extract valid JSON from response."""
    # Strategy 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: extract first {...} block
    try:
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            return json.loads(m.group(0))
    except json.JSONDecodeError:
        pass

    # Strategy 3: fix common issues (trailing commas, smart quotes)
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

    raise ValueError(f"Could not parse JSON from response: {raw[:200]}")


def _call_claude(system_prompt: str, user_prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    for attempt in range(5):
        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return message.content[0].text.strip()
        except anthropic.RateLimitError:
            wait = 10 * (attempt + 1)
            print(f"[html_generator] Claude rate limit, waiting {wait}s...")
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            if e.status_code in (529, 503):
                wait = 10 * (attempt + 1)
                print(f"[html_generator] Claude overloaded, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise

    raise Exception("Claude API failed after 5 retries")


def _generate_content(data, crawled: str) -> dict:
    system = "You are a copywriter. Return ONLY valid JSON, no explanation, no markdown."
    prompt = f"""Generate website content for this company. Return ONLY a JSON object with these exact keys:

Company: {data.company_name}
Industry: {data.industry}
Region: {data.region or 'Germany'}
Services: {data.services or 'infer from industry'}
Target audience: {data.target_audience or 'infer from industry'}
Style: {data.style or 'professional modern'}
Crawled website content: {crawled[:2000] if crawled else 'none'}

Return this JSON structure (all text in German):
{{
  "slogan": "a compelling one-line slogan",
  "about": "2-3 sentence about us text, mention region and experience",
  "services": [
    {{"name": "Service 1", "description": "one sentence description"}},
    {{"name": "Service 2", "description": "one sentence description"}},
    {{"name": "Service 3", "description": "one sentence description"}},
    {{"name": "Service 4", "description": "one sentence description"}},
    {{"name": "Service 5", "description": "one sentence description"}},
    {{"name": "Service 6", "description": "one sentence description"}}
  ],
  "testimonials": [
    {{"name": "Full Name", "role": "customer type", "text": "positive review 1-2 sentences"}},
    {{"name": "Full Name", "role": "customer type", "text": "positive review 1-2 sentences"}}
  ],
  "address": "realistic street address in {data.region or 'the region'}",
  "phone": "realistic german phone number",
  "email": "realistic email for the company"
}}"""

    for attempt in range(3):
        try:
            raw = _call_claude(system, prompt, max_tokens=1500, temperature=0)
            return _parse_json_safe(raw)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"[html_generator] JSON parse failed (attempt {attempt+1}): {e}")
            if attempt == 2:
                raise
    raise Exception("Failed to get valid JSON after 3 attempts")


def _build_service_cards(services: list) -> str:
    images = ["image-02.jpg", "image-03.jpg", "image-04.jpg",
              "image-05.jpg", "image-06.jpg", "image-09.jpg"]
    cards = []
    for i, svc in enumerate(services[:6]):
        img = images[i % len(images)]
        cards.append(f"""
        <div class="bg-white rounded-2xl shadow-lg overflow-hidden hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
          <img src="{img}" alt="{svc['name']}" class="w-full h-48 object-cover">
          <div class="p-6">
            <h3 class="text-xl font-bold mb-2 text-gray-800">{svc['name']}</h3>
            <p class="text-gray-500 text-sm leading-relaxed">{svc['description']}</p>
          </div>
        </div>""")
    return "\n".join(cards)


def _build_testimonial_cards(testimonials: list) -> str:
    cards = []
    for t in testimonials:
        cards.append(f"""
        <div class="bg-gray-50 rounded-2xl p-8 border border-gray-100">
          <p class="text-gray-600 italic mb-6 leading-relaxed">"{t['text']}"</p>
          <div>
            <p class="font-bold text-gray-800">{t['name']}</p>
            <p class="text-sm text-gray-400">{t['role']}</p>
          </div>
        </div>""")
    return "\n".join(cards)


def _build_index_html(data, content: dict, primary: str, primary_dark: str) -> str:
    service_cards = _build_service_cards(content.get("services", []))
    testimonial_cards = _build_testimonial_cards(content.get("testimonials", []))
    logo_img = '<img src="logo.png" alt="Logo" class="h-10 mr-3">' if data.logo_url else ""

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data.company_name}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Inter', sans-serif; }}
    .hero-section {{
      background: linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0.55)), url('image-01.jpg');
      background-size: cover;
      background-position: center;
      min-height: 100vh;
    }}
    .btn-primary {{ background-color: {primary}; }}
    .btn-primary:hover {{ background-color: {primary_dark}; }}
    .text-primary {{ color: {primary}; }}
    .bg-primary {{ background-color: {primary}; }}
    .border-primary {{ border-color: {primary}; }}
    @keyframes fadeInUp {{ from {{ opacity:0; transform:translateY(30px); }} to {{ opacity:1; transform:translateY(0); }} }}
    .animate-fade {{ animation: fadeInUp 0.8s ease forwards; }}
  </style>
</head>
<body class="bg-white text-gray-800">

  <!-- NAVIGATION -->
  <nav class="fixed top-0 w-full bg-white/95 backdrop-blur shadow-sm z-50">
    <div class="max-w-6xl mx-auto px-6 py-4 flex justify-between items-center">
      <div class="flex items-center">
        {logo_img}
        <span class="text-xl font-bold text-primary">{data.company_name}</span>
      </div>
      <div class="flex items-center space-x-6">
        <a href="#ueber-uns" class="text-gray-600 hover:text-primary font-medium transition-colors">Über uns</a>
        <a href="#leistungen" class="text-gray-600 hover:text-primary font-medium transition-colors">Leistungen</a>
        <a href="#galerie" class="text-gray-600 hover:text-primary font-medium transition-colors">Galerie</a>
        <a href="angebot.html" class="btn-primary text-white px-5 py-2 rounded-full font-semibold hover:opacity-90 transition-all">Kontakt</a>
      </div>
    </div>
  </nav>

  <!-- HERO -->
  <section class="hero-section flex items-center justify-center text-white">
    <div class="text-center px-6 animate-fade">
      <h1 class="text-5xl md:text-7xl font-black mb-6 leading-tight tracking-tight">{data.company_name}</h1>
      <p class="text-xl md:text-2xl mb-10 max-w-2xl mx-auto font-light opacity-90">{content.get('slogan', '')}</p>
      <a href="angebot.html" class="btn-primary text-white px-10 py-4 rounded-full text-lg font-bold hover:opacity-90 transition-all inline-block shadow-lg">
        Mehr erfahren &rarr;
      </a>
    </div>
  </section>

  <!-- ABOUT -->
  <section id="ueber-uns" class="py-24 px-6 bg-gray-50">
    <div class="max-w-4xl mx-auto text-center">
      <h2 class="text-4xl font-bold mb-4 text-gray-800">Über uns</h2>
      <div class="w-16 h-1 bg-primary mx-auto mb-8 rounded"></div>
      <p class="text-lg text-gray-600 leading-relaxed">{content.get('about', '')}</p>
      <a href="angebot.html" class="inline-block mt-8 border-2 border-primary text-primary px-8 py-3 rounded-full font-semibold hover:bg-primary hover:text-white transition-all">
        Mehr über uns
      </a>
    </div>
  </section>

  <!-- SERVICES -->
  <section id="leistungen" class="py-24 px-6 bg-white">
    <div class="max-w-6xl mx-auto">
      <div class="text-center mb-16">
        <h2 class="text-4xl font-bold text-gray-800 mb-4">Unsere Leistungen</h2>
        <div class="w-16 h-1 bg-primary mx-auto rounded"></div>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {service_cards}
      </div>
      <div class="text-center mt-12">
        <a href="angebot.html" class="btn-primary text-white px-10 py-4 rounded-full text-lg font-bold hover:opacity-90 transition-all inline-block">
          Jetzt anfragen
        </a>
      </div>
    </div>
  </section>

  <!-- GALLERY -->
  <section id="galerie" class="py-24 px-6 bg-gray-50">
    <div class="max-w-6xl mx-auto">
      <div class="text-center mb-16">
        <h2 class="text-4xl font-bold text-gray-800 mb-4">Galerie</h2>
        <div class="w-16 h-1 bg-primary mx-auto rounded"></div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <img src="image-07.jpg" alt="Projekt" class="w-full h-72 object-cover rounded-2xl shadow-md hover:shadow-xl transition-shadow">
        <img src="image-08.jpg" alt="Projekt" class="w-full h-72 object-cover rounded-2xl shadow-md hover:shadow-xl transition-shadow">
        <img src="image-09.jpg" alt="Projekt" class="w-full h-72 object-cover rounded-2xl shadow-md hover:shadow-xl transition-shadow">
        <img src="image-10.jpg" alt="Projekt" class="w-full h-72 object-cover rounded-2xl shadow-md hover:shadow-xl transition-shadow">
      </div>
    </div>
  </section>

  <!-- TESTIMONIALS -->
  <section class="py-24 px-6 bg-white">
    <div class="max-w-4xl mx-auto">
      <div class="text-center mb-16">
        <h2 class="text-4xl font-bold text-gray-800 mb-4">Was unsere Kunden sagen</h2>
        <div class="w-16 h-1 bg-primary mx-auto rounded"></div>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
        {testimonial_cards}
      </div>
    </div>
  </section>

  <!-- CTA BANNER -->
  <section class="py-20 px-6 bg-primary text-white text-center">
    <h2 class="text-4xl font-bold mb-4">Bereit für Ihr Projekt?</h2>
    <p class="text-xl mb-10 opacity-90 max-w-xl mx-auto">Kontaktieren Sie uns noch heute für ein kostenloses Erstgespräch.</p>
    <a href="angebot.html" class="bg-white px-10 py-4 rounded-full text-lg font-bold hover:bg-gray-100 transition-all inline-block" style="color:{primary}">
      Jetzt anfragen
    </a>
  </section>

  <!-- FOOTER -->
  <footer class="bg-gray-900 text-gray-400 py-12 px-6">
    <div class="max-w-6xl mx-auto text-center">
      <p class="text-xl font-bold text-white mb-2">{data.company_name}</p>
      <p class="mb-1">{content.get('address', '')}</p>
      <p class="mb-1">{content.get('phone', '')} &bull; {content.get('email', '')}</p>
      <p class="mt-6 text-sm text-gray-600">&copy; 2025 {data.company_name}. Alle Rechte vorbehalten.</p>
    </div>
  </footer>

</body>
</html>"""


def _build_angebot_html(data, content: dict, primary: str, primary_dark: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Website anfragen – Hannah's Webdesign</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap" rel="stylesheet">
  <style>body {{ font-family: 'Inter', sans-serif; }}</style>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen">

  <!-- NAV -->
  <nav class="bg-white shadow-sm px-6 py-4">
    <div class="max-w-4xl mx-auto flex justify-between items-center">
      <span class="text-lg font-bold text-gray-800">Hannah's Webdesign</span>
      <a href="index.html" class="text-gray-500 hover:text-gray-800 text-sm font-medium">&larr; Zurück zur Demo</a>
    </div>
  </nav>

  <!-- MAIN -->
  <main class="max-w-2xl mx-auto px-6 py-20 text-center">
    <div class="bg-white rounded-3xl shadow-xl p-12">
      <div class="text-5xl mb-6">&#127968;</div>
      <h1 class="text-4xl font-black text-gray-800 mb-4">Gefällt Ihnen diese Website?</h1>
      <p class="text-lg text-gray-500 mb-8 leading-relaxed">
        Wir haben diese Demo speziell für <strong>{data.company_name}</strong> erstellt —
        professionell, modern und auf Ihre Branche zugeschnitten.<br><br>
        Gerne erstellen wir Ihre komplette Website: responsive, SEO-optimiert und innerhalb weniger Tage live.
      </p>
      <a href="mailto:hallo@hannahs-webdesign.de?subject=Anfrage%20Website%20{data.company_name}"
         class="inline-block text-white text-xl font-bold px-12 py-5 rounded-full shadow-lg hover:opacity-90 transition-all mb-6"
         style="background-color:{primary}">
        Jetzt kostenlos anfragen
      </a>
      <p class="text-gray-400 text-sm">oder rufen Sie uns an: <strong>+49 30 123 456 789</strong></p>
      <p class="text-gray-400 text-sm mt-1">hallo@hannahs-webdesign.de</p>
    </div>
  </main>

  <footer class="text-center text-gray-400 text-sm py-6">
    &copy; 2025 Hannah's Webdesign
  </footer>

</body>
</html>"""


@dataclass
class GeneratedSite:
    index_html: str
    angebot_html: str
    styles_css: str
    outreach_email: str


def _generate_outreach_email(data, content: dict, primary: str) -> str:
    system = "Du bist ein erfahrener Vertriebstexter. Schreibe professionelle Akquise-E-Mails auf Deutsch."
    prompt = f"""Schreibe eine kurze Akquise-E-Mail von Hannah's Webdesign an {data.company_name}.

Kontext:
- Branche: {data.industry}
- Region: {data.region or 'Deutschland'}
- Demo-URL: {config.PREVIEW_BASE_URL}/{data.slug}/
- Slogan der Demo: {content.get('slogan', '')}

Format:
- Betreff: (erste Zeile)
- Ca. 120-150 Wörter
- Persönlich, professionell, auf die Branche eingehen
- Demo-Link erwähnen
- CTA: Termin oder Rückruf
- Unterschrift: Hannah Müller, Hannah's Webdesign, hallo@hannahs-webdesign.de"""

    return _call_claude(system, prompt, max_tokens=600)


def generate(data, crawled: str) -> GeneratedSite:
    _, primary, primary_dark = _get_colors(data.industry, data.style)

    print("[html_generator] Generating content via Claude...")
    content = _generate_content(data, crawled)

    print("[html_generator] Building HTML from template...")
    index_html = _build_index_html(data, content, primary, primary_dark)
    angebot_html = _build_angebot_html(data, content, primary, primary_dark)
    styles_css = "/* Styles are embedded via Tailwind CDN in HTML files */"

    print("[html_generator] Generating outreach email...")
    outreach_email = _generate_outreach_email(data, content, primary)

    return GeneratedSite(
        index_html=index_html,
        angebot_html=angebot_html,
        styles_css=styles_css,
        outreach_email=outreach_email,
    )
