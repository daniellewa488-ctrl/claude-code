import io
import ftplib
import config


def _mkdir_p(ftp, remote_path: str):
    """Create remote directory tree, ignoring if exists."""
    parts = [p for p in remote_path.replace("\\", "/").split("/") if p]
    current = ""
    for part in parts:
        current += f"/{part}"
        try:
            ftp.mkd(current)
        except ftplib.error_perm:
            pass  # directory already exists


def upload(slug: str, site, images) -> str:
    """
    Upload all generated files to STRATO under {SFTP_ROOT}/{slug}/
    using FTP over TLS (FTPS) on port 21.
    Returns the remote directory path.
    """
    remote_dir = f"{config.STRATO_SFTP_ROOT}/{slug}"

    ftp = ftplib.FTP_TLS()
    ftp.connect(config.STRATO_SFTP_HOST, 21, timeout=30)
    ftp.login(config.STRATO_SFTP_USER, config.STRATO_SFTP_PASS)
    ftp.prot_p()  # enable encrypted data channel
    ftp.set_pasv(True)

    try:
        _mkdir_p(ftp, remote_dir)
        ftp.cwd(remote_dir)

        # Upload text files
        text_files = {
            "index.html": site.index_html,
            "angebot.html": site.angebot_html,
            "styles.css": site.styles_css,
        }
        for name, content in text_files.items():
            data = content.encode("utf-8")
            ftp.storbinary(f"STOR {name}", io.BytesIO(data))
            print(f"[ftp_uploader] Uploaded {name}")

        # Upload images
        for filename, img_bytes in images.images.items():
            ftp.storbinary(f"STOR {filename}", io.BytesIO(img_bytes))
            print(f"[ftp_uploader] Uploaded {filename}")

        # Upload logo
        if images.logo_bytes:
            ftp.storbinary("STOR logo.png", io.BytesIO(images.logo_bytes))
            print("[ftp_uploader] Uploaded logo.png")

        # Upload logo concepts
        for name, logo_bytes in images.logo_concepts:
            ftp.storbinary(f"STOR {name}", io.BytesIO(logo_bytes))
            print(f"[ftp_uploader] Uploaded {name}")

    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()

    return remote_dir
