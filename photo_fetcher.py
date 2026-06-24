"""
Unsplash photo fetcher for beautiful scenic backgrounds.

- Fetches a random high-quality photo for each theme from Unsplash API
- Caches photos locally so they're reused across runs (saves API quota)
- Falls back to programmatic background if API key missing or request fails
- Free tier: 50 requests/hour — more than enough for daily use

Setup:
  1. Go to https://unsplash.com/developers → "New Application"
  2. Copy your "Access Key"
  3. Paste it in config.py → UNSPLASH_ACCESS_KEY = "your_key_here"
"""

import os
import json
import random
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from PIL import Image
import io

from config import (
    UNSPLASH_ACCESS_KEY,
    UNSPLASH_QUERIES,
    BG_CACHE_DIR,
    POSTER_WIDTH,
    POSTER_HEIGHT,
)

UNSPLASH_API_BASE = "https://api.unsplash.com"
CACHE_EXPIRY_DAYS = 1   # Re-fetch daily so every poster gets a fresh photo


def _cache_path(theme: str) -> str:
    """Return the local cache file path for a theme's photo."""
    os.makedirs(BG_CACHE_DIR, exist_ok=True)
    return os.path.join(BG_CACHE_DIR, f"{theme}.jpg")


def _cache_meta_path(theme: str) -> str:
    """Return the cache metadata JSON path (stores fetch date + photo info)."""
    os.makedirs(BG_CACHE_DIR, exist_ok=True)
    return os.path.join(BG_CACHE_DIR, f"{theme}_meta.json")


def _is_cache_valid(theme: str) -> bool:
    """Return True if a cached photo exists and is not expired."""
    img_path = _cache_path(theme)
    meta_path = _cache_meta_path(theme)
    if not os.path.exists(img_path) or not os.path.exists(meta_path):
        return False
    with open(meta_path) as f:
        meta = json.load(f)
    fetched_at = datetime.fromisoformat(meta.get("fetched_at", "2000-01-01"))
    return (datetime.now() - fetched_at) < timedelta(days=CACHE_EXPIRY_DAYS)


def _save_cache_meta(theme: str, photo_info: dict):
    """Save metadata about the cached photo."""
    meta = {
        "fetched_at": datetime.now().isoformat(),
        "photographer": photo_info.get("user", {}).get("name", "Unknown"),
        "unsplash_url": photo_info.get("links", {}).get("html", ""),
        "description": photo_info.get("description") or photo_info.get("alt_description", ""),
    }
    with open(_cache_meta_path(theme), "w") as f:
        json.dump(meta, f, indent=2)


# Fallback queries — tried if the primary query returns no usable result
UNSPLASH_FALLBACK_QUERIES = {
    "flower_meadow":  "spring flowers nature morning light",
    "beach_sunrise":  "ocean sunrise coast morning golden",
    "mountain_lake":  "lake mountains reflection serene",
    "lotus_pond":     "pond water lily nature morning",
    "misty_tree":     "forest mist morning light trees",
    "sunrise_path":   "path nature morning sunlight golden",
    "yoga_dawn":      "sunrise dawn peaceful morning sky",
}


def _fetch_unsplash_photo(theme: str) -> bool:
    """
    Fetch a random Unsplash photo for the theme and cache it.
    Tries the primary query first; falls back to an alternative if it fails.

    Returns True on success, False on failure.
    """
    if not UNSPLASH_ACCESS_KEY:
        print("⚠️  No Unsplash API key set. Add your key to config.py → UNSPLASH_ACCESS_KEY")
        return False

    primary_query  = UNSPLASH_QUERIES.get(theme, "beautiful morning nature sunrise")
    fallback_query = UNSPLASH_FALLBACK_QUERIES.get(theme, "nature morning sunrise peaceful")
    queries_to_try = [primary_query, fallback_query]

    for attempt, query in enumerate(queries_to_try, 1):
        success = _try_fetch_with_query(theme, query)
        if success:
            return True
        if attempt < len(queries_to_try):
            print(f"ℹ️  Primary query failed for '{theme}', trying fallback query…")

    return False


def _try_fetch_with_query(theme: str, query: str) -> bool:
    """Attempt a single Unsplash fetch with the given query. Returns True on success."""
    encoded_query = urllib.parse.quote(query)

    # Unsplash random photo endpoint — squarish orientation for 1080×1080
    url = (
        f"{UNSPLASH_API_BASE}/photos/random"
        f"?query={encoded_query}"
        f"&orientation=squarish"
        f"&content_filter=high"
    )

    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"⚠️  Unsplash API error {e.code}: {e.reason}")
        return False
    except Exception as e:
        print(f"⚠️  Unsplash request failed: {e}")
        return False

    # Get the highest-resolution URL available (regular ≈ 1080px wide)
    photo_url = data.get("urls", {}).get("regular") or data.get("urls", {}).get("full")
    if not photo_url:
        print("⚠️  No photo URL in Unsplash response")
        return False

    # Download the image
    try:
        with urllib.request.urlopen(photo_url, timeout=30) as img_resp:
            img_data = img_resp.read()
    except Exception as e:
        print(f"⚠️  Failed to download photo: {e}")
        return False

    # Open, crop to square, resize to poster size, save
    try:
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        img = _crop_to_square(img)
        img = img.resize((POSTER_WIDTH, POSTER_HEIGHT), Image.LANCZOS)
        img.save(_cache_path(theme), format="JPEG", quality=92)
        _save_cache_meta(theme, data)
        photographer = data.get("user", {}).get("name", "Unknown")
        print(f"✅  Downloaded Unsplash photo for '{theme}' (query: '{query}') by {photographer}")
        return True
    except Exception as e:
        print(f"⚠️  Failed to process photo: {e}")
        return False


def _crop_to_square(img: Image.Image) -> Image.Image:
    """Centre-crop an image to a square."""
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def get_background_photo(theme: str) -> Image.Image | None:
    """
    Return a Pillow Image for the theme's background photo.

    Flow:
      1. If valid cached photo exists → load and return it
      2. Otherwise fetch fresh photo from Unsplash → cache → return it
      3. If API unavailable / no key → return None (caller falls back to programmatic bg)
    """
    if not _is_cache_valid(theme):
        success = _fetch_unsplash_photo(theme)
        if not success:
            # Try loading stale cache if it exists (better than nothing)
            if os.path.exists(_cache_path(theme)):
                print(f"ℹ️  Using stale cached photo for '{theme}'")
            else:
                return None

    try:
        img = Image.open(_cache_path(theme)).convert("RGB")
        # Ensure correct size (in case cache is from different run)
        if img.size != (POSTER_WIDTH, POSTER_HEIGHT):
            img = img.resize((POSTER_WIDTH, POSTER_HEIGHT), Image.LANCZOS)
        return img
    except Exception as e:
        print(f"⚠️  Could not load cached photo for '{theme}': {e}")
        return None


def refresh_all_photos(force: bool = False):
    """Pre-fetch / refresh Unsplash photos for all 7 themes."""
    from config import UNSPLASH_QUERIES
    print(f"\n📸  Refreshing background photos from Unsplash...\n")
    for theme in UNSPLASH_QUERIES:
        if force and os.path.exists(_cache_path(theme)):
            os.remove(_cache_path(theme))
            if os.path.exists(_cache_meta_path(theme)):
                os.remove(_cache_meta_path(theme))
        get_background_photo(theme)
    print("\nDone.\n")


def get_cache_status() -> dict:
    """Return a summary of which themes have valid cached photos."""
    from config import UNSPLASH_QUERIES
    status = {}
    for theme in UNSPLASH_QUERIES:
        valid = _is_cache_valid(theme)
        meta_path = _cache_meta_path(theme)
        photographer = ""
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            photographer = meta.get("photographer", "")
        status[theme] = {
            "cached": os.path.exists(_cache_path(theme)),
            "valid": valid,
            "photographer": photographer,
        }
    return status


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    if not UNSPLASH_ACCESS_KEY:
        print("\n❌  Please set UNSPLASH_ACCESS_KEY in config.py first.")
        print("    Get a free key at: https://unsplash.com/developers\n")
    else:
        refresh_all_photos(force=force)
        print("\nCache status:")
        for theme, info in get_cache_status().items():
            icon = "✅" if info["valid"] else ("⚠️ " if info["cached"] else "❌")
            print(f"  {icon} {theme:<18} {info['photographer']}")
