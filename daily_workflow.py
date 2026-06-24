"""
Daily Inspirational Poster Workflow — Main Orchestrator

This script is called by the scheduled task each morning. It:
1. Determines today's quote based on day of week
2. Generates the poster HTML (with scenic background + verse)
3. Saves the quote info to a pending approval file
4. Signals Claude to present the poster for user approval
5. Upon approval: posts to Instagram + WhatsApp Status

Run manually:
    python daily_workflow.py              # Today's poster
    python daily_workflow.py --day friday # Specific day
    python daily_workflow.py --preview    # Generate without posting
"""

import sys
import os
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from poster_generator import generate_poster_html
from quote_database import get_quote_for_day, get_rotation_status
from post_to_social import build_caption
from config import POSTERS_DIR, DAY_SCHEDULE

PENDING_FILE = os.path.join(os.path.dirname(__file__), "output", "pending_approval.json")


def run_daily_workflow(day_of_week=None, preview_only=False):
    """
    Main workflow:
    1. Generate poster
    2. Save metadata for approval
    3. Return info for Claude to present to user
    """
    os.makedirs(POSTERS_DIR, exist_ok=True)

    if day_of_week is None:
        day_of_week = datetime.now().weekday()

    schedule = DAY_SCHEDULE[day_of_week]
    day_label = schedule["label"]
    today_str = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*55}")
    print(f"  Daily Inspirational Poster — {day_label}, {today_str}")
    print(f"{'='*55}")

    # Step 1: Get quote
    print(f"\n📖 Selecting today's {schedule['language']} verse...")
    quote = get_quote_for_day(day_of_week)
    print(f"   Source: {quote.get('author', '')}, {quote['source']}")

    # Step 2: Generate poster HTML
    html_filename = f"poster_{day_label.lower()}_{today_str}.html"
    html_path = os.path.join(POSTERS_DIR, html_filename)
    print(f"\n🎨 Generating poster with {schedule['theme']} background...")
    generate_poster_html(day_of_week=day_of_week, output_path=html_path)
    print(f"   Saved: {html_path}")

    # Step 3: Build caption
    caption = build_caption(quote, day_label)

    # Step 4: Save pending approval data
    pending = {
        "day_label": day_label,
        "day_of_week": day_of_week,
        "date": today_str,
        "quote": quote,
        "html_path": html_path,
        "caption": caption,
        "preview_only": preview_only,
        "status": "pending",
        "generated_at": datetime.now().isoformat(),
    }
    os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, indent=2, ensure_ascii=False)

    # Step 5: Print summary for Claude to present
    print(f"\n✅ Poster ready for approval!")
    print(f"\n{'─'*55}")
    print(f"  📅 {day_label} | {quote.get('author','')}")
    print(f"  📜 {quote['source']}")
    print(f"\n  VERSE:")
    print(f"  {quote['original_text'][:120]}...")
    if quote.get('transliteration'):
        print(f"\n  Transliteration: {quote['transliteration'][:80]}...")
    if quote.get('english_translation'):
        print(f"\n  Meaning: {quote['english_translation'][:120]}...")
    print(f"\n  🌅 {quote['good_morning_message']}")
    print(f"{'─'*55}")
    print(f"\n  HTML poster: {html_path}")
    print(f"\n  CAPTION PREVIEW:")
    print(f"  {caption[:200]}...")
    print(f"\n{'='*55}")
    print(f"\nAWAITING YOUR APPROVAL")
    print(f"Please review the poster and reply:")
    print(f"  ✅ 'post it' — to post to Instagram + WhatsApp")
    print(f"  ❌ 'skip' — to skip posting today")
    print(f"  🔄 'regenerate' — to generate a fresh poster")
    print(f"{'='*55}\n")

    return pending


def load_pending():
    """Load the currently pending poster approval data."""
    if not os.path.exists(PENDING_FILE):
        return None
    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def mark_posted():
    """Mark the current pending poster as posted."""
    pending = load_pending()
    if pending:
        pending["status"] = "posted"
        pending["posted_at"] = datetime.now().isoformat()
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(pending, f, indent=2, ensure_ascii=False)


def mark_skipped():
    """Mark the current pending poster as skipped."""
    pending = load_pending()
    if pending:
        pending["status"] = "skipped"
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(pending, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run daily poster workflow")
    parser.add_argument("--day", type=str, help="Day name (e.g. friday, sunday)")
    parser.add_argument("--preview", action="store_true", help="Generate without posting")
    args = parser.parse_args()

    day_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
               "friday": 4, "saturday": 5, "sunday": 6}
    dow = None
    if args.day:
        dow = day_map.get(args.day.lower())

    run_daily_workflow(day_of_week=dow, preview_only=args.preview)
