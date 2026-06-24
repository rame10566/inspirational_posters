"""
Poster generator — creates HTML poster files that render perfectly in all scripts.

Strategy:
1. Generate scenic background with Pillow (saves as PNG)
2. Create an HTML file with the poster layout using Google Fonts
   (Noto Sans Tamil, Noto Sans Devanagari, Playfair Display for English)
3. The HTML is self-contained and can be screenshotted via browser for final PNG

This approach ensures Tamil, Sanskrit (Devanagari), and English all render beautifully.
"""

import os
import base64
import json
import io
from datetime import datetime
from PIL import Image, ImageEnhance
from config import POSTER_WIDTH, POSTER_HEIGHT, POSTERS_DIR, DAY_SCHEDULE
from background_generator import generate_background
from quote_database import get_quote_for_day


def _bg_to_base64(bg_image):
    """Convert a Pillow image to base64 data URI for embedding in HTML."""
    # Very slight brightness boost to keep backgrounds light and vibrant
    enhancer = ImageEnhance.Brightness(bg_image)
    bg_image = enhancer.enhance(1.05)
    # Slight saturation boost
    from PIL import ImageEnhance as IE
    sat = IE.Color(bg_image)
    bg_image = sat.enhance(1.15)

    buffer = io.BytesIO()
    bg_image.save(buffer, format="PNG", quality=90)
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _compute_bg_brightness(bg_image, top_fraction=0.62):
    """
    Compute the average luminance of the top portion of the background image.
    Returns a float 0–255 (0=black, 255=white).
    Used to decide whether to use dark or light text.
    """
    width, height = bg_image.size
    crop_height = int(height * top_fraction)
    region = bg_image.crop((0, 0, width, crop_height))
    # Convert to grayscale and get mean brightness
    gray = region.convert("L")
    import numpy as np
    arr = np.array(gray, dtype=float)
    return arr.mean()


def _text_colors_for_brightness(brightness):
    """
    Return a dict of CSS color values based on background brightness.
    bright background (>140) → dark text
    dark background (<=140) → light text
    """
    if brightness > 140:
        # Light / mixed background — dark text on a warm frosted light panel
        return {
            "verse":           "#1a1208",
            "transliteration": "#2a2010",
            "source":          "#3a3020",
            "translation":     "#1a1208",
            # Thin white halo keeps letters crisp on any local dark patch
            "verse_shadow":    "0 0 6px rgba(255,255,255,0.5), 0 1px 2px rgba(255,255,255,0.4)",
            "trans_shadow":    "0 0 4px rgba(255,255,255,0.5)",
            "src_shadow":      "0 0 3px rgba(255,255,255,0.4)",
            # Warm frosted light panel behind the text block
            "panel_bg":        "rgba(255, 252, 238, 0.58)",
            "panel_border":    "1px solid rgba(255,255,255,0.70)",
            "top_overlay":     "linear-gradient(to bottom, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0.05) 45%, rgba(0,0,0,0.06) 55%, rgba(0,0,0,0.48) 75%, rgba(0,0,0,0.68) 100%)",
        }
    else:
        # Dark / mixed background — white text on a dark frosted panel
        return {
            "verse":           "#ffffff",
            "transliteration": "rgba(255,252,235,0.97)",
            "source":          "rgba(255,248,210,0.93)",
            "translation":     "#f8f4ea",
            # Dark halo makes letters pop even where a bright patch shows through the panel
            "verse_shadow":    "0 0 8px rgba(0,0,0,0.8), 0 1px 4px rgba(0,0,0,0.6)",
            "trans_shadow":    "0 0 5px rgba(0,0,0,0.75)",
            "src_shadow":      "0 0 4px rgba(0,0,0,0.70)",
            # Dark frosted panel behind the text block
            "panel_bg":        "rgba(0, 0, 0, 0.45)",
            "panel_border":    "1px solid rgba(255,255,255,0.12)",
            "top_overlay":     "linear-gradient(to bottom, rgba(0,0,0,0.20) 0%, rgba(0,0,0,0.10) 45%, rgba(0,0,0,0.08) 55%, rgba(0,0,0,0.48) 75%, rgba(0,0,0,0.68) 100%)",
        }


def _get_font_family(language):
    """Return CSS font-family and Google Font import for the language."""
    if language == "tamil":
        return {
            "verse_family": "'Noto Sans Tamil', sans-serif",
            "google_import": "@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Tamil:wght@400;700&family=Playfair+Display:wght@400;700&family=Lora:ital,wght@0,400;0,700;1,400&display=swap');",
        }
    elif language == "sanskrit":
        return {
            "verse_family": "'Noto Sans Devanagari', sans-serif",
            "google_import": "@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;700&family=Playfair+Display:wght@400;700&family=Lora:ital,wght@0,400;0,700;1,400&display=swap');",
        }
    else:
        return {
            "verse_family": "'Playfair Display', 'Georgia', serif",
            "google_import": "@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Lora:ital,wght@0,400;0,700;1,400&display=swap');",
        }


def _escape_html(text):
    """Escape HTML special characters and preserve newlines."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\n", "<br>")
    return text


def generate_poster_html(day_of_week=None, cycle=None, output_path=None, quote=None):
    """
    Generate an HTML poster file for the given day.

    Args:
        day_of_week: 0=Monday ... 6=Sunday. None = today.
        cycle: Quote rotation index (for testing). Ignored if quote is provided.
        output_path: Custom save path for HTML. None = auto-generate.
        quote: Pre-selected quote dict. If provided, skips get_quote_for_day()
               so that the poster always matches the caption built in daily_runner.

    Returns:
        Path to the saved HTML file.
    """
    if day_of_week is None:
        day_of_week = datetime.now().weekday()

    schedule = DAY_SCHEDULE[day_of_week]
    theme = schedule["theme"]
    day_label = schedule["label"]

    # Get quote — use the pre-selected one if supplied (avoids double-rotation bug)
    if quote is None:
        quote = get_quote_for_day(day_of_week, cycle=cycle)

    # Language comes from the quote itself (rotation picks it dynamically)
    language = quote.get("_language", "english")
    font_config = _get_font_family(language)

    # Generate background and encode as base64 — keep it bright!
    bg = generate_background(theme)
    # Detect brightness BEFORE the saturation/brightness tweaks in _bg_to_base64
    brightness = _compute_bg_brightness(bg)
    tc = _text_colors_for_brightness(brightness)
    print(f"    Background brightness: {brightness:.1f}/255 → "
          f"{'dark' if brightness <= 140 else 'light'} background → "
          f"{'white' if brightness <= 140 else 'dark'} text")
    bg_data_uri = _bg_to_base64(bg)  # _bg_to_base64 applies only gentle darkening

    # Build source attribution
    source_text = f"— {quote['source']}"
    if quote.get("author"):
        source_text = f"— {quote['author']}, {quote['source']}"

    # Prepare content sections
    verse_html = _escape_html(quote["original_text"])
    transliteration_section = ""
    if quote.get("transliteration"):
        trans_escaped = _escape_html(quote["transliteration"])
        transliteration_section = f"<div class='transliteration'>{trans_escaped}</div>"
    translation_section = ""
    if quote.get("english_translation"):
        tl_escaped = _escape_html(quote["english_translation"])
        translation_section = f'<div class="translation">&quot;{tl_escaped}&quot;</div>'
    morning_msg = _escape_html(quote["good_morning_message"])

    # Verse font size — more restrained, elegant
    verse_len = len(quote["original_text"])
    if verse_len > 200:
        verse_size = "1.45rem"
    elif verse_len > 120:
        verse_size = "1.65rem"
    else:
        verse_size = "1.85rem"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
{font_config["google_import"]}

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    width: {POSTER_WIDTH}px;
    height: {POSTER_HEIGHT}px;
    overflow: hidden;
    font-family: 'Lora', 'Georgia', serif;
}}

.poster {{
    width: {POSTER_WIDTH}px;
    height: {POSTER_HEIGHT}px;
    background-image: url('{bg_data_uri}');
    background-size: cover;
    background-position: center;
    display: flex;
    flex-direction: column;
    position: relative;
}}

/* Adaptive overlay — tinted for contrast based on background brightness */
.poster::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: {tc["top_overlay"]};
    z-index: 1;
}}

/* ── Top section: outer container ── */
.top-section {{
    position: relative;
    z-index: 2;
    flex: 0 0 62%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 30px 55px 12px 55px;
    overflow: hidden;
}}

/* Frosted panel — sits behind the text so it reads on any background photo */
.text-panel {{
    background: {tc["panel_bg"]};
    border: {tc["panel_border"]};
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    border-radius: 16px;
    padding: 28px 40px 22px 40px;
    max-width: 92%;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
}}

.verse {{
    font-family: {font_config["verse_family"]};
    font-size: {verse_size};
    font-weight: 400;
    line-height: 1.7;
    color: {tc["verse"]};
    margin-bottom: 14px;
    letter-spacing: 0.3px;
    text-shadow: {tc["verse_shadow"]};
}}

.transliteration {{
    font-family: 'Lora', serif;
    font-size: 1.25rem;
    font-style: italic;
    font-weight: 400;
    color: {tc["transliteration"]};
    line-height: 1.65;
    margin-bottom: 12px;
    text-shadow: {tc["trans_shadow"]};
}}

.source {{
    font-size: 1.0rem;
    color: {tc["source"]};
    letter-spacing: 1.2px;
    margin-bottom: 12px;
    font-family: 'Lora', serif;
    font-style: italic;
    text-transform: uppercase;
    text-shadow: {tc["src_shadow"]};
}}

.translation {{
    font-family: 'Lora', serif;
    font-size: 1.35rem;
    font-weight: 400;
    font-style: italic;
    color: {tc["translation"]};
    line-height: 1.65;
    text-shadow: {tc["trans_shadow"]};
    max-width: 90%;
}}

/* ── Bottom section: Good Morning on darker backdrop ── */
.bottom-section {{
    position: relative;
    z-index: 2;
    flex: 0 0 38%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 10px 65px 50px 65px;
}}

.good-morning {{
    font-family: 'Playfair Display', serif;
    font-size: 2.1rem;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 10px;
    text-shadow: 1px 2px 8px rgba(0,0,0,0.45);
    letter-spacing: 1.5px;
}}

.morning-msg {{
    font-family: 'Lora', serif;
    font-size: 1.3rem;
    font-weight: 400;
    color: rgba(255, 252, 238, 0.96);
    line-height: 1.65;
    text-shadow: 1px 1px 6px rgba(0,0,0,0.6);
    max-width: 84%;
}}
</style>
</head>
<body>
<div class="poster">

    <!-- Top section: verse, transliteration, source, meaning -->
    <div class="top-section">
        <div class="text-panel">
            <div class="verse">{verse_html}</div>
            {transliteration_section}
            <div class="source">{_escape_html(source_text)}</div>
            {translation_section}
        </div>
    </div>

    <!-- Bottom section: Good Morning message -->
    <div class="bottom-section">
        <div class="good-morning">Good Morning!</div>
        <div class="morning-msg">{morning_msg}</div>
    </div>

</div>
</body>
</html>"""

    # Save HTML
    if output_path is None:
        os.makedirs(POSTERS_DIR, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"poster_{day_label.lower()}_{date_str}.html"
        output_path = os.path.join(POSTERS_DIR, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def generate_all_sample_posters(cycle=0):
    """Generate one HTML poster for each day of the week (for testing)."""
    os.makedirs(POSTERS_DIR, exist_ok=True)
    paths = {}
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for weekday in range(7):
        day_name = day_names[weekday]
        filename = f"sample_{day_name.lower()}.html"
        path = os.path.join(POSTERS_DIR, filename)
        generate_poster_html(day_of_week=weekday, cycle=cycle, output_path=path)
        paths[day_name] = path
        print(f"Generated: {day_name} → {path}")
    return paths


if __name__ == "__main__":
    paths = generate_all_sample_posters()
    print(f"\nGenerated {len(paths)} sample posters.")
