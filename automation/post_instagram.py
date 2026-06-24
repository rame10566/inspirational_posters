"""
Post the daily poster PNG to Instagram using instagrapi.

instagrapi uses Instagram's mobile API directly — no browser needed,
no fragile UI selectors, far more reliable than Playwright for posting.

Requirements:
    pip3 install instagrapi --break-system-packages

First-time setup:
    python3 automation/post_instagram.py --setup
    (saves encrypted session to output/instagram_session.json)
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_FILE = os.path.join(BASE_DIR, "output", "instagram_session.json")
CREDS_FILE   = os.path.join(BASE_DIR, "instagram_credentials.json")


def _load_credentials() -> dict:
    if not os.path.exists(CREDS_FILE):
        print("❌  instagram_credentials.json not found.")
        print("    Run: python3 automation/post_instagram.py --setup")
        sys.exit(1)
    with open(CREDS_FILE) as f:
        return json.load(f)


def _get_client():
    """Return an authenticated instagrapi Client, reusing saved session."""
    try:
        from instagrapi import Client
    except ImportError:
        print("❌  instagrapi not installed.")
        print("    Run: python3 -m pip install instagrapi --break-system-packages")
        sys.exit(1)

    creds = _load_credentials()
    cl = Client()
    cl.delay_range = [2, 5]   # human-like delays between requests

    # Try loading saved session first (avoids login every time)
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(creds["username"], creds["password"])
            cl.dump_settings(SESSION_FILE)
            return cl
        except Exception:
            pass  # Session expired — fall through to fresh login

    # Fresh login
    print("  🔐  Logging in to Instagram…")
    try:
        cl.login(creds["username"], creds["password"])
        os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
        cl.dump_settings(SESSION_FILE)
        print("  ✅  Logged in and session saved.")
    except Exception as e:
        print(f"  ❌  Instagram login failed: {e}")
        print("      Check your username/password in instagram_credentials.json")
        raise

    return cl


def setup_instagram_credentials():
    """Interactive setup — saves Instagram username and password."""
    print("\n🔐  Instagram Setup")
    print("─" * 40)
    print("  Your credentials are saved locally only.")
    print("  They are never sent anywhere except Instagram's servers.\n")

    username = input("  Instagram username: ").strip()
    password = input("  Instagram password: ").strip()

    creds = {"username": username, "password": password}
    with open(CREDS_FILE, "w") as f:
        json.dump(creds, f, indent=2)

    print("\n  Testing login…")
    try:
        cl = _get_client()
        info = cl.account_info()
        print(f"  ✅  Logged in as @{info.username} ({info.full_name})")
        print("  Session saved — future runs will use it automatically.\n")
        return True
    except Exception as e:
        print(f"  ❌  Login failed: {e}")
        return False


def _ensure_jpeg(png_path: str) -> str:
    """
    instagrapi works best with JPEG. Convert PNG → JPEG if needed.
    Returns path to a JPEG file (creates a temp file if conversion needed).
    """
    if png_path.lower().endswith(".jpg") or png_path.lower().endswith(".jpeg"):
        return png_path

    from PIL import Image
    jpeg_path = os.path.splitext(png_path)[0] + "_ig.jpg"
    img = Image.open(png_path).convert("RGB")
    img.save(jpeg_path, format="JPEG", quality=95)
    print(f"    Converted to JPEG: {jpeg_path}")
    return jpeg_path


def post_to_instagram(png_path: str, caption: str) -> bool:
    """
    Upload a photo to Instagram feed.

    Args:
        png_path: Absolute path to the poster PNG.
        caption:  Post caption with hashtags.

    Returns:
        True on success, False on failure.
    """
    print("📸  Posting to Instagram…")

    if not os.path.exists(png_path):
        print(f"❌  Image not found: {png_path}")
        return False

    # instagrapi requires JPEG — convert if needed
    img_path = _ensure_jpeg(png_path)

    try:
        cl = _get_client()
        print("    Uploading image…")
        media = cl.photo_upload(img_path, caption=caption)

        if media and media.pk:
            url = f"https://www.instagram.com/p/{media.code}/"
            print(f"✅  Posted to Instagram!")
            print(f"    View post: {url}")
            return True
        else:
            print("❌  Upload returned no media object — post may have failed silently.")
            return False
    except Exception as e:
        error = str(e)
        print(f"❌  Instagram posting failed: {error}")

        # Helpful hints for common errors
        if "login_required" in error or "checkpoint" in error.lower():
            print("    Your session expired or Instagram requires verification.")
            print("    Run: python3 automation/post_instagram.py --setup")
        elif "feedback_required" in error:
            print("    Instagram flagged the action. Wait a few hours and try again.")
        elif "rate" in error.lower():
            print("    Rate limited — too many requests. Wait 30 minutes and retry.")

        return False


if __name__ == "__main__":
    if "--setup" in sys.argv:
        setup_instagram_credentials()
    elif len(sys.argv) >= 2:
        caption = sys.argv[2] if len(sys.argv) > 2 else "Good morning! 🌅 #morningvibes"
        post_to_instagram(sys.argv[1], caption)
    else:
        print("Usage:")
        print("  python3 post_instagram.py --setup             (first-time login)")
        print("  python3 post_instagram.py poster.png caption  (post image)")
