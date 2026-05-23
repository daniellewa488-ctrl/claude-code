import io
import stat
import paramiko
import config


def _mkdir_p(sftp, remote_path: str):
    """Create remote directory tree, ignoring if exists."""
    parts = remote_path.replace("\\", "/").split("/")
    current = ""
    for part in parts:
        if not part:
            continue
        current += f"/{part}"
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def upload(slug: str, site, images) -> str:
    """
    Upload all generated files to STRATO under {SFTP_ROOT}/{slug}/.
    Returns the remote directory path.
    """
    remote_dir = f"{config.STRATO_SFTP_ROOT}/{slug}"

    transport = paramiko.Transport((config.STRATO_SFTP_HOST, 22))
    transport.connect(username=config.STRATO_SFTP_USER, password=config.STRATO_SFTP_PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)

    try:
        _mkdir_p(sftp, remote_dir)

        # Upload text files
        text_files = {
            "index.html": site.index_html,
            "angebot.html": site.angebot_html,
            "styles.css": site.styles_css,
        }
        for name, content in text_files.items():
            remote_path = f"{remote_dir}/{name}"
            data = content.encode("utf-8")
            sftp.putfo(io.BytesIO(data), remote_path)
            print(f"[sftp_uploader] Uploaded {name}")

        # Upload images
        for filename, img_bytes in images.images.items():
            remote_path = f"{remote_dir}/{filename}"
            sftp.putfo(io.BytesIO(img_bytes), remote_path)
            print(f"[sftp_uploader] Uploaded {filename}")

        # Upload logo
        if images.logo_bytes:
            sftp.putfo(io.BytesIO(images.logo_bytes), f"{remote_dir}/logo.png")
            print("[sftp_uploader] Uploaded logo.png")

        # Upload logo concepts
        for name, logo_bytes in images.logo_concepts:
            sftp.putfo(io.BytesIO(logo_bytes), f"{remote_dir}/{name}")
            print(f"[sftp_uploader] Uploaded {name}")

    finally:
        sftp.close()
        transport.close()

    return remote_dir
