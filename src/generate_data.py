import os
import sys
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from notion_client import Client
from dotenv import load_dotenv

TAIPEI = ZoneInfo("Asia/Taipei")


def main():
    load_dotenv(encoding="utf-8")

    NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
    NOTION_DATASOURCE_ID = os.environ.get("NOTION_DATASOURCE_ID")
    DATE_PROP = os.environ.get("NOTION_DATE_PROP")
    DURATION_PROP = os.environ.get("NOTION_DURATION_PROP")

    if not DATE_PROP or not DURATION_PROP:
        print("Error: NOTION_DATE_PROP or NOTION_DURATION_PROP not set.")
        sys.exit(1)
    if not NOTION_TOKEN or not NOTION_DATASOURCE_ID:
        print("Error: NOTION_TOKEN or NOTION_DATASOURCE_ID not set.")
        sys.exit(1)

    # Date window: 52 weeks back, aligned to Monday
    today = datetime.now(TAIPEI).date()
    one_year_ago = today - timedelta(weeks=52)
    start_date = one_year_ago - timedelta(days=one_year_ago.weekday())
    print(f"Querying window: {start_date} to {today}")

    notion = Client(auth=NOTION_TOKEN)
    daily = defaultdict(float)
    total_records = 0

    has_more = True
    start_cursor = None
    while has_more:
        try:
            response = notion.data_sources.query(
                data_source_id=NOTION_DATASOURCE_ID,
                start_cursor=start_cursor,
                page_size=100,
                filter={
                    "timestamp": "created_time",
                    "created_time": {"on_or_after": start_date.isoformat()},
                },
            )
        except Exception as e:
            print(f"Error querying Notion: {e}")
            sys.exit(1)

        for page in response.get("results", []):
            props = page.get("properties", {})

            # --- Extract date (same three fallbacks as before) ---
            date_prop = props.get(DATE_PROP, {})
            date_str = None
            if date_prop.get("type") == "date":
                d = date_prop.get("date")
                if d:
                    date_str = d.get("start")
            if not date_str and date_prop.get("type") == "created_time":
                date_str = date_prop.get("created_time")
            if not date_str:
                content = date_prop.get("title", []) or date_prop.get("rich_text", [])
                if content:
                    mention = content[0].get("mention") or {}
                    date_str = (mention.get("date") or {}).get("start")
            if not date_str:
                continue

            # --- Extract duration (rollup.number) ---
            duration = props.get(DURATION_PROP, {}).get("rollup", {}).get("number")
            if duration is None:
                continue

            # --- Parse & convert to Asia/Taipei local date ---
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local_date = dt.astimezone(TAIPEI).date()

            daily[local_date.isoformat()] += float(duration)
            total_records += 1

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")
        print(f"Total records so far: {total_records}")

    output_dir = Path("public")
    output_dir.mkdir(exist_ok=True)

    payload = {
        "generated_at": datetime.now(TAIPEI).isoformat(timespec="seconds"),
        "start_date": start_date.isoformat(),
        "end_date": today.isoformat(),
        # minutes per day; days with 0 are omitted, the page fills them in
        "days": dict(sorted(daily.items())),
    }

    out_path = output_dir / "heatmap.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Data saved to {out_path} ({len(daily)} active days)")


if __name__ == "__main__":
    main()
