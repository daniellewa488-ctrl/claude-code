import os
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
import config

_PROCESSED_FILE = os.path.join(os.path.dirname(__file__), "processed_ids.txt")

# Only process emails received within this window.
# Cron fires every 5 min — 15 min covers up to 2 delayed runs before giving up.
_MAX_AGE_MINUTES = 15


def _load_processed() -> set:
    if not os.path.exists(_PROCESSED_FILE):
        return set()
    with open(_PROCESSED_FILE, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _save_processed(msg_id: str) -> None:
    with open(_PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(msg_id + "\n")


def _age_minutes(msg) -> float:
    """Return how many minutes ago this email was sent. Returns 9999 if unparseable."""
    date_str = msg.get("Date", "")
    if not date_str:
        return 0  # no Date header → assume it just arrived
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return delta.total_seconds() / 60
    except Exception:
        return 0  # unparseable → assume recent


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
    Return Workflow emails received within the last 15 minutes that haven't
    been processed yet.

    Age check (15 min) is the primary gate — old emails are skipped regardless
    of processed_ids.txt state, so wiping that file never causes reprocessing.
    processed_ids.txt is a secondary dedup guard against two cron runs
    overlapping on the same fresh email.
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

        # Server-side filter: only today and yesterday (reduces emails scanned)
        since_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%d-%b-%Y")

        uids_found = set()
        for term in ["Workflow", "workflow", "WORKFLOW"]:
            status, data = conn.search(None, f'SINCE {since_str} SUBJECT "{term}"')
            if status == "OK" and data[0]:
                for uid in data[0].split():
                    uids_found.add(uid)

        print(f"[email_reader] Found {len(uids_found)} Workflow email(s) from last 24h")

        if not uids_found and unseen_count > 0:
            status, data = conn.search(None, "UNSEEN")
            if status == "OK" and data[0]:
                print("[email_reader] Unread inbox subjects (for diagnosis):")
                for uid in data[0].split()[:10]:
                    s, md = conn.fetch(uid, "(BODY[HEADER.FIELDS (SUBJECT FROM)])")
                    if s == "OK":
                        m = email.message_from_bytes(md[0][1])
                        print(f"  uid={uid.decode()} from={_decode_str(m.get('From',''))} subject={_decode_str(m.get('Subject',''))}")

        new_count = 0
        skipped_old = 0
        skipped_processed = 0

        for uid in sorted(uids_found):
            status, msg_data = conn.fetch(uid, "(RFC822)")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            age = _age_minutes(msg)

            # Primary gate: ignore anything older than 15 minutes
            if age > _MAX_AGE_MINUTES:
                skipped_old += 1
                continue

            msg_id = _decode_str(msg.get("Message-ID", "")).strip()
            if not msg_id:
                msg_id = _decode_str(msg.get("From", "")) + "|" + _decode_str(msg.get("Date", ""))

            # Secondary gate: skip if already processed in a previous run
            if msg_id in already_processed:
                skipped_processed += 1
                continue

            sender = _decode_str(msg.get("From", ""))
            subject = _decode_str(msg.get("Subject", ""))
            body = _get_body(msg)
            print(f"[email_reader] NEW ({age:.1f} min old): subject='{subject}' from='{sender}'")

            results.append({"uid": uid, "sender": sender, "body": body, "msg_id": msg_id})

            conn.store(uid, "+FLAGS", "\\Seen")
            _save_processed(msg_id)
            already_processed.add(msg_id)
            new_count += 1

        print(
            f"[email_reader] Result: {new_count} new | "
            f"{skipped_old} too old (>{_MAX_AGE_MINUTES} min) | "
            f"{skipped_processed} already processed"
        )
        conn.logout()

    except Exception as e:
        print(f"[email_reader] Error: {e}")
        import traceback
        traceback.print_exc()

    return results
