"""
Local Flask approval server.

Started automatically by daily_runner.py each morning after the poster is generated.
Keeps running in the background until you click Approve or Skip in the email / browser.

Routes:
  GET /         → Nice approval page showing the poster + buttons
  GET /approve  → Posts to Instagram + WhatsApp, then shuts down
  GET /skip     → Marks skipped, shuts down
  GET /status   → JSON status check

Usage:
  python3 approval_server.py path/to/pending.json
"""

import os
import sys
import json
import uuid
import socket
import threading
import subprocess
from datetime import datetime
from functools import wraps

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PORT = 5678
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_local_ip() -> str:
    """Detect the Mac's LAN IP address so other devices can reach the server."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def _load_pending(pending_path: str) -> dict:
    with open(pending_path) as f:
        return json.load(f)


def _update_pending(pending_path: str, update: dict):
    data = _load_pending(pending_path)
    data.update(update)
    with open(pending_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_server(pending_path: str):
    """Start the Flask approval server."""
    import signal

    # Clean exit on SIGTERM (sent by noon-stop plist or manual kill).
    # Exiting with code 0 prevents KeepAlive from restarting us after an
    # intentional shutdown.
    signal.signal(signal.SIGTERM, lambda s, f: os._exit(0))

    try:
        from flask import Flask, send_file, jsonify, redirect
    except ImportError:
        print("❌  Flask not installed. Run: pip3 install flask")
        sys.exit(1)

    app = Flask(__name__)
    shutdown_event = threading.Event()

    def _delayed_shutdown(seconds=5, wait_for_thread=None):
        """Shut down the server after response loads, optionally waiting for a posting thread."""
        def _do():
            import time
            time.sleep(seconds)          # let the browser receive the response first
            if wait_for_thread is not None:
                print("⏳  Waiting for posting to finish before shutting down…")
                wait_for_thread.join(timeout=180)  # wait up to 3 minutes for posting
            # Kill cloudflared tunnel so it doesn't linger after the server is gone
            try:
                subprocess.run(["pkill", "-f", "cloudflared"], check=False)
                print("🔒  Cloudflared tunnel closed.")
            except Exception:
                pass
            shutdown_event.set()
            time.sleep(1)
            os._exit(0)
        threading.Thread(target=_do, daemon=True).start()

    # ── SSL certificate ───────────────────────────────────────────────────────
    from automation.ssl_helper import ensure_cert, print_trust_instructions
    ssl_paths = ensure_cert()
    USE_HTTPS = ssl_paths is not None
    SCHEME    = "https" if USE_HTTPS else "http"

    LOCAL_IP = _get_local_ip()

    def _base_url():
        return f"{SCHEME}://{LOCAL_IP}:{PORT}"

    # ── Mutable server state — populated once pending file is ready ───────────
    # Start with empty/sentinel values; _reload_state() fills them in
    state = {
        "ready":       False,   # True once pending_approval.json is loaded
        "png_path":    "",
        "caption":     "",
        "quote":       {},
        "day_label":   "",
        "token":       "",
    }

    def _reload_state():
        """Load / refresh state from pending_approval.json. Returns True if ready."""
        if not os.path.exists(pending_path):
            return False
        try:
            pending = _load_pending(pending_path)
        except Exception:
            return False
        state["ready"]     = True
        state["png_path"]  = pending.get("png_path", "")
        state["caption"]   = pending.get("caption", "")
        state["quote"]     = pending.get("quote", {})
        state["day_label"] = pending.get("day_label", "")
        state["token"]     = pending.get("session_token", "")
        return True

    # Try loading immediately (poster already exists from earlier today)
    _reload_state()

    if state["ready"]:
        print(f"\n📱  Approval page reachable on your network at:")
        tok_url = f"{_base_url()}/?token={state['token']}"
        print(f"    {tok_url}\n")
    else:
        print(f"\n⏳  No pending poster yet — server is waiting for daily_runner.py …")
        print(f"    Approval server running on {_base_url()} (waiting mode)\n")

    # ── Background poller: watch for pending_approval.json ───────────────────
    def _poll_for_pending():
        import time
        while not state["ready"]:
            time.sleep(30)
            if _reload_state():
                print(f"\n✅  Poster ready — approval page now live at:")
                print(f"    {_base_url()}/?token={state['token']}\n")
                break

    if not state["ready"]:
        threading.Thread(target=_poll_for_pending, daemon=True).start()

    # ── Helper: current session token (may update after poster is generated) ──
    def _session_token() -> str:
        return state["token"]

    def _tok(path: str) -> str:
        """Append the session token to a URL path."""
        tok = _session_token()
        if not tok:
            return f"{_base_url()}{path}"
        sep = "&" if "?" in path else "?"
        return f"{_base_url()}{path}{sep}token={tok}"

    def require_token(f):
        """Decorator: reject requests that don't carry the correct token."""
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import request, Response
            # Always re-read the token from disk so a freshly-written
            # pending_approval.json (e.g. after a re-run) is picked up
            # immediately without waiting for the 30-second poller.
            _reload_state()
            # If poster isn't ready yet, show waiting page for all token-gated routes
            if not state["ready"]:
                return Response(_waiting_page_html(), mimetype="text/html")
            tok = _session_token()
            if tok and request.args.get("token") != tok:
                return Response(
                    """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Not authorised</title></head><body style="font-family:Georgia,serif;
text-align:center;padding:60px;background:#fff8f0;">
<h2 style="color:#c0392b;">🔒 Not authorised</h2>
<p style="color:#777;">Use the link from your morning email to access this page.</p>
</body></html>""",
                    status=403, mimetype="text/html"
                )
            return f(*args, **kwargs)
        return decorated

    # ── Waiting page (shown before daily_runner creates the pending file) ─────
    def _waiting_page_html():
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>🌅 Morning Poster — Waiting…</title>
  <meta http-equiv="refresh" content="30">
  <style>
    body {{ font-family: Georgia, serif; background: #fff8f0; display: flex;
            align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
    .box {{ text-align: center; padding: 48px 40px; background: white; border-radius: 16px;
            box-shadow: 0 4px 30px rgba(0,0,0,0.08); max-width: 420px; }}
    h2 {{ color: #8b4513; margin-bottom: 12px; }}
    p  {{ color: #999; line-height: 1.7; margin: 0; }}
    .spinner {{ font-size: 2.8rem; animation: spin 4s linear infinite; display: inline-block;
                margin-bottom: 16px; }}
    @keyframes spin {{ from {{ transform: rotate(0deg) }} to {{ transform: rotate(360deg) }} }}
  </style>
</head>
<body>
<div class="box">
  <div class="spinner">🌅</div>
  <h2>Getting your poster ready…</h2>
  <p>Your daily poster is being prepared for {datetime.now().strftime("%A, %d %B")}.<br>
  This page refreshes every 30 seconds — it will update automatically once the poster is ready.</p>
</div>
</body>
</html>"""

    # ── Backward-compat: day label helper ────────────────────────────────────
    def _day():
        return state.get("day_label", datetime.now().strftime("%A"))

    # ── Approval page HTML ───────────────────────────────────────────────────
    def approval_page_html(message="", message_color="#333"):
        cur_quote   = state["quote"]
        cur_caption = state["caption"]
        cur_png     = state["png_path"]
        cur_token   = _session_token()

        verse   = cur_quote.get("original_text", "")[:160].replace("\n", " ")
        source  = cur_quote.get("source", "")
        author  = cur_quote.get("author", "")
        src_ln  = f"— {author}, {source}" if author else f"— {source}"
        gm      = cur_quote.get("good_morning_message", "")
        has_img = os.path.exists(cur_png)

        # Cache-bust the image so the browser reloads it after regeneration
        ts      = int(datetime.now().timestamp())
        img_section = (
            f'<img src="/poster.png?t={ts}" id="poster-img" '
            f'style="width:100%;border-radius:14px;margin:16px 0;box-shadow:0 4px 20px rgba(0,0,0,0.12);">'
            if has_img else
            '<p style="color:#999;font-style:italic;">Poster image not found — check output/posters/</p>'
        )

        msg_html = f'<p style="color:{message_color};font-weight:bold;margin:16px 0;">{message}</p>' if message else ""

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>🌅 Morning Poster — {_day()}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: Georgia, serif; background: #fff8f0; min-height: 100vh; padding: 30px 20px; }}
    .card {{ max-width: 560px; margin: 0 auto; background: white; border-radius: 16px;
             padding: 32px; box-shadow: 0 4px 30px rgba(0,0,0,0.08); }}
    h1 {{ color: #8b4513; font-size: 1.5rem; margin-bottom: 4px; }}
    .sub {{ color: #999; font-size: 0.9rem; margin-bottom: 16px; }}
    blockquote {{ background: #fff8f0; border-left: 4px solid #d4a574;
                 padding: 14px 18px; border-radius: 0 10px 10px 0; margin: 16px 0; }}
    blockquote p {{ font-style: italic; color: #444; line-height: 1.6; margin-bottom: 8px; }}
    blockquote small {{ color: #999; font-size: 13px; }}
    .gm {{ color: #8b4513; font-size: 14px; margin-top: 8px; font-style: italic; }}
    .buttons {{ display: flex; gap: 10px; margin-top: 24px; flex-wrap: wrap; }}
    .btn {{ padding: 12px 22px; border-radius: 10px; text-decoration: none;
            font-size: 14px; font-family: Georgia, serif; display: inline-block;
            transition: opacity 0.2s; cursor: pointer; }}
    .btn:hover {{ opacity: 0.85; }}
    .btn-approve {{ background: #405DE6; color: white; }}
    .btn-ig      {{ background: #C13584; color: white; }}
    .btn-wa      {{ background: #25D366; color: white; }}
    .btn-regen   {{ background: #ff9800; color: white; }}
    .btn-verse   {{ background: #9c27b0; color: white; }}
    .btn-skip    {{ background: #eee; color: #555; }}
    .divider     {{ width: 100%; border: none; border-top: 1px solid #f0e8e0; margin: 10px 0 4px; }}
    .regen-note  {{ color: #aaa; font-size: 12px; margin-top: 6px; font-style: italic; }}
    .caption {{ margin-top: 20px; background: #f9f9f9; border-radius: 10px;
                padding: 14px; font-size: 13px; color: #555; white-space: pre-wrap;
                max-height: 150px; overflow-y: auto; }}
    details summary {{ cursor: pointer; color: #aaa; font-size: 12px; margin-top: 16px; }}
    #regen-status {{ display:none; color:#e65100; font-weight:bold; margin-top:10px; }}
  </style>
  <script>
    function regen(type) {{
      document.getElementById('regen-status').style.display = 'block';
      document.getElementById('regen-status').textContent =
        type === 'image' ? '🔄 Fetching a new background photo…' : '📝 Picking a different verse…';
      fetch('/regenerate?type=' + type + '&token={cur_token}')
        .then(r => r.json())
        .then(d => {{ if (d.ok) location.reload(); else alert('Regeneration failed: ' + d.error); }})
        .catch(() => location.reload());
    }}
  </script>
</head>
<body>
<div class="card">
  <h1>🌅 Good Morning!</h1>
  <p class="sub">{_day()} — {datetime.now().strftime("%d %B %Y")}</p>
  {img_section}
  <blockquote>
    <p>{verse}…</p>
    <small>{src_ln}</small>
    <p class="gm">✨ {gm}</p>
  </blockquote>
  {msg_html}
  <div id="regen-status"></div>

  <!-- Regeneration options -->
  <div class="buttons">
    <button onclick="regen('image')" class="btn btn-regen">🔄 New Image</button>
    <button onclick="regen('verse')" class="btn btn-verse">📝 New Verse</button>
  </div>
  <p class="regen-note">Not happy with the photo or verse? Tap above to swap — page refreshes automatically.</p>

  <hr class="divider">

  <!-- Post actions -->
  <div class="buttons">
    <a href="/approve?token={cur_token}" class="btn btn-approve">✅ Post to Both</a>
    <a href="/approve?target=instagram&token={cur_token}" class="btn btn-ig">📸 Instagram only</a>
    <a href="/approve?target=whatsapp&token={cur_token}"  class="btn btn-wa">💬 WhatsApp only</a>
    <a href="/skip?token={cur_token}"    class="btn btn-skip">⏭ Skip today</a>
  </div>
  <details>
    <summary>View Instagram caption</summary>
    <div class="caption">{cur_caption[:700]}</div>
  </details>
</div>
</body>
</html>"""

    # ── Already-done page (shown if poster was posted or skipped earlier) ────
    def _done_page_html(status: str):
        if status == "posted":
            icon, heading, detail = "✅", "Already posted!", "Today's poster has been shared. See you tomorrow 🌅"
        else:
            icon, heading, detail = "🌿", "Skipped for today", "No worries — the verse is saved for another day. See you tomorrow 🌅"
        ts = int(datetime.now().timestamp())
        cur_png = state.get("png_path", "")
        img_html = (
            f'<img src="/poster.png?t={ts}" style="width:100%;border-radius:12px;'
            f'margin:16px 0;box-shadow:0 4px 16px rgba(0,0,0,0.10);">'
            if cur_png and os.path.exists(cur_png) else ""
        )
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>🌅 Morning Poster — Done</title>
  <style>
    body {{ font-family: Georgia, serif; background: #fff8f0; display: flex;
            align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }}
    .box {{ text-align: center; padding: 40px 32px; background: white; border-radius: 16px;
            box-shadow: 0 4px 30px rgba(0,0,0,0.08); max-width: 480px; width: 100%; }}
    h2 {{ color: #8b4513; margin: 12px 0 8px; }}
    p  {{ color: #999; line-height: 1.7; margin: 0; }}
    .icon {{ font-size: 2.8rem; }}
  </style>
</head>
<body>
<div class="box">
  <div class="icon">{icon}</div>
  <h2>{heading}</h2>
  {img_html}
  <p>{detail}</p>
</div>
</body>
</html>"""

    # ── Routes ───────────────────────────────────────────────────────────────

    @app.route("/")
    @require_token
    def index():
        from flask import Response
        # If already posted or skipped today, show a done page instead
        try:
            cur_status = _load_pending(pending_path).get("status", "pending")
        except Exception:
            cur_status = "pending"
        if cur_status == "posted":
            return Response(_done_page_html("posted"), mimetype="text/html")
        if cur_status == "skipped":
            return Response(_done_page_html("skipped"), mimetype="text/html")
        return Response(approval_page_html(), mimetype="text/html")

    @app.route("/poster.png")
    def poster_image():
        # No token needed — just an image file
        from flask import send_file as sf
        return sf(state["png_path"], mimetype="image/png")

    @app.route("/approve")
    @require_token
    def approve():
        from flask import request, Response
        target = request.args.get("target", "both")  # both | instagram | whatsapp

        # Guard: don't post twice if already approved/posted
        try:
            cur_status = _load_pending(pending_path).get("status", "pending")
        except Exception:
            cur_status = "pending"
        if cur_status in ("approved", "posted"):
            return Response(_done_page_html("posted"), mimetype="text/html")

        _update_pending(pending_path, {
            "status": "approved",
            "approved_at": datetime.now().isoformat(),
            "target": target,
        })

        # ── Run posting in background thread ────────────────────────────────
        def post():
            ig_ok = wa_ok = True
            cur_png     = state["png_path"]
            cur_caption = state["caption"]

            if target in ("both", "instagram"):
                try:
                    from automation.post_instagram import post_to_instagram
                    ig_ok = post_to_instagram(cur_png, cur_caption)
                except Exception as e:
                    print(f"Instagram error: {e}")
                    ig_ok = False

            if target in ("both", "whatsapp"):
                try:
                    from automation.post_whatsapp import post_whatsapp_status
                    wa_ok = post_whatsapp_status(cur_png)
                except Exception as e:
                    print(f"WhatsApp error: {e}")
                    wa_ok = False

            _update_pending(pending_path, {
                "status": "posted",
                "posted_at": datetime.now().isoformat(),
                "instagram_ok": ig_ok,
                "whatsapp_ok": wa_ok,
            })

        post_thread = threading.Thread(target=post, daemon=True)
        post_thread.start()
        _delayed_shutdown(seconds=5, wait_for_thread=post_thread)  # waits for posting to finish

        targets = {"both": "Instagram & WhatsApp Status", "instagram": "Instagram", "whatsapp": "WhatsApp Status"}
        tname = targets.get(target, "Instagram & WhatsApp Status")
        success_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Posting…</title>
<style>body{{font-family:Georgia,serif;background:#fff8f0;display:flex;
align-items:center;justify-content:center;min-height:100vh;margin:0;}}
.box{{text-align:center;padding:40px;background:white;border-radius:16px;
box-shadow:0 4px 20px rgba(0,0,0,0.08);max-width:400px;}}
h2{{color:#8b4513;}} p{{color:#777;margin-top:12px;line-height:1.6;}}
.spinner{{font-size:2.5rem;animation:spin 2s linear infinite;display:inline-block;}}
@keyframes spin{{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}
</style></head>
<body><div class="box">
<div class="spinner">🌅</div>
<h2>Posting to {tname}…</h2>
<p>Please wait. Browser windows may open briefly.<br>
You can close this page — the posting will continue in the background.</p>
</div></body></html>"""
        return Response(success_html, mimetype="text/html")

    @app.route("/regenerate")
    @require_token
    def regenerate():
        from flask import request, jsonify
        rtype = request.args.get("type", "image")  # "image" or "verse"

        try:
            cur_pending = _load_pending(pending_path)
            day_of_week = cur_pending.get("day_of_week", datetime.now().weekday())
            html_path   = cur_pending.get("html_path", "")
            cur_png     = cur_pending.get("png_path",  state["png_path"])

            sys.path.insert(0, BASE_DIR)
            from config import DAY_SCHEDULE
            from poster_generator import generate_poster_html
            from automation.screenshot_poster import take_screenshot
            from post_to_social import build_caption

            if rtype == "image":
                # Force-delete cached photo so photo_fetcher downloads a fresh one
                from config import BG_CACHE_DIR
                from photo_fetcher import _cache_path, _cache_meta_path
                theme = DAY_SCHEDULE[day_of_week]["theme"]
                for p in (_cache_path(theme), _cache_meta_path(theme)):
                    if os.path.exists(p):
                        os.remove(p)
                print("🔄  Regenerating with new background image…")
                new_quote = state["quote"]   # keep same verse

            elif rtype == "verse":
                # Pick a new verse BEFORE unmarking the old one, so the rotation
                # engine skips it and doesn't immediately re-select the same verse.
                from quote_database import get_quote_for_day, unmark_used
                old_q   = state["quote"]
                # Support both new (_language) and legacy (_day_tag) key names
                old_lang = old_q.get("_language") or old_q.get("_day_tag")
                old_idx  = old_q.get("_quote_index")

                new_quote = get_quote_for_day(day_of_week)

                if new_quote.get("_quote_id") == old_q.get("_quote_id"):
                    # Same verse came back — only one available; restore mark and tell user
                    return jsonify(ok=False, error="No other verses available for today — all have been used. They'll reset next cycle.")

                # Different verse selected — now free the old one since it was never posted
                # Pass full quote dict so unmark_used can identify by content, not index
                unmark_used(old_lang, old_idx, quote=old_q)
                print(f"📝  New verse: {new_quote.get('author','')} — {new_quote.get('source','')}")

            else:
                return jsonify(ok=False, error=f"Unknown type: {rtype}")

            # Regenerate HTML poster with the (possibly new) quote
            generate_poster_html(day_of_week=day_of_week, output_path=html_path, quote=new_quote)

            # Re-screenshot to PNG
            take_screenshot(html_path, cur_png)

            # Rebuild caption if verse changed
            day_label  = DAY_SCHEDULE[day_of_week]["label"]
            new_caption = build_caption(new_quote, day_label)

            # Update live state so /approve uses the latest version
            state["quote"]    = new_quote
            state["caption"]  = new_caption
            state["png_path"] = cur_png

            # Persist to pending file
            _update_pending(pending_path, {
                "quote":   new_quote,
                "caption": new_caption,
            })

            print("✅  Regeneration complete.")
            return jsonify(ok=True)

        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify(ok=False, error=str(e))

    @app.route("/skip")
    @require_token
    def skip():
        from flask import Response
        _update_pending(pending_path, {
            "status": "skipped",
            "skipped_at": datetime.now().isoformat(),
        })
        # Free the verse so it can be used on a future day
        try:
            from quote_database import unmark_used
            q = state["quote"]
            # Support both new (_language) and legacy (_day_tag) key names
            # Pass full quote dict so unmark identifies by content (not fragile index)
            unmark_used(q.get("_language") or q.get("_day_tag"), q.get("_quote_index"), quote=q)
        except Exception:
            pass
        _delayed_shutdown(seconds=5)
        skip_html = """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Skipped</title>
<style>body{font-family:Georgia,serif;background:#fff8f0;display:flex;
align-items:center;justify-content:center;min-height:100vh;margin:0;}
.box{text-align:center;padding:40px;background:white;border-radius:16px;
box-shadow:0 4px 20px rgba(0,0,0,0.08);} h2{color:#888;} p{color:#aaa;margin-top:12px;}
</style></head><body><div class="box">
<div style="font-size:2.5rem;">🌿</div>
<h2>Skipped for today</h2>
<p>No worries — see you tomorrow! 🌅</p>
</div></body></html>"""
        return Response(skip_html, mimetype="text/html")

    @app.route("/status")
    def status():
        from flask import jsonify as jj
        return jj(_load_pending(pending_path))


    if not USE_HTTPS:
        print(f"    ⚠️  Running on HTTP (SSL cert generation failed).\n")
    else:
        print_trust_instructions(LOCAL_IP)

    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)  # suppress Flask request logs

    # ── HTTP-only endpoint for cloudflared tunnel (localhost only) ────────────
    # cloudflared tunnels to this plain-HTTP port; it provides HTTPS externally.
    # Bound to 127.0.0.1 so it's never reachable directly from the network.
    TUNNEL_PORT = 5679
    try:
        from werkzeug.serving import make_server as _make_server
        _http_srv = _make_server("127.0.0.1", TUNNEL_PORT, app, passthrough_errors=False)
        threading.Thread(target=_http_srv.serve_forever, daemon=True).start()
        print(f"    🔒  Tunnel HTTP endpoint ready on http://127.0.0.1:{TUNNEL_PORT}")
    except Exception as _e:
        print(f"    ⚠️  Could not start tunnel HTTP endpoint: {_e}")

    if USE_HTTPS:
        app.run(host="0.0.0.0", port=PORT, debug=False,
                ssl_context=(ssl_paths[0], ssl_paths[1]))
    else:
        app.run(host="0.0.0.0", port=PORT, debug=False)


if __name__ == "__main__":
    # Always start the server — it will show a "waiting" page if the pending
    # file doesn't exist yet and pick it up automatically once it appears.
    if len(sys.argv) >= 2:
        pending_file = sys.argv[1]
    else:
        pending_file = os.path.join(BASE_DIR, "output", "pending_approval.json")

    crash_log = os.path.join(BASE_DIR, "output", "server_crash.log")
    try:
        run_server(pending_file)
    except Exception:
        import traceback
        os.makedirs(os.path.dirname(crash_log), exist_ok=True)
        with open(crash_log, "w") as _f:
            _f.write(traceback.format_exc())
        print(traceback.format_exc())
        sys.exit(1)
