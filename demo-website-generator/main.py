import time
import traceback
import config
import email_reader
import email_parser
import website_crawler
import html_generator
import image_generator
import sftp_uploader
import summary_sender


def process_email(raw_email: dict) -> None:
    print(f"[main] Processing email from {raw_email['sender']}")

    data = email_parser.parse(raw_email)
    print(f"[main] Company: {data.company_name} | Slug: {data.slug}")

    print("[main] Crawling website...")
    crawled = website_crawler.crawl(data.website_url)

    print("[main] Generating HTML/CSS via Groq...")
    site = html_generator.generate(data, crawled)

    print("[main] Generating images via Pollinations.ai...")
    images = image_generator.generate(data)

    print("[main] Uploading to STRATO via SFTP...")
    sftp_uploader.upload(data.slug, site, images)

    print("[main] Sending summary email...")
    summary_sender.send(data, site, images)

    print(f"[main] ✅ Done: {config.PREVIEW_BASE_URL}/{data.slug}/")


def main():
    print(f"[main] Demo-Website-Generator started. Polling every {config.POLL_INTERVAL_SECONDS}s.")
    while True:
        try:
            emails = email_reader.fetch_new()
            if emails:
                print(f"[main] Found {len(emails)} new Workflow email(s).")
            for raw_email in emails:
                try:
                    process_email(raw_email)
                except Exception:
                    print(f"[main] ERROR processing email:")
                    traceback.print_exc()
        except Exception:
            print("[main] ERROR in polling loop:")
            traceback.print_exc()

        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
