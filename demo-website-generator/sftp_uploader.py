import io
import re
import paramiko
import config

_HTACCESS_MARKER_START = "# BEGIN Demo Websites - Auto-managed"
_HTACCESS_MARKER_END = "# END Demo Websites"
_HTACCESS_INJECTION = (
    "# BEGIN Demo Websites - Auto-managed\n"
    "<IfModule mod_rewrite.c>\n"
    "RewriteEngine On\n"
    "RewriteCond %{REQUEST_FILENAME} -d\n"
    "RewriteRule ^ - [L]\n"
    "</IfModule>\n"
    "# END Demo Websites\n"
)


def _mkdir_p(sftp, remote_path: str):
    parts = [p for p in remote_path.replace("\\", "/").split("/") if p]
    current = ""
    for part in parts:
        current += f"/{part}"
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def _patch_root_htaccess(sftp, root_path: str):
    """Prepend a rule so Apache serves real subdirectories directly, bypassing CMS rewrites."""
    htaccess_path = f"{root_path}/.htaccess"
    existing = ""
    try:
        with sftp.open(htaccess_path, "r") as f:
            existing = f.read().decode("utf-8", errors="replace")
    except FileNotFoundError:
        pass
    cleaned = re.sub(
        rf"{re.escape(_HTACCESS_MARKER_START)}.*?{re.escape(_HTACCESS_MARKER_END)}\n?",
        "",
        existing,
        flags=re.DOTALL,
    ).lstrip()
    new_content = _HTACCESS_INJECTION + cleaned
    sftp.putfo(io.BytesIO(new_content.encode("utf-8")), htaccess_path)
    print("[sftp_uploader] Patched root .htaccess — demo directories bypass CMS rewrites")


def upload(slug: str, site, images) -> str:
    remote_dir = f"{config.STRATO_SFTP_ROOT}/{slug}"
    print(f"[sftp_uploader] Connecting to {config.STRATO_SFTP_HOST}:22 ...")

    transport = paramiko.Transport((config.STRATO_SFTP_HOST, 22))
    transport.connect(username=config.STRATO_SFTP_USER, password=config.STRATO_SFTP_PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)

    try:
        _patch_root_htaccess(sftp, config.STRATO_SFTP_ROOT)
        _mkdir_p(sftp, remote_dir)

        text_files = {
            "index.html": site.index_html,
            "angebot.html": site.angebot_html,
            "impressum.html": site.impressum_html,
            "styles.css": site.styles_css,
            ".htaccess": "DirectoryIndex index.html\nOptions -Indexes\n",
        }
        for name, content in text_files.items():
            sftp.putfo(io.BytesIO(content.encode("utf-8")), f"{remote_dir}/{name}")
            print(f"[sftp_uploader] Uploaded {name}")

        for filename, img_bytes in images.images.items():
            sftp.putfo(io.BytesIO(img_bytes), f"{remote_dir}/{filename}")
            print(f"[sftp_uploader] Uploaded {filename}")

        if images.logo_bytes:
            logo_remote = f"{remote_dir}/{images.logo_filename}"
            sftp.putfo(io.BytesIO(images.logo_bytes), logo_remote)
            print(f"[sftp_uploader] Uploaded {images.logo_filename}")

        for name, logo_bytes in images.logo_concepts:
            sftp.putfo(io.BytesIO(logo_bytes), f"{remote_dir}/{name}")
            print(f"[sftp_uploader] Uploaded {name}")

    finally:
        sftp.close()
        transport.close()

    preview_url = f"{config.PREVIEW_BASE_URL}/{slug}/"
    print(f"[sftp_uploader] Done. Preview: {preview_url}")
    return preview_url
