"""
Post the daily poster PNG to WhatsApp Status via web.whatsapp.com + Playwright.

First-time setup:
    python3 automation/post_whatsapp.py --setup

Requirements:
    pip3 install playwright --break-system-packages
    python3 -m playwright install chromium
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_DIR = os.path.join(BASE_DIR, "output", "browser_sessions", "whatsapp")
DEBUG_DIR   = os.path.join(BASE_DIR, "output", "whatsapp_debug")


def _screenshot(page, name):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    path = os.path.join(DEBUG_DIR, f"{name}.png")
    try:
        page.screenshot(path=path)
        print(f"    📷  Screenshot: output/whatsapp_debug/{name}.png")
    except Exception:
        pass


def _get_context(playwright):
    os.makedirs(SESSION_DIR, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        user_data_dir=SESSION_DIR,
        headless=False,
        viewport={"width": 1400, "height": 900},
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )


def setup_whatsapp_session():
    """Open WhatsApp Web for first-time QR scan."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌  Playwright not installed.")
        print("    Run: python3 -m pip install playwright --break-system-packages")
        return False

    print("\n📱  WhatsApp Web — First Time Setup")
    print("─" * 40)
    print("  1. A browser window will open showing a QR code")
    print("  2. On your phone: WhatsApp → Settings → Linked Devices → Link a Device")
    print("  3. Scan the QR code")
    print("  4. Wait for your chats to load")
    print("  5. Come back here and press Enter\n")

    with sync_playwright() as p:
        context = _get_context(p)
        page = context.new_page()
        page.goto("https://web.whatsapp.com/")
        input("  ✅  Chats loaded? Press Enter to save session…")
        context.close()

    print("  ✅  WhatsApp session saved!\n")
    return True


def post_whatsapp_status(png_path: str) -> bool:
    """Post an image to WhatsApp Status."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌  Playwright not installed.")
        return False

    if not os.path.exists(png_path):
        print(f"❌  Image not found: {png_path}")
        return False

    print("💬  Posting to WhatsApp Status…")

    with sync_playwright() as p:
        context = _get_context(p)
        page = context.new_page()

        try:
            # ── Step 1: Load WhatsApp Web ────────────────────────────────────
            print("    Loading WhatsApp Web…")
            page.goto("https://web.whatsapp.com/", timeout=90000,
                      wait_until="domcontentloaded")

            try:
                page.wait_for_selector(
                    '#pane-side, [data-testid="chatlist-header"], '
                    'div[aria-label="Chat list"]',
                    timeout=60000,
                )
                print("    ✅  Logged in")
            except Exception:
                _screenshot(page, "01_login_failed")
                print("❌  WhatsApp didn't load. Session may have expired.")
                print("    Run: python3 automation/post_whatsapp.py --setup")
                context.close()
                return False

            time.sleep(3)
            _screenshot(page, "02_loaded")

            # ── Step 2: Click the Status nav button ──────────────────────────
            # From DOM analysis: the Status nav button is BUTTON[aria-label="Status"]
            # at approximately x=12, y=56 (center x=32, y=76) in the left icon bar.
            # We click it and then proceed WITHOUT a strict "_in_status_view()" gate,
            # because the Status panel's internal data-testid attributes are version-
            # dependent and hard to predict. Success is confirmed when the Add Status
            # button is found in Step 3.

            print("    Clicking Status tab…")
            status_clicked = False

            # Primary: CSS selector for the exact button identified in DOM analysis
            for sel in [
                'button[aria-label="Status"]',
                'button[aria-label="Updates"]',
                '[data-testid="status-tab"]',
                'span[data-icon="status-tab"]',
                'span[data-icon="status"]',
            ]:
                try:
                    el = page.locator(sel).first
                    el.wait_for(state="visible", timeout=3000)
                    el.click()
                    status_clicked = True
                    print(f"    ✅  Clicked ({sel})")
                    break
                except Exception:
                    continue

            # Fallback: Playwright role-based locators
            if not status_clicked:
                for locator in [
                    page.get_by_role("button", name="Status"),
                    page.get_by_role("button", name="Updates"),
                    page.get_by_label("Status"),
                    page.get_by_label("Updates"),
                ]:
                    try:
                        locator.wait_for(state="visible", timeout=2000)
                        locator.click()
                        status_clicked = True
                        print("    ✅  Clicked (semantic locator)")
                        break
                    except Exception:
                        continue

            # Last resort: coordinate click on center of Status button (x=32, y=76)
            if not status_clicked:
                print("    Trying coordinate click at Status button position (32, 76)…")
                try:
                    page.mouse.click(32, 76)
                    status_clicked = True
                    print("    ✅  Clicked (coordinate 32, 76)")
                except Exception:
                    pass

            if not status_clicked:
                _screenshot(page, "03_status_click_failed")
                print("❌  Could not click Status tab at all.")
                context.close()
                return False

            # Wait for the Status panel to render
            time.sleep(3)
            _screenshot(page, "04_after_status_click")

            # ── Step 3: Click ⊕ and upload image ─────────────────────────────
            # The ⊕ button is in the Status panel header top-right (confirmed in
            # screenshot at approximately x=387, y=31 for a 1400×900 viewport).
            # IMPORTANT: Do NOT click the "My status" row — that opens a
            # "Select chats" sharing dialog, not the add-new-status flow.
            #
            # After clicking ⊕ WhatsApp may either:
            #   A) Open a file chooser directly
            #   B) Show a type-selection menu (Photo/Video / Text / etc.)
            #      → we then click the Photo/video option from that menu

            print("    Clicking ⊕ / My status button…")
            file_uploaded = False

            # Two confirmed entry points (from screenshot analysis):
            #   A) ⊕ header button      — coordinate (387, 31)
            #   B) Green + circle       — coordinate (128, 109) on "My status" avatar
            #
            # IMPORTANT: click each entry point only ONCE.
            # Clicking twice can open-then-close the type-selection menu.
            # After clicking, wait 2 s then check what appeared:
            #   - A type-selection menu (Photo / Video / Text) → click Photo
            #   - A file input         → set it directly
            #   - A file chooser dialog → set it

            def _upload_via_entry(click_coord, label):
                """Click one entry point, handle menu or direct file-chooser."""
                print(f"    Trying entry point: {label} …")
                page.mouse.click(*click_coord)
                time.sleep(2)
                _screenshot(page, f"04b_{label}")

                # Dump what appeared so we can see it in logs
                menu_items = page.evaluate("""() => {
                    const items = [];
                    for (const el of document.querySelectorAll(
                            'li,div[role="menuitem"],[role="option"],[role="listitem"]')) {
                        const lbl  = el.getAttribute('aria-label') || '';
                        const txt  = (el.innerText || '').trim().substring(0, 40);
                        const r    = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0 && (lbl || txt)) {
                            items.push({lbl, txt,
                                x: Math.round(r.x), y: Math.round(r.y)});
                        }
                    }
                    return items.slice(0, 20);
                }""")
                if menu_items:
                    print(f"    Menu/list items visible: {menu_items[:8]}")

                # ── Case A: type-selection menu appeared → click Photo option ──
                photo_selectors = [
                    '[aria-label="Photo & video"]',
                    '[aria-label="Photo/video"]',
                    '[aria-label="Photos & Videos"]',
                    '[aria-label="Photo or video"]',
                    'li[aria-label*="hoto"]',
                    'div[role="menuitem"][aria-label*="hoto"]',
                ]
                for sel in photo_selectors:
                    try:
                        el = page.locator(sel).first
                        el.wait_for(state="visible", timeout=2000)
                        with page.expect_file_chooser(timeout=8000) as fc:
                            el.click()
                        fc.value.set_files(png_path)
                        print(f"    ✅  Uploaded via menu → photo ({sel})")
                        return True
                    except Exception:
                        continue

                # ── Case B: menu uses text labels not aria — try text matching ──
                for text in ["Photo", "Video", "Photos & videos", "Photo & video"]:
                    try:
                        el = page.get_by_role("menuitem", name=text)
                        el.wait_for(state="visible", timeout=1500)
                        with page.expect_file_chooser(timeout=8000) as fc:
                            el.click()
                        fc.value.set_files(png_path)
                        print(f"    ✅  Uploaded via menu text ({text})")
                        return True
                    except Exception:
                        continue

                # ── Case C: direct file chooser appeared without a menu ────────
                try:
                    with page.expect_file_chooser(timeout=3000) as fc:
                        pass   # already appeared — just capture it
                    fc.value.set_files(png_path)
                    print("    ✅  Uploaded via direct file chooser")
                    return True
                except Exception:
                    pass

                # ── Case D: hidden file input became attached ──────────────────
                try:
                    fi = page.locator('input[type="file"]').first
                    fi.wait_for(state="attached", timeout=3000)
                    fi.set_input_files(png_path)
                    print("    ✅  Uploaded via hidden file input")
                    return True
                except Exception:
                    pass

                return False

            # Try ⊕ header button first, then green + circle on avatar
            for coord, lbl in [((387, 31), "plus_header"),
                                ((128, 109), "my_status_circle")]:
                if _upload_via_entry(coord, lbl):
                    file_uploaded = True
                    break
                # If this entry point did nothing useful, press Escape to reset
                # before trying the next one
                try:
                    page.keyboard.press("Escape")
                    time.sleep(1)
                except Exception:
                    pass

            if not file_uploaded:
                _screenshot(page, "05_upload_failed")
                print("❌  Could not upload image to status.")
                print("    Check 04_after_status_click.png — status panel state")
                print("    Check 04b_after_plus_click.png — state after ⊕ was clicked")
                # Diagnostic: dump all visible interactive elements
                try:
                    dom_info = page.evaluate("""() => {
                        const items = [];
                        for (const el of document.querySelectorAll(
                                'button,[role="button"],[aria-label],[data-testid]')) {
                            const lbl = el.getAttribute('aria-label') || '';
                            const tid = el.getAttribute('data-testid') || '';
                            const ttl = el.getAttribute('title') || '';
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0
                                    && r.x < 1400 && r.y < 900
                                    && (lbl || tid || ttl)) {
                                items.push({
                                    tag: el.tagName,
                                    lbl: lbl.substring(0, 40),
                                    tid: tid.substring(0, 40),
                                    ttl: ttl.substring(0, 40),
                                    x: Math.round(r.x), y: Math.round(r.y),
                                    w: Math.round(r.width), h: Math.round(r.height)
                                });
                            }
                        }
                        // Sort by y position for easier reading
                        items.sort((a, b) => a.y - b.y);
                        return items.slice(0, 40);
                    }""")
                    print("\n    Visible interactive elements (sorted by y position):")
                    for item in dom_info:
                        print(f"      {item}")
                except Exception:
                    pass
                context.close()
                return False

            time.sleep(4)
            _screenshot(page, "06_image_preview")

            # ── Step 4: Send ─────────────────────────────────────────────────
            # The image editor is now open with the poster visible.
            # The green circular Send button is at the bottom-right of the editor.
            # DO NOT close any dialogs here — the editor IS the correct state.
            print("    Looking for Send button in image editor…")

            sent = False

            # Primary send selectors for the image editor
            send_selectors = [
                '[data-testid="status-send-btn"]',
                '[data-testid="send"]',
                '[data-testid="media-forward-btn"]',
                '[data-testid="forward"]',
                'span[data-icon="send-light"]',
                'span[data-icon="send"]',
                'span[data-icon="forward"]',
                'button[aria-label="Send"]',
                '[aria-label="Send"]',
                '[aria-label="Send status update"]',
                '[aria-label="Send status"]',
                '[aria-label="Share"]',
                '[aria-label="Next"]',
            ]

            for sel in send_selectors:
                try:
                    el = page.locator(sel).first
                    el.wait_for(state="visible", timeout=5000)
                    el.click()
                    sent = True
                    print(f"    ✅  Send clicked ({sel})")
                    break
                except Exception:
                    continue

            if not sent:
                try:
                    send_btn = page.get_by_role("button", name="Send")
                    send_btn.wait_for(state="visible", timeout=3000)
                    send_btn.click()
                    sent = True
                    print("    ✅  Send clicked (semantic)")
                except Exception:
                    pass

            # Coordinate fallback — green Send circle is at bottom-right of the
            # full-screen image editor. At 1400×900 viewport it sits near (1358, 860).
            if not sent:
                print("    Trying coordinate click on Send button (1358, 860)…")
                try:
                    page.mouse.click(1358, 860)
                    time.sleep(2)
                    sent = True
                    print("    ✅  Send clicked (coordinate 1358, 860)")
                except Exception:
                    pass

            if not sent:
                _screenshot(page, "07_send_not_found")
                print("❌  Could not find Send button.")
                print("    Check 06_image_preview.png and 07_send_not_found.png")
                # Dump all visible interactive elements with icons
                try:
                    btns = page.evaluate("""() => {
                        const items = [];
                        for (const el of document.querySelectorAll(
                                'button,[role="button"],span[data-icon]')) {
                            const lbl = el.getAttribute('aria-label') || '';
                            const ico = el.getAttribute('data-icon') || '';
                            const tid = el.getAttribute('data-testid') || '';
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0 &&
                                    r.x >= 0 && r.y >= 0 &&
                                    r.x < 1400 && r.y < 900) {
                                items.push({tag: el.tagName,
                                    lbl: lbl.substring(0,40),
                                    ico: ico.substring(0,30),
                                    tid: tid.substring(0,40),
                                    x: Math.round(r.x), y: Math.round(r.y)});
                            }
                        }
                        items.sort((a,b) => a.y - b.y);
                        return items.slice(0,35);
                    }""")
                    print("    Visible buttons/icons:")
                    for b in btns:
                        print(f"      {b}")
                except Exception:
                    pass
                context.close()
                return False

            # ── Wait for upload to finish ─────────────────────────────────
            # The "My status" row shows "Sending…" while the image is uploading.
            # We wait up to 60 s for that text to disappear before closing the
            # browser — closing too early was cutting off the upload mid-way.
            print("    Waiting for upload to complete…")
            try:
                # Option A: wait for "Sending…" text to disappear from the status list
                sending_locator = page.locator("text=Sending…").or_(
                    page.locator("text=Sending...")
                )
                # First confirm it's visible (it appears right after send)
                try:
                    sending_locator.first.wait_for(state="visible", timeout=5000)
                    # Then wait for it to go away (upload done)
                    sending_locator.first.wait_for(state="hidden", timeout=60000)
                    print("    ✅  Upload confirmed (Sending… disappeared)")
                except Exception:
                    # "Sending…" may have disappeared too fast — that's fine
                    pass

                # Option B: belt-and-suspenders — just wait a bit longer regardless
                time.sleep(5)

            except Exception as e:
                print(f"    ⚠️  Upload wait error: {e}")
                time.sleep(10)   # fallback: wait 10 s minimum

            _screenshot(page, "08_after_send")
            print("✅  Posted to WhatsApp Status!")
            context.close()
            return True

        except Exception as e:
            print(f"❌  WhatsApp posting failed: {e}")
            _screenshot(page, "error")
            context.close()
            return False


if __name__ == "__main__":
    if "--setup" in sys.argv:
        setup_whatsapp_session()
    elif len(sys.argv) >= 2:
        post_whatsapp_status(sys.argv[1])
    else:
        print("Usage:")
        print("  python3 post_whatsapp.py --setup       (first-time QR scan)")
        print("  python3 post_whatsapp.py poster.png    (post to status)")
