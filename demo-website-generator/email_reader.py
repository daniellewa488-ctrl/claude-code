import imaplib
import email
from email.header import decode_header
import config


def _decode_str(value):
    if value is None:
        return ""
    parts = decode_header(value)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _get_body(msg):
    """Extract plain text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="replace")
    else:
        charset = msg.get_content_charset() or "utf-8"
        return msg.get_payload(decode=True).decode(charset, errors="replace")
    return ""


def fetch_new():
    """
    Connect to IMAP, find unread emails with subject containing 'Workflow',
    mark them as read, return list of dicts with keys: uid, sender, body.
    """
    results = []
    try:
        conn = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
        conn.login(config.IMAP_USER, config.IMAP_PASS)
        conn.select("INBOX")

        status, data = conn.search(None, 'UNSEEN SUBJECT "Workflow"')
        if status != "OK" or not data[0]:
            conn.logout()
            return results

        uids = data[0].split()
        for uid in uids:
            status, msg_data = conn.fetch(uid, "(RFC822)")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            sender = _decode_str(msg.get("From", ""))
            body = _get_body(msg)
            results.append({"uid": uid, "sender": sender, "body": body})
            # Mark as read
            conn.store(uid, "+FLAGS", "\\Seen")

        conn.logout()
    except Exception as e:
        print(f"[email_reader] Error: {e}")
    return results
