"""
Social media posting engine for inspirational posters.

Handles:
  - Instagram (post + optional Facebook/Threads cross-post if connected)
  - WhatsApp Status

Requires: Claude in Chrome browser extension connected.
The poster_png_path must be a valid PNG file path.
"""

import os
import time


def build_caption(quote, day_label):
    """Build an engaging Instagram caption from the quote."""
    lines = []

    # Verse in original language
    lines.append(quote["original_text"])
    lines.append("")

    # Transliteration if non-English
    if quote.get("transliteration"):
        lines.append(f"— {quote['transliteration']}")
        lines.append("")

    # English meaning
    if quote.get("english_translation"):
        lines.append(f'"{quote["english_translation"]}"')
        lines.append("")

    # Attribution
    author = quote.get("author", "")
    source = quote.get("source", "")
    if author and source:
        lines.append(f"— {author}, {source}")
    elif author:
        lines.append(f"— {author}")
    lines.append("")

    # Morning message
    lines.append("🌅 " + quote["good_morning_message"])
    lines.append("")

    # Hashtags based on language/day
    lang_tags = {
        "tamil": "#Tamil #Bharathiyar #Thirukkural #TamilPoetry #TamilLiterature",
        "sanskrit": "#Sanskrit #BhagavadGita #Yoga #Vedanta #SanskritWisdom",
        "english": "#Poetry #MorningInspiration #ClassicPoetry #EnglishPoetry",
    }
    language = quote.get("day_tag", "").split("_")[1] if "_" in quote.get("day_tag", "") else "english"
    # Determine language from day_tag
    day_tag = quote.get("day_tag", "")
    if "tamil" in day_tag:
        lang = "tamil"
    elif "sanskrit" in day_tag or "yoga" in day_tag:
        lang = "sanskrit"
    else:
        lang = "english"

    lines.append(lang_tags.get(lang, ""))
    lines.append("#GoodMorning #MorningQuote #DailyInspiration #Wisdom #MorningVibes")

    return "\n".join(lines)


def get_poster_file_uri(png_path):
    """Convert absolute path to file URI for browser upload."""
    return f"file://{png_path}"
