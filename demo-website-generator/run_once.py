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
import config


def process_email(raw_email: dict) -> None:
    print(f"[run_once] Processing email from {raw_email['sender']}")

    data = email_parser.parse(raw_email)
    print(f"[run_once] Company: {data.company_name} | Slug: {data.slug}")

    print("[run_once] Crawling website...")
    crawled = website_crawler.crawl(data.website_url)

    print("[run_once] Generating HTML/CSS via Groq...")
    site = html_generator.generate(data, crawled)

    print("[run_once] Generating images via Pollinations.ai...")
    images = image_generator.generate(data)

    print("[run_once] Uploading to STRATO via SFTP...")
    preview_url = sftp_uploader.upload(data.slug, site, images)

    print("[run_once] Sending summary email...")
    summary_sender.send(data, site, images)

    print(f"[run_once] Done: {preview_url}")


def main():
    print("[run_once] Checking inbox for Workflow emails...")
    emails = email_reader.fetch_new()
    print(f"[run_once] Found {len(emails)} new Workflow email(s).")
    for raw_email in emails:
        try:
            process_email(raw_email)
        except Exception:
            print("[run_once] ERROR:")
            traceback.print_exc()


if __name__ == "__main__":
    main()
