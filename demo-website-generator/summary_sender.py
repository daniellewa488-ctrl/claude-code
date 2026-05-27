import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import config


def _file_list(site, images) -> str:
    files = ["index.html", "angebot.html", "impressum.html", "styles.css"]
    files += list(images.images.keys())
    if images.logo_bytes:
        files.append("logo.png")
    for name, _ in images.logo_concepts:
        files.append(name)
    return "".join(f"<li>{f}</li>" for f in files)


def send(data, site, images) -> None:
    preview_url = f"{config.PREVIEW_BASE_URL}/{data.slug}/"

    outreach_escaped = site.outreach_email.replace("\n", "<br>")

    html_body = f"""
<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"><style>
  body {{ font-family: Arial, sans-serif; color: #333; max-width: 700px; margin: 0 auto; padding: 20px; }}
  .preview-btn {{ display: inline-block; background: #2563eb; color: white; padding: 14px 28px;
                  border-radius: 8px; text-decoration: none; font-size: 18px; margin: 20px 0; }}
  .box {{ background: #f0f4ff; border-left: 4px solid #2563eb; padding: 16px; border-radius: 4px; margin: 20px 0; }}
  ul {{ column-count: 2; }}
  h2 {{ color: #1e40af; }}
</style></head>
<body>
  <h1>✅ Demo-Website fertig: {data.company_name}</h1>
  <p>Die Demo wurde erfolgreich generiert und auf STRATO hochgeladen.</p>

  <a href="{preview_url}" class="preview-btn">🌐 Demo ansehen</a>

  <h2>Hochgeladene Dateien</h2>
  <ul>{_file_list(site, images)}</ul>

  <h2>Akquise-E-Mail (fertig zum Versenden)</h2>
  <div class="box">{outreach_escaped}</div>

  <p style="color:#888;font-size:12px">Automatisch generiert von Demo-Website-Generator</p>
</body>
</html>
""".strip()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Demo fertig: {data.company_name}"
    msg["From"] = config.SMTP_USER
    msg["To"] = data.sender_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=ctx) as server:
        server.login(config.SMTP_USER, config.SMTP_PASS)
        server.send_message(msg)

    print(f"[summary_sender] Summary email sent to {data.sender_email}")
