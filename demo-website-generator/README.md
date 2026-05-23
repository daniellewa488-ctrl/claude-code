# Demo-Website-Generator

Vollautomatische Demo-Website-Erstellung: Eingehende E-Mail → HTML/CSS/Bilder generieren → STRATO hochladen → Zusammenfassung versenden.

## Was das System macht

1. Überwacht ein E-Mail-Postfach alle 2 Minuten via IMAP
2. Erkennt E-Mails mit Betreff **Workflow**
3. Crawlt die Unternehmenswebsite (falls angegeben)
4. Generiert `index.html`, `angebot.html`, `styles.css` via **Groq API** (kostenlos)
5. Generiert 10 Bilder via **Pollinations.ai** (kostenlos, kein API-Schlüssel nötig)
6. Lädt alles per SFTP auf STRATO hoch unter `/httpdocs/{slug}/`
7. Sendet eine Zusammenfassungs-E-Mail mit Vorschau-Link und fertiger Akquise-Mail

## Voraussetzungen

- Python 3.10+
- Ein E-Mail-Konto mit IMAP + SMTP Zugang
- [Groq API Key](https://console.groq.com) (kostenlos)
- STRATO-Hosting mit SFTP-Zugang
- (Für Cloud-Deployment) [Railway.app](https://railway.app) Account

## Lokale Installation

```bash
git clone https://github.com/daniellewa488-ctrl/claude-code.git
cd claude-code/demo-website-generator
pip install -r requirements.txt
cp .env.example .env
# .env mit deinen Zugangsdaten befüllen
python main.py
```

## Trigger-E-Mail Format

**Betreff:** `Workflow`

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

**Hinweise:**
- `Website: keine` → kein Crawling, nur Pflichtfelder werden genutzt
- `Logo: keine` → kein Logo
- `Logo-Facelift: ja` → 3 zusätzliche Logo-Konzepte werden generiert

## Deployment auf Railway.app (kostenlos)

### Schritt 1 – Repository verbinden
1. Gehe zu [railway.app](https://railway.app) → **New Project**
2. Wähle **Deploy from GitHub repo**
3. Wähle `daniellewa488-ctrl/claude-code`
4. Railway erkennt den `Procfile` automatisch

### Schritt 2 – Umgebungsvariablen setzen
Im Railway Dashboard → dein Projekt → **Variables** → alle Werte aus `.env.example` eintragen:

| Variable | Beschreibung |
|---|---|
| `IMAP_HOST` | IMAP-Server (z.B. `imap.strato.de`) |
| `IMAP_PORT` | IMAP-Port (Standard: `993`) |
| `IMAP_USER` | E-Mail-Adresse |
| `IMAP_PASS` | E-Mail-Passwort |
| `SMTP_HOST` | SMTP-Server (z.B. `smtp.strato.de`) |
| `SMTP_PORT` | SMTP-Port (Standard: `465`) |
| `SMTP_USER` | E-Mail-Adresse |
| `SMTP_PASS` | E-Mail-Passwort |
| `GROQ_API_KEY` | API-Schlüssel von console.groq.com |
| `STRATO_SFTP_HOST` | SFTP-Host (z.B. `ssh.strato.de`) |
| `STRATO_SFTP_USER` | SFTP-Benutzername |
| `STRATO_SFTP_PASS` | SFTP-Passwort |
| `STRATO_SFTP_ROOT` | Upload-Verzeichnis (z.B. `/httpdocs`) |
| `PREVIEW_BASE_URL` | Deine Domain (z.B. `https://www.hannahs-webdesign.de`) |

### Schritt 3 – Deployen
- Railway startet automatisch: `python main.py`
- Läuft 24/7, neustart bei Absturz automatisch
- Logs: Railway Dashboard → Logs

## Kostenübersicht

| Service | Kosten |
|---|---|
| Groq API | Kostenlos (14.400 Anfragen/Tag) |
| Pollinations.ai | Kostenlos, kein API-Schlüssel |
| Railway.app | $5/Monat Guthaben (reicht für dieses Skript) |
| E-Mail (IMAP/SMTP) | Bereits vorhanden |
| STRATO SFTP | Im Hosting-Paket enthalten |

## Dateistruktur nach Upload

```
/httpdocs/baeckerei-mueller/
├── index.html          ← Hauptseite
├── angebot.html        ← Hannah's Webdesign CTA
├── styles.css          ← Alle Styles
├── image-01.jpg        ← Hero-Bild
├── image-02.jpg        ← Team
├── ...
├── image-10.jpg        ← Abstrakt
├── logo.png            ← (optional, wenn URL angegeben)
├── logo-concept-1.jpg  ← (optional, wenn Facelift: ja)
├── logo-concept-2.jpg
└── logo-concept-3.jpg
```
