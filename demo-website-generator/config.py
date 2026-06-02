import os
from dotenv import load_dotenv

load_dotenv()

# IMAP (incoming email)
IMAP_HOST = os.environ["IMAP_HOST"]
IMAP_PORT = int(os.getenv("IMAP_PORT") or "993")
IMAP_USER = os.environ["IMAP_USER"]
IMAP_PASS = os.environ["IMAP_PASS"]

# SMTP (outgoing email)
SMTP_HOST = os.environ["SMTP_HOST"]
SMTP_PORT = int(os.getenv("SMTP_PORT") or "465")
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASS"]

# Anthropic Claude (email parsing + HTML/content generation)
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# STRATO SFTP
STRATO_SFTP_HOST = os.environ["STRATO_SFTP_HOST"]
STRATO_SFTP_USER = os.environ["STRATO_SFTP_USER"]
STRATO_SFTP_PASS = os.environ["STRATO_SFTP_PASS"]
STRATO_SFTP_ROOT = os.getenv("STRATO_SFTP_ROOT", "/httpdocs")

# Preview base URL (your domain where demos live)
PREVIEW_BASE_URL = os.getenv("PREVIEW_BASE_URL", "https://www.hannahs-webdesign.de")

# Together AI — free FLUX.1-schnell image generation (recommended)
# Sign up free at https://api.together.xyz → grab API key
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")

# Hugging Face — alternative FLUX.1-schnell (requires Pro account on HF)
HF_TOKEN = os.getenv("HF_TOKEN", "")

# Polling interval
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS") or "120")
