import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import traceback
import email_reader
import email_parser
import website_crawler
import html_generator
import image_generator
import sftp_uploader
import summary_sender
import error_notifier
import demo_logger
import config


def process_email(raw_email: dict) -> None:
    print(f"[run_once] Processing email from {raw_email['sender']}")

    data = email_parser.parse(raw_email)
    print(f"[run_once] Company: {data.company_name} | Slug: {data.slug}")

    # ── Path A: crawl existing website ────────────────────────────────────────
    if data.website_url:
        print(f"[run_once] Website provided: {data.website_url} — crawling...")
        crawled = website_crawler.crawl(data.website_url)

        if crawled.found:
            # Use logo found on their site if the email didn't supply one
            if crawled.logo_url and not data.logo_url:
                data.logo_url = crawled.logo_url
                print(f"[run_once] Using logo found on website: {crawled.logo_url}")
        else:
            print(
                f"[run_once] Website '{data.website_url}' is unreachable — "
                "falling back to email data only for content generation"
            )
    # ── Path B: no website ────────────────────────────────────────────────────
    else:
        print("[run_once] No website URL provided — using email data only.")
        crawled = website_crawler.CrawledData(found=False)

    print("[run_once] Generating website via Claude...")
    site = html_generator.generate(data, crawled)

    print("[run_once] Generating images via Pollinations.ai...")
    images = image_generator.generate(data)

    print("[run_once] Uploading to STRATO via SFTP...")
    preview_url = sftp_uploader.upload(data.slug, site, images)

    print("[run_once] Sending summary email...")
    summary_sender.send(data, site, images)

    demo_logger.log(data, preview_url, had_website=bool(data.website_url))
    print(f"[run_once] Done: {preview_url}")


def main():
    print("[run_once] Checking inbox for Workflow emails...")
    emails = email_reader.fetch_new()
    print(f"[run_once] Found {len(emails)} new Workflow email(s).")
    for raw_email in emails:
        company_name = ""
        try:
            try:
                company_name = email_parser.parse(raw_email).company_name
            except Exception:
                pass
            process_email(raw_email)
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[run_once] ERROR processing email:\n{tb}")
            try:
                error_notifier.send(company_name, str(exc), tb)
            except Exception as notify_err:
                print(f"[run_once] Could not send error notification: {notify_err}")


if __name__ == "__main__":
    main()
