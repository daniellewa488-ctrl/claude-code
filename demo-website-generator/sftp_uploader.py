import io
import paramiko
import config


def _mkdir_p(sftp, remote_path: str):
    """Create remote directory tree, ignoring if exists."""
    parts = [p for p in remote_path.replace("\\", "/").split("/") if p]
    current = ""
    for part in parts:
        current += f"/{part}"
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def upload(slug: str, site, images) -> str:
    """
    Upload all generated files to STRATO under {SFTP_ROOT}/{slug}/.
    Returns the preview URL.
    """
    remote_dir = f"{config.STRATO_SFTP_ROOT}/{slug}"
    print(f"[sftp_uploader] Connecting to {config.STRATO_SFTP_HOST}:22 ...")

    transport = paramiko.Transport((config.STRATO_SFTP_HOST, 22))
    transport.connect(username=config.STRATO_SFTP_USER, password=config.STRATO_SFTP_PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)

    try:
        _mkdir_p(sftp, remote_dir)

        text_files = {
            "index.html": site.index_html,
            "angebot.html": site.angebot_html,
            "styles.css": site.styles_css,
        }
        for name, content in text_files.items():
            sftp.putfo(io.BytesIO(content.encode("utf-8")), f"{remote_dir}/{name}")
            print(f"[sftp_uploader] Uploaded {name}")

        for filename, img_bytes in images.images.items():
            sftp.putfo(io.BytesIO(img_bytes), f"{remote_dir}/{filename}")
            print(f"[sftp_uploader] Uploaded {filename}")

        if images.logo_bytes:
            sftp.putfo(io.BytesIO(images.logo_bytes), f"{remote_dir}/logo.png")
            print("[sftp_uploader] Uploaded logo.png")

        for name, logo_bytes in images.logo_concepts:
            sftp.putfo(io.BytesIO(logo_bytes), f"{remote_dir}/{name}")
            print(f"[sftp_uploader] Uploaded {name}")

    finally:
        sftp.close()
        transport.close()

    preview_url = f"{config.PREVIEW_BASE_URL}/{slug}/"
    print(f"[sftp_uploader] Done. Preview: {preview_url}")
    return preview_url
