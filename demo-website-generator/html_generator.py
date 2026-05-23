import re
import requests
from dataclasses import dataclass
import config

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"


@dataclass
class GeneratedSite:
    index_html: str
    angebot_html: str
    styles_css: str
    outreach_email: str


def _call_groq(system_prompt: str, user_prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 8000,
        "temperature": 0.7,
    }
    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    # Strip any accidental markdown fences
    content = re.sub(r"^```[a-z]*\n?", "", content.strip())
    content = re.sub(r"\n?```$", "", content.strip())
    return content.strip()


def _context_block(data, crawled: str) -> str:
    return f"""
Unternehmensname: {data.company_name}
Branche: {data.industry}
Region: {data.region}
Leistungen: {data.services}
Zielgruppe: {data.target_audience}
Stil/Design: {data.style}
Vorhandene Website gecrawlt: {crawled[:3000] if crawled else 'Keine Website vorhanden'}
""".strip()


def generate(data, crawled: str) -> GeneratedSite:
    ctx = _context_block(data, crawled)
    code_system = (
        "Du bist ein professioneller Webentwickler. "
        "Gib NUR validen Code aus – keine Markdown-Fences, keine Erklärungen, kein Text davor oder danach."
    )

    # --- index.html ---
    index_prompt = f"""
Erstelle eine vollständige, professionelle und moderne index.html für folgendes Unternehmen:

{ctx}

Anforderungen:
- Vollständige HTML5-Seite mit <head> (charset, viewport, title, link zu styles.css, Google Fonts)
- Navigationsleiste mit den Links: Startseite, Über uns, Leistungen, Galerie, Kontakt
  WICHTIG: ALLE Navigationslinks müssen zu angebot.html verlinken (href="angebot.html") – keine Anker-Links (#)
- Hero-Bereich mit großem Hintergrundbild (image-01.jpg), Firmennamen als H1, Slogan, großer CTA-Button "Mehr erfahren" → angebot.html
- Über-uns-Bereich mit Text passend zur Branche und Region, CTA-Button → angebot.html
- Leistungen-Bereich mit 4-6 Karten, jede mit Bild (image-02.jpg bis image-06.jpg), CTA-Button unter dem Bereich → angebot.html
- Galerie-Bereich mit image-07.jpg und image-08.jpg
- Testimonials-Bereich mit 2 fiktiven Kundenbewertungen (passend zur Zielgruppe)
- Footer mit Copyright und Link → angebot.html
- Alle Bildpfade relativ (z.B. image-01.jpg, nicht /image-01.jpg)
- Wenn eine logo.png vorhanden ist, zeige sie in der Navigation
- Sprache: Deutsch
""".strip()

    index_html = _call_groq(code_system, index_prompt)

    # --- angebot.html ---
    angebot_prompt = f"""
Erstelle eine einfache, fokussierte angebot.html für "Hannah's Webdesign".

Kontext: Der Besucher ({data.company_name}) hat gerade die Demo-Website gesehen und soll jetzt zur Kontaktaufnahme bewegt werden.

Anforderungen:
- Vollständige HTML5-Seite mit <head> (charset, viewport, title, link zu styles.css, Google Fonts)
- Kleines Logo/Name "Hannah's Webdesign" oben links, daneben Link "← Zurück zur Demo" → index.html
- Großer zentrierter Hero-Text: "Gefällt Ihnen diese Website?" mit Unterzeile: "Wir erstellen Ihre komplette Website – professionell, schnell und zu fairen Preisen."
- Kurzer persönlicher Absatz: direkt an {data.company_name} gerichtet, Bezug auf {data.industry} in {data.region}
- Großer, auffälliger CTA-Button: "Jetzt kostenlos anfragen" → mailto:hallo@hannahs-webdesign.de
- Darunter kurz: Telefonnummer (fiktiv), E-Mail hallo@hannahs-webdesign.de
- Footer: Copyright Hannah's Webdesign
- Keine Pakete, keine Preislisten – nur die klare Botschaft und den Kontakt-Button
- Sprache: Deutsch
""".strip()

    angebot_html = _call_groq(code_system, angebot_prompt)

    # --- styles.css ---
    css_prompt = f"""
Erstelle eine vollständige styles.css für eine professionelle Unternehmenswebsite.

Design-Vorgaben aus der Anfrage: {data.style}
Branche: {data.industry}

Anforderungen:
- CSS Custom Properties (--primary-color, --secondary-color, --font-main, etc.) passend zum Stil
- Google Fonts Import (2 passende Schriften)
- Reset / Box-sizing
- Navigation: sticky, mit Hamburger-Menü für Mobile (JavaScript-frei via :checked trick)
- Hero: full-viewport-height, background-image cover, dunkles Overlay, zentrierter Text
- Responsive Grid für Leistungskarten (3 Spalten Desktop, 2 Tablet, 1 Mobile)
- Galerie: CSS Grid, 2 Spalten
- Testimonials: Flex, Karten mit Schatten
- Kontaktbereich: zentriert, andere Hintergrundfarbe
- Buttons: abgerundet, hover-Animation
- Footer: dunkler Hintergrund
- Animierter Hero-Text (fade-in)
- Media Queries für 768px und 480px
- Keine externen Abhängigkeiten außer Google Fonts
""".strip()

    styles_css = _call_groq(code_system, css_prompt)

    # --- Outreach email ---
    email_system = (
        "Du bist ein erfahrener Vertriebstexter. Schreibe professionelle, "
        "persönliche Akquise-E-Mails auf Deutsch."
    )
    email_prompt = f"""
Schreibe eine kurze, professionelle Akquise-E-Mail von Hannah's Webdesign an {data.company_name}.

Kontext:
- Empfänger: {data.company_name}, {data.industry}, in {data.region}
- Wir haben kostenlos eine Demo-Website für sie erstellt
- Vorschau: {config.PREVIEW_BASE_URL}/{data.slug}/
- Ziel: Termin oder Rückruf vereinbaren

Format:
- Betreff-Zeile am Anfang (Betreff: ...)
- Ca. 150-180 Wörter
- Persönliche Ansprache, kein generisches Template
- Erwähne konkret die Branche und den Mehrwert einer professionellen Website
- CTA: auf die Demo-Seite verweisen, dann Kontaktaufnahme vorschlagen
- Unterschrift: Hannah Müller, Hannah's Webdesign, hallo@hannahs-webdesign.de
""".strip()

    outreach_email = _call_groq(email_system, email_prompt)

    return GeneratedSite(
        index_html=index_html,
        angebot_html=angebot_html,
        styles_css=styles_css,
        outreach_email=outreach_email,
    )
