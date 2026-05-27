import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send(company_name: str, error_message: str, tb: str) -> None:
    """Send an error alert to the operator (SMTP_USER) when demo generation fails."""
    import config

    subject = f"⚠️ Demo fehlgeschlagen: {company_name or 'Unbekannt'}"
    html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:20px;color:#333">
  <div style="background:#fef2f2;border-left:4px solid #dc2626;padding:16px;border-radius:6px;margin-bottom:20px">
    <h2 style="color:#dc2626;margin:0 0 8px">⚠️ Demo-Generierung fehlgeschlagen</h2>
    <p style="margin:0"><strong>Unternehmen:</strong> {company_name or 'Unbekannt'}</p>
  </div>
  <p><strong>Fehler:</strong></p>
  <pre style="background:#f3f4f6;padding:14px;border-radius:6px;font-size:13px;overflow-x:auto;white-space:pre-wrap">{error_message}</pre>
  <p><strong>Vollständiger Traceback:</strong></p>
  <pre style="background:#f3f4f6;padding:14px;border-radius:6px;font-size:12px;overflow-x:auto;white-space:pre-wrap">{tb}</pre>
  <p style="color:#9ca3af;font-size:12px;margin-top:24px">Automatisch gesendet vom Demo-Website-Generator</p>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_USER
    msg["To"] = config.SMTP_USER   # alert goes to Hannah's own inbox
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=ctx) as server:
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
        print(f"[error_notifier] Alert sent to {config.SMTP_USER}")
    except Exception as e:
        print(f"[error_notifier] Could not send alert: {e}")
