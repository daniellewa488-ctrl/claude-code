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
    Connect to IMAP, find unread emails with subject containing 'Workflow'
    (case-insensitive). Mark them as read. Return list of dicts: uid, sender, body.
    """
    results = []
    try:
        conn = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
        conn.login(config.IMAP_USER, config.IMAP_PASS)

        # List available folders for debugging
        status, folders = conn.list()
        print(f"[email_reader] Connected as {config.IMAP_USER}")

        conn.select("INBOX")

        # Log total inbox size and unseen count
        status, total = conn.search(None, "ALL")
        total_count = len(total[0].split()) if total[0] else 0
        status, unseen = conn.search(None, "UNSEEN")
        unseen_count = len(unseen[0].split()) if unseen[0] else 0
        print(f"[email_reader] INBOX: {total_count} total, {unseen_count} unseen")

        # Try searching for unread Workflow emails — try both capitalisation variants
        uids_found = set()
        for search_term in ["Workflow", "workflow", "WORKFLOW"]:
            status, data = conn.search(None, f'UNSEEN SUBJECT "{search_term}"')
            if status == "OK" and data[0]:
                for uid in data[0].split():
                    uids_found.add(uid)

        print(f"[email_reader] Found {len(uids_found)} unread Workflow email(s)")

        # If nothing found, log subjects of all unseen emails so we can diagnose
        if not uids_found and unseen_count > 0:
            status, data = conn.search(None, "UNSEEN")
            if status == "OK" and data[0]:
                print("[email_reader] Unread emails in inbox (subject preview):")
                for uid in data[0].split()[:10]:
                    s, md = conn.fetch(uid, "(BODY[HEADER.FIELDS (SUBJECT FROM)])")
                    if s == "OK":
                        msg = email.message_from_bytes(md[0][1])
                        print(f"  uid={uid.decode()} from={_decode_str(msg.get('From',''))} subject={_decode_str(msg.get('Subject',''))}")

        for uid in sorted(uids_found):
            status, msg_data = conn.fetch(uid, "(RFC822)")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            sender = _decode_str(msg.get("From", ""))
            subject = _decode_str(msg.get("Subject", ""))
            body = _get_body(msg)
            print(f"[email_reader] Processing: subject='{subject}' from='{sender}'")
            results.append({"uid": uid, "sender": sender, "body": body})
            conn.store(uid, "+FLAGS", "\\Seen")

        conn.logout()
    except Exception as e:
        print(f"[email_reader] Error: {e}")
        import traceback
        traceback.print_exc()
    return results
