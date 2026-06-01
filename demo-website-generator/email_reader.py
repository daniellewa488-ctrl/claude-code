import os
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
import config

_PROCESSED_FILE = os.path.join(os.path.dirname(__file__), "processed_ids.txt")

# Python-level age guard — reject anything older than this even if IMAP returns it
_MAX_AGE_HOURS = 24


def _load_processed() -> set:
    if not os.path.exists(_PROCESSED_FILE):
        return set()
    with open(_PROCESSED_FILE, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _save_processed(msg_id: str) -> None:
    with open(_PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(msg_id + "\n")


def _is_recent(msg) -> bool:
    date_str = msg.get("Date", "")
    if not date_str:
        return True
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt <= timedelta(hours=_MAX_AGE_HOURS)
    except Exception:
        return True


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
    Return unprocessed Workflow emails received in the last 24 hours.
    Uses IMAP SINCE to filter at the server level so old backlog is never fetched.
    Marks each returned email as read and records its Message-ID so it is never
    processed again even if processed_ids.txt is re-used across runs.
    """
    results = []
    already_processed = _load_processed()

    try:
        conn = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
        conn.login(config.IMAP_USER, config.IMAP_PASS)
        print(f"[email_reader] Connected as {config.IMAP_USER}")

        conn.select("INBOX")

        status, total = conn.search(None, "ALL")
        total_count = len(total[0].split()) if total[0] else 0
        status, unseen = conn.search(None, "UNSEEN")
        unseen_count = len(unseen[0].split()) if unseen[0] else 0
        print(f"[email_reader] INBOX: {total_count} total, {unseen_count} unread")

        # Ask the IMAP server to filter by date — only emails from the last 2 days
        # (SINCE has date-only precision, so we go back 2 days to avoid timezone edge cases)
        since_str = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%d-%b-%Y")

        uids_found = set()
        for term in ["Workflow", "workflow", "WORKFLOW"]:
            status, data = conn.search(None, f'SINCE {since_str} SUBJECT "{term}"')
            if status == "OK" and data[0]:
                for uid in data[0].split():
                    uids_found.add(uid)

        print(f"[email_reader] Found {len(uids_found)} Workflow email(s) in last 2 days")

        if not uids_found and unseen_count > 0:
            status, data = conn.search(None, "UNSEEN")
            if status == "OK" and data[0]:
                print("[email_reader] Unread emails in inbox (for diagnosis):")
                for uid in data[0].split()[:10]:
                    s, md = conn.fetch(uid, "(BODY[HEADER.FIELDS (SUBJECT FROM)])")
                    if s == "OK":
                        m = email.message_from_bytes(md[0][1])
                        print(f"  uid={uid.decode()} from={_decode_str(m.get('From',''))} subject={_decode_str(m.get('Subject',''))}")

        new_count = 0
        skipped_processed = 0
        skipped_old = 0

        for uid in sorted(uids_found):
            status, msg_data = conn.fetch(uid, "(RFC822)")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            # Secondary Python-level age check (catches emails just outside the 24h window)
            if not _is_recent(msg):
                skipped_old += 1
                msg_id = _decode_str(msg.get("Message-ID", "")).strip() or (
                    _decode_str(msg.get("From", "")) + "|" + _decode_str(msg.get("Date", ""))
                )
                if msg_id not in already_processed:
                    _save_processed(msg_id)
                    already_processed.add(msg_id)
                continue

            msg_id = _decode_str(msg.get("Message-ID", "")).strip()
            if not msg_id:
                msg_id = _decode_str(msg.get("From", "")) + "|" + _decode_str(msg.get("Date", ""))

            if msg_id in already_processed:
                skipped_processed += 1
                continue

            sender = _decode_str(msg.get("From", ""))
            subject = _decode_str(msg.get("Subject", ""))
            body = _get_body(msg)
            print(f"[email_reader] NEW email: subject='{subject}' from='{sender}'")

            results.append({"uid": uid, "sender": sender, "body": body, "msg_id": msg_id})

            conn.store(uid, "+FLAGS", "\\Seen")
            _save_processed(msg_id)
            already_processed.add(msg_id)
            new_count += 1

        print(f"[email_reader] Result: {new_count} new | {skipped_processed} already processed | {skipped_old} too old")
        conn.logout()

    except Exception as e:
        print(f"[email_reader] Error: {e}")
        import traceback
        traceback.print_exc()

    return results
