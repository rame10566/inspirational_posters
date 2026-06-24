"""Configuration for the Daily Inspirational Poster Workflow."""

import os

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUOTES_DIR = os.path.join(BASE_DIR, "quotes")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
POSTERS_DIR = os.path.join(OUTPUT_DIR, "posters")

# Poster dimensions (Instagram square)
POSTER_WIDTH = 1080
POSTER_HEIGHT = 1080

# Fonts
FONTS = {
    "english_title": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "english_body": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "script": "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
}

# Day-of-week schedule (0=Monday ... 6=Sunday in Python's weekday())
# Language is NO LONGER fixed per day — it rotates automatically so the same
# language never appears on consecutive days.  Only the background theme is
# fixed here; everything else is determined at runtime.
DAY_SCHEDULE = {
    0: {"theme": "misty_tree",    "label": "Monday"},
    1: {"theme": "beach_sunrise", "label": "Tuesday"},
    2: {"theme": "lotus_pond",    "label": "Wednesday"},
    3: {"theme": "sunrise_path",  "label": "Thursday"},
    4: {"theme": "flower_meadow", "label": "Friday"},
    5: {"theme": "mountain_lake", "label": "Saturday"},
    6: {"theme": "yoga_dawn",     "label": "Sunday"},
}

# The three language pools that rotate across days.
# Order matters only as a tiebreaker when all are equally available.
LANGUAGES = ["english", "tamil", "sanskrit"]

# Legacy — kept so any existing code that imports DAY_TAGS doesn't hard-crash.
# New code should use quote_database.get_language_for_today() instead.
DAY_TAGS = {}

# Color palettes for backgrounds
PALETTES = {
    "sunrise": [(25, 10, 40), (120, 40, 80), (200, 80, 50), (240, 160, 60), (255, 220, 140)],
    "dawn": [(10, 15, 45), (40, 60, 100), (80, 120, 160), (160, 190, 210), (220, 230, 240)],
    "golden": [(40, 20, 10), (120, 60, 20), (200, 120, 40), (240, 180, 80), (255, 230, 160)],
    "lotus": [(20, 10, 30), (80, 30, 60), (160, 60, 100), (200, 120, 140), (240, 180, 200)],
    "forest": [(10, 25, 15), (30, 60, 40), (60, 100, 70), (120, 160, 100), (180, 210, 160)],
    "ocean": [(5, 15, 40), (20, 50, 80), (40, 100, 140), (80, 160, 200), (160, 210, 230)],
}

# ── Unsplash Photo API ──────────────────────────────────────────────────────
# Get a free key at https://unsplash.com/developers → "New Application"
# Paste your Access Key below (the "Access Key", NOT the Secret Key)
UNSPLASH_ACCESS_KEY = "ke5pdZwMk8MTvSl9hc9fejmzP4zKWdIX1m9EFmjK8L0"   # ← paste your key here

# Search queries per theme — tuned for beautiful morning/nature shots
UNSPLASH_QUERIES = {
    "yoga_dawn":      "golden sunrise yoga meditation peaceful morning",
    "misty_tree":     "misty forest morning fog sunlight trees",
    "beach_sunrise":  "beach sunrise golden hour ocean morning calm",
    "lotus_pond":     "lotus pond reflection morning serene nature",
    "sunrise_path":   "forest path sunlight golden morning peaceful",
    "flower_meadow":  "flower meadow morning sunlight wildflowers",
    "mountain_lake":  "mountain lake morning mist reflection calm",
}

# Local cache folder for downloaded background photos
BG_CACHE_DIR = os.path.join(OUTPUT_DIR, "bg_cache")

# Schedule
SCHEDULE_CRON = "0 19 * * *"  # Daily at 7:00 PM
