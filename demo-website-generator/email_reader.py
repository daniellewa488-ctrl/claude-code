import os
import imaplib
import email
from email.header import decode_header
import config

# Tracks Message-IDs we've already processed so we never run the same email twice,
# regardless of whether it was opened/read before the workflow ran.
_PROCESSED_FILE = os.path.join(os.path.dirname(__file__), "processed_ids.txt")


def _load_processed() -> set:
    if not os.path.exists(_PROCESSED_FILE):
        return set()
    with open(_PROCESSED_FILE, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _save_processed(msg_id: str) -> None:
    with open(_PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(msg_id + "\n")


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
    Connect to IMAP, find ALL emails (read or unread) with subject containing
    'Workflow' that haven't been processed yet. Mark as read and record their
    Message-ID so we never process the same email twice.
    """
    results = []
    already_processed = _load_processed()

    try:
        conn = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
        conn.login(config.IMAP_USER, config.IMAP_PASS)
        print(f"[email_reader] Connected as {config.IMAP_USER}")

        conn.select("INBOX")

        # Log inbox state
        status, total = conn.search(None, "ALL")
        total_count = len(total[0].split()) if total[0] else 0
        status, unseen = conn.search(None, "UNSEEN")
        unseen_count = len(unseen[0].split()) if unseen[0] else 0
        print(f"[email_reader] INBOX: {total_count} total, {unseen_count} unread")

        # Search ALL emails (read + unread) matching any capitalisation of "Workflow"
        uids_found = set()
        for term in ["Workflow", "workflow", "WORKFLOW"]:
            status, data = conn.search(None, f'SUBJECT "{term}"')
            if status == "OK" and data[0]:
                for uid in data[0].split():
                    uids_found.add(uid)

        print(f"[email_reader] Found {len(uids_found)} Workflow email(s) in inbox (read + unread)")

        # If nothing at all, log unread subjects to help diagnose
        if not uids_found and unseen_count > 0:
            status, data = conn.search(None, "UNSEEN")
            if status == "OK" and data[0]:
                print("[email_reader] Unread emails found (subjects):")
                for uid in data[0].split()[:10]:
                    s, md = conn.fetch(uid, "(BODY[HEADER.FIELDS (SUBJECT FROM)])")
                    if s == "OK":
                        msg = email.message_from_bytes(md[0][1])
                        print(f"  uid={uid.decode()} from={_decode_str(msg.get('From',''))} subject={_decode_str(msg.get('Subject',''))}")

        new_count = 0
        skipped_count = 0
        for uid in sorted(uids_found):
            status, msg_data = conn.fetch(uid, "(RFC822)")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            # Use Message-ID as the dedup key — stable across sessions
            msg_id = _decode_str(msg.get("Message-ID", "")).strip()
            if not msg_id:
                # Fall back to From + Date if no Message-ID
                msg_id = _decode_str(msg.get("From", "")) + "|" + _decode_str(msg.get("Date", ""))

            if msg_id in already_processed:
                skipped_count += 1
                print(f"[email_reader] Already processed — skipping: {msg_id[:60]}")
                continue

            sender = _decode_str(msg.get("From", ""))
            subject = _decode_str(msg.get("Subject", ""))
            body = _get_body(msg)
            print(f"[email_reader] NEW email to process: subject='{subject}' from='{sender}'")

            results.append({"uid": uid, "sender": sender, "body": body, "msg_id": msg_id})

            # Mark as read and record as processed
            conn.store(uid, "+FLAGS", "\\Seen")
            _save_processed(msg_id)
            already_processed.add(msg_id)
            new_count += 1

        print(f"[email_reader] Result: {new_count} new, {skipped_count} already processed")

        conn.logout()
    except Exception as e:
        print(f"[email_reader] Error: {e}")
        import traceback
        traceback.print_exc()

    return results
