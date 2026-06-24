"""
Convert the poster HTML file to a PNG image using Playwright.

Key challenge: Google Fonts (Noto Sans Tamil, Noto Sans Devanagari) must fully
load before screenshotting, otherwise Sanskrit/Tamil shows as boxes.

We handle this by:
  1. Waiting for networkidle (all font requests complete)
  2. Waiting an extra 3s for font rendering to finish
  3. Verifying fonts actually loaded via document.fonts.ready

Requirements:
    pip3 install playwright --break-system-packages
    python3 -m playwright install chromium
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import POSTER_WIDTH, POSTER_HEIGHT


def take_screenshot(html_path: str, png_path: str = None) -> str:
    """
    Screenshot an HTML poster file and save as PNG.

    Args:
        html_path: Absolute path to the .html poster file.
        png_path:  Where to save the PNG. Defaults to same location as HTML.

    Returns:
        Absolute path to the saved PNG.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # Raise a regular exception so daily_runner.py's try/except can catch it
        # and continue gracefully rather than killing the whole process.
        raise RuntimeError(
            "Playwright not installed.\n"
            "    Run: pip3 install playwright --break-system-packages\n"
            "    Then: python3 -m playwright install chromium"
        )

    if png_path is None:
        png_path = os.path.splitext(html_path)[0] + ".png"

    abs_html = os.path.abspath(html_path)
    file_url = f"file://{abs_html}"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--font-render-hinting=none"],   # crisper font rendering
        )
        page = browser.new_page(viewport={
            "width":  POSTER_WIDTH,
            "height": POSTER_HEIGHT,
        })

        # Navigate and wait for network to go idle (fonts downloaded)
        page.goto(file_url, wait_until="networkidle", timeout=30000)

        # Wait for browser's font loading promise to resolve
        page.evaluate("() => document.fonts.ready")

        # Extra buffer — font rendering can lag slightly after loading
        page.wait_for_timeout(3000)

        # Take the screenshot
        page.screenshot(
            path=png_path,
            clip={"x": 0, "y": 0, "width": POSTER_WIDTH, "height": POSTER_HEIGHT},
        )
        browser.close()

    print(f"📸  Screenshot saved: {png_path}")
    return png_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 screenshot_poster.py path/to/poster.html [output.png]")
        sys.exit(1)
    html = sys.argv[1]
    png  = sys.argv[2] if len(sys.argv) > 2 else None
    take_screenshot(html, png)
