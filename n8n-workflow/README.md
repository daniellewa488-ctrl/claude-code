# Demo-Website Generator – n8n Workflow
**Hannah's Webdesign | Vollautomatische Demo-Websites per E-Mail**

---

## Was der Workflow macht

1. **E-Mail empfangen** – du sendest eine strukturierte E-Mail mit dem Betreff `Workflow`
2. **Daten extrahieren** – n8n liest Firmenname, Branche, URL, Logo, Region, Leistungen, Zielgruppe, Stil
3. **Website crawlen** – falls eine URL angegeben wurde, werden Homepage + eine Unterseite analysiert
4. **HTML/CSS generieren** – Groq AI (Llama 3.3 70B, kostenlos) erstellt individuelle `index.html`, `angebot.html` und `styles.css`
5. **10 KI-Bilder generieren** – Pollinations.ai (komplett kostenlos) erzeugt passende Fotos
6. **Logo einbinden** – vorhandenes Logo wird heruntergeladen; bei Facelift-Wunsch 3 KI-Logo-Konzepte
7. **SFTP-Upload** – alle Dateien landen auf STRATO unter `/httpdocs/{firmen-slug}/`
8. **Zusammenfassung senden** – du erhältst Vorschau-Link, fertige Akquise-E-Mail und Übersicht

**Vorschau-URL:** `https://www.hannahs-webdesign.de/{firmen-slug}/`

---

## Kosten (alles kostenlos!)

| Tool | Funktion | Kosten |
|------|----------|--------|
| n8n (self-hosted) | Workflow-Automation | Kostenlos |
| Groq API | HTML/CSS/Text generieren | Kostenlos (14.400 Req/Tag) |
| Pollinations.ai | Bilder generieren | Komplett kostenlos |
| Gmail | E-Mail senden/empfangen | Kostenlos |
| STRATO SFTP | Dateien hochladen | Im Hosting enthalten |

---

## Voraussetzungen

- **n8n** (self-hosted via Docker oder n8n.cloud Free Tier)
- **Groq-Account** → [console.groq.com](https://console.groq.com) (kostenlos, API-Key erstellen)
- **Gmail-Account** mit aktivierter n8n-Integration
- **STRATO Webhosting** mit SFTP-Zugang
- Domain `hannahs-webdesign.de` zeigt auf STRATO

---

## Schritt-für-Schritt Setup

### 1. n8n installieren

**Via Docker (empfohlen):**
```bash
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -e N8N_BASIC_AUTH_ACTIVE=true \
  -e N8N_BASIC_AUTH_USER=admin \
  -e N8N_BASIC_AUTH_PASSWORD=deinPasswort \
  -e GROQ_API_KEY=dein_groq_api_key_hier \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

**Via npm:**
```bash
npm install n8n -g
export GROQ_API_KEY=dein_groq_api_key_hier
n8n start
```

Dann öffne: `http://localhost:5678`

---

### 2. Groq API-Key einrichten

1. Registriere dich kostenlos auf [console.groq.com](https://console.groq.com)
2. Erstelle einen API-Key unter **API Keys**
3. Setze ihn als Umgebungsvariable:
   ```
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
   ```
   (In Docker: `-e GROQ_API_KEY=...`, sonst in der Shell/`.env`)

---

### 3. Workflow importieren

1. Öffne n8n (`http://localhost:5678`)
2. Klicke oben rechts auf **+** → **Import from file**
3. Wähle `workflow.json` aus diesem Ordner
4. Der Workflow erscheint im Editor

---

### 4. Gmail-Credential einrichten

1. In n8n: **Settings** → **Credentials** → **New Credential**
2. Typ: **Gmail OAuth2**
3. Folge der OAuth2-Einrichtung (Google Cloud Console)
   - Aktiviere die Gmail API in der Google Cloud Console
   - Erstelle OAuth2-Credentials (Desktop-App oder Web)
   - Scope benötigt: `gmail.readonly`, `gmail.send`
4. Nach Einrichtung: Im Workflow-Editor beide Gmail-Nodes öffnen und das Credential auswählen

---

### 5. STRATO SFTP-Credential einrichten

1. In n8n: **Settings** → **Credentials** → **New Credential**
2. Typ: **SFTP**
3. Felder ausfüllen:
   ```
   Host:     ssh.strato.de  (oder dein STRATO SFTP-Host)
   Port:     22
   Username: dein-strato-ftp-benutzer
   Password: dein-strato-ftp-passwort
   ```
4. **Credential speichern**
5. Im Workflow: Alle SFTP-Nodes öffnen und das Credential auswählen

**STRATO SFTP-Daten finden:**
- Login auf [mein.strato.de](https://mein.strato.de)
- Hosting → FTP-Zugänge
- SFTP-Host ist meist `ssh.strato.de` oder `ssh.ihr-server.de`

---

### 6. Credential-IDs im Workflow aktualisieren

Nach dem Import musst du in folgenden Nodes deine Credential-IDs eintragen:

| Node | Credential |
|------|-----------|
| `Email Trigger (Gmail)` | Gmail OAuth2 |
| `Zusammenfassung per Email senden` | Gmail OAuth2 |
| Alle `... hochladen` SFTP-Nodes (8x) | STRATO SFTP |

n8n zeigt beim Öffnen eines Nodes automatisch, welches Credential fehlt.

---

### 7. STRATO Verzeichnisstruktur prüfen

Stelle sicher, dass dein Web-Root korrekt ist. Auf STRATO ist es meist:
- `/httpdocs/` – Standardpfad für Webdateien

Der Workflow legt automatisch Unterordner an (z.B. `/httpdocs/muster-sanitaer-gmbh/`).

> **Tipp:** Falls dein Web-Root anders heißt (z.B. `/html/`), suche in allen SFTP-Nodes nach `/httpdocs/` und ersetze es.

---

### 8. Workflow aktivieren

1. Im n8n Workflow-Editor: oben rechts **Activate** einschalten
2. Der Gmail-Trigger prüft jetzt alle ~1 Minute auf neue E-Mails mit Betreff `Workflow`

---

## E-Mail senden

Sende eine E-Mail an deine Gmail-Adresse mit:
- **Betreff:** `Workflow`
- **Inhalt:** Strukturiertes Format (siehe `email-template.txt`)

**Beispiel:**
```
Unternehmensname: Bäckerei Müller
Branche: Bäckerei und Konditorei
Website: https://www.baeckerei-mueller.de
Logo: https://www.baeckerei-mueller.de/logo.png
Logo-Facelift: nein
Region: Nürnberg
Leistungen: Frischbrot, Konditorei, Catering, Partyservice
Zielgruppe: Privatkunden und Büros in Nürnberg
Stil: Warm, traditionell, orange-braun, einladend und gemütlich
```

Nach **ca. 3–8 Minuten** erhältst du die Bestätigungs-E-Mail.

---

## Dateistruktur auf STRATO

```
/httpdocs/
  baeckerei-mueller/
    index.html          ← Haupt-Demo-Seite
    angebot.html        ← CTA-Seite (Hannah's Webdesign)
    styles.css          ← Responsives Stylesheet
    image-01.jpg        ← Hero-Bild
    image-02.jpg        ← Team / Über uns
    image-03.jpg        ← Leistungen
    image-04.jpg        ← Vorteile
    image-05.jpg        ← Galerie
    image-06.jpg        ← Galerie
    image-07.jpg        ← Galerie
    image-08.jpg        ← Galerie
    image-09.jpg        ← Galerie
    image-10.jpg        ← Kontakt / Footer
    logo.png            ← (falls Logo-URL angegeben)
    logo-concept-1.jpg  ← (falls Facelift gewünscht)
    logo-concept-2.jpg  ← (falls Facelift gewünscht)
    logo-concept-3.jpg  ← (falls Facelift gewünscht)
    README.txt          ← Zusammenfassung
```

**Vorschau-URL:** `https://www.hannahs-webdesign.de/baeckerei-mueller/`

---

## Workflow-Architektur

```
[Gmail Trigger]
    ↓
[Parse Email Data]           → Felder extrahieren + Slug erstellen
    ↓
[Hat Website?]
    ├─ JA  → [Crawle Homepage] → [Extrahiere Content] → [Crawle Unterseite]
    └─ NEIN → [Leere Crawl-Daten]
    ↓
[Merge Crawl-Daten]
    ↓
[Groq: Index HTML]           → GPT-4 Qualität, kostenlos via Groq
    ↓
[Groq: Angebot HTML]
    ↓
[Groq: CSS]
    ↓
[Erstelle 10 Bild-Prompts]
    ↓
[Loop: Bild 1-10]
    ├─ [Pollinations.ai: Bild generieren]   → Kostenlos
    └─ [SFTP: Bild hochladen]              → Loop zurück
    ↓ (nach 10 Bildern)
[Hat Logo?]
    ├─ JA  → [Logo herunterladen] → [SFTP Upload]
    └─ NEIN → weiter
    ↓
[Facelift gewünscht?]
    ├─ JA  → [3x Logo-Konzepte generieren] → [3x SFTP Upload]
    └─ NEIN → weiter
    ↓
[Dateien vorbereiten]        → HTML/CSS aus Groq-Antworten extrahieren
    ↓
[4x SFTP Upload]             → index.html, angebot.html, styles.css, README.txt
    ↓
[Groq: Akquise-Email]        → Personalisierter Outreach-Text
    ↓
[Gmail: Zusammenfassung]     → An dich: Link + Akquise-Text + Übersicht
```

---

## Troubleshooting

### Workflow startet nicht
- Prüfe ob der Workflow **aktiviert** ist (blauer Schieberegler)
- Gmail-Credential korrekt eingerichtet?
- Betreff exakt `Workflow` (Groß-/Kleinschreibung prüfen)

### Groq gibt Fehler zurück
- API-Key prüfen: Umgebungsvariable `GROQ_API_KEY` gesetzt?
- Rate-Limit: Groq erlaubt 14.400 Requests/Tag kostenlos
- Fallback: In den HTTP Request Nodes das Modell auf `mixtral-8x7b-32768` ändern

### SFTP-Upload schlägt fehl
- STRATO SFTP-Credentials prüfen
- Port 22 (SFTP) ≠ Port 21 (FTP)
- Pfad `/httpdocs/` existiert und ist beschreibbar?
- Teste den SFTP-Zugang mit FileZilla o.ä.

### Bilder werden nicht generiert
- Pollinations.ai ist kostenlos aber manchmal langsam (bis 90 Sek. Timeout)
- Bei anhaltenden Problemen: URL testen: `https://image.pollinations.ai/prompt/test`
- Alternativ: In den Image-Nodes den Parameter `model=flux` zu `model=turbo` ändern

### HTML sieht nicht gut aus
- Groq's Llama 3.3 70B liefert normalerweise sehr gutes HTML
- Falls das Modell Markdown-Blöcke erzeugt: Die Code-Nodes `Dateien vorbereiten` und `index.html als Datei` strippen diese bereits automatisch
- Versuche, den Stil-Parameter in deiner E-Mail detaillierter zu formulieren

### Bilder-Loop geht nicht weiter
- Sicherstellen dass die SFTP-Node im Loop korrekt mit dem SplitInBatches-Node verbunden ist
- In n8n: Die letzte Node im Loop muss zurück zum `Bilder-Loop (10x)`-Node verbunden sein

---

## Anpassungen

### Andere KI für HTML (z.B. OpenAI)
Ersetze in den drei Groq HTTP-Request-Nodes:
- URL: `https://api.openai.com/v1/chat/completions`
- Header: `Authorization: Bearer {{ $env.OPENAI_API_KEY }}`
- Modell: `gpt-4o`

### Mehr/weniger Bilder
Im Node `Bild-Prompts erstellen` einfach Einträge im `prompts`-Array hinzufügen oder entfernen.

### Anderen SFTP-Pfad
In allen SFTP-Nodes `/httpdocs/` durch deinen tatsächlichen Web-Root ersetzen.

### E-Mail auf anderem Account empfangen
Im `Email Trigger`-Node das Gmail-Credential ändern. Der Trigger beobachtet dann diesen Account.

---

## Sicherheitshinweise

- Speichere API-Keys nie im Workflow selbst, sondern als n8n-Umgebungsvariablen
- Beschränke den STRATO SFTP-User wenn möglich auf das Webhosting-Verzeichnis
- Aktiviere n8n-Authentifizierung wenn es öffentlich erreichbar ist

---

*Erstellt für Hannah's Webdesign – Automatisiertes Demo-Website-System*
