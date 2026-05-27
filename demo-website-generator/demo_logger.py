"""Append a one-line record to demos.csv after each successful generation."""
import csv
import os
from datetime import datetime

_LOG = os.path.join(os.path.dirname(__file__), "demos.csv")
_FIELDS = ["date_utc", "company", "industry", "region",
           "preview_url", "had_website", "logo_generated"]


def log(data, preview_url: str, had_website: bool) -> None:
    exists = os.path.exists(_LOG)
    with open(_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS)
        if not exists:
            w.writeheader()
        w.writerow({
            "date_utc":       datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            "company":        data.company_name,
            "industry":       data.industry,
            "region":         data.region or "",
            "preview_url":    preview_url,
            "had_website":    "yes" if had_website else "no",
            "logo_generated": "yes" if getattr(data, "generate_logo", False) else "no",
        })
    print(f"[demo_logger] Logged: {data.company_name} → {preview_url}")
