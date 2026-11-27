#!/usr/bin/env python3
"""
Weekly SaaS Churn Radar report generator.
Reads verified B2B buying intent signals from a local JSON file or fetches live
from the Apify SignalRadar Actor, then writes a formatted Markdown report.
"""

import argparse
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

APIFY_SYNC_URL = (
    "https://api.apify.com/v2/acts/"
    "seanxin~b2b-buying-intent-pain-radar/run-sync-get-dataset-items"
)


def fetch_from_apify(token: str, competitors: list[str], days_back: int = 7) -> list[dict]:
    """Fetch live signals from SignalRadar Apify Actor."""
    payload = json.dumps({
        "competitors": competitors,
        "nicheKeywords": ["alternative to", "switching from", "pricing hike", "too expensive"],
        "sources": ["hackernews", "reddit_rss", "github_issues", "devto"],
        "subreddits": ["SaaS", "sales", "coldemail", "Observability", "CRMSoftware"],
        "daysBack": days_back,
        "minIntentScore": 3,
        "maxResults": 50,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{APIFY_SYNC_URL}?token={token}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def render_markdown(items: list[dict], generated_date: str) -> str:
    """Filter, sort, and render qualified intent signals as Markdown."""
    qualified = [x for x in items if isinstance(x, dict) and int(x.get("intentScore", 0)) >= 3]
    qualified.sort(key=lambda x: int(x.get("intentScore", 0)), reverse=True)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in qualified:
        cat = str(item.get("painCategory") or "general")
        grouped[cat].append(item)

    lines = [
        f"# SaaS Churn Radar Report ({generated_date})",
        "",
        f"Total qualified switching/pain signals (`intentScore >= 3`): **{len(qualified)}**",
        "",
        "> Powered by [SignalRadar on Apify Store](https://apify.com/seanxin/b2b-buying-intent-pain-radar)",
        "",
        "## Summary Table",
        "",
        "| Score | Category | Source | Title | Link |",
        "| :---: | :--- | :--- | :--- | :--- |",
    ]

    for item in qualified:
        score = item.get("intentScore", "-")
        cat = str(item.get("painCategory") or "general").replace("|", "\\|")
        src = str(item.get("source") or "unknown").replace("|", "\\|")
        title = str(item.get("title") or "Untitled").replace("|", "\\|").replace("\n", " ")[:90]
        url = str(item.get("url") or "")
        link_md = f"[View Thread]({url})" if url else "-"
        lines.append(f"| **{score}/5** | `{cat}` | {src} | {title} | {link_md} |")

    lines.extend(["", "## Signals by Pain Category", ""])
    for cat in sorted(grouped.keys()):
        lines.append(f"### `{cat}` ({len(grouped[cat])})")
        lines.append("")
        for item in grouped[cat]:
            score = item.get("intentScore", "-")
            title = str(item.get("title") or "Untitled").replace("\n", " ")
            url = str(item.get("url") or "")
            snippet = str(item.get("snippet") or "").strip().replace("\n", " ")[:240]
            angle = str(item.get("safeReplyAngle") or "").strip().replace("\n", " ")
            lines.append(f"- **[{score}/5] {title}** ({item.get('source', 'unknown')})")
            if snippet:
                lines.append(f"  > {snippet}")
            if angle:
                lines.append(f"  - `safeReplyAngle`: {angle}")
            if url:
                lines.append(f"  - Source: {url}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SaaS Churn Radar Markdown report.")
    parser.add_argument("--input", help="Path to local JSON array of signals.")
    parser.add_argument("--fetch", action="store_true", help="Fetch live signals from Apify using APIFY_TOKEN.")
    parser.add_argument("--output", required=True, help="Output Markdown file path.")
    parser.add_argument(
        "--competitors",
        default="HubSpot,Datadog,Apollo.io,Instantly,Airtable,Notion",
        help="Comma-separated competitor names when using --fetch.",
    )
    args = parser.parse_args()

    if args.fetch:
        token = os.environ.get("APIFY_TOKEN", "").strip()
        if not token:
            print("Error: APIFY_TOKEN environment variable is required with --fetch.", file=sys.stderr)
            return 1
        competitors = [c.strip() for c in args.competitors.split(",") if c.strip()]
        items = fetch_from_apify(token, competitors)
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            items = json.load(f)
    else:
        print("Error: Provide either --input <path> or --fetch.", file=sys.stderr)
        return 1

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md = render_markdown(items, today)

    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Wrote {len(md)} bytes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
