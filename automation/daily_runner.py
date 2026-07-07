"""
Daily Runner — runs every morning at 6 AM via macOS LaunchAgent.

Steps:
  1. Generate today's poster HTML (Unsplash photo background + verse)
  2. Screenshot the HTML → PNG (via Playwright)
  3. Start the approval server in the background (Flask on localhost:5678)
  4. Send you an approval email with the poster + Approve / Skip buttons
  5. Exit (the approval server keeps running until you click a button)

Run manually to test:
    python3 automation/daily_runner.py
    python3 automation/daily_runner.py --day friday
"""

import os
import sys
import json
import re
import shutil
import uuid
import argparse
import subprocess
from datetime import datetime

# Make sure we can import from the parent folder
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from poster_generator import generate_poster_html
from quote_database import get_quote_for_day
from post_to_social import build_caption
from config import POSTERS_DIR, DAY_SCHEDULE

PENDING_FILE    = os.path.join(BASE_DIR, "output", "pending_approval.json")
TUNNEL_URL_FILE = os.path.join(BASE_DIR, "output", "tunnel_url.txt")
AUTOMATION_DIR  = os.path.dirname(os.path.abspath(__file__))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _start_cloudflared_tunnel(http_port: int = 5679, timeout: int = 40):
    """
    Start a cloudflared quick tunnel to the approval server's HTTP endpoint.
    Returns (process, public_url) or (None, None) if cloudflared isn't installed
    or the tunnel can't be established.

    No Cloudflare account needed — uses free quick tunnels (trycloudflare.com).
    The URL changes each session but is embedded in the email, so each day's
    email has the correct link.
    """
    import time

    if not shutil.which("cloudflared"):
        return None, None   # not installed — fall back to local IP

    # Kill any cloudflared left over from a previous run
    subprocess.run(["pkill", "-f", "cloudflared"], check=False)
    time.sleep(1)

    try:
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{http_port}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,   # keep running after daily_runner exits
        )

        # cloudflared prints the public URL to stderr once the tunnel is up
        deadline = time.time() + timeout
        url = None
        while time.time() < deadline:
            line = proc.stderr.readline()
            if not line:
                time.sleep(0.1)
                continue
            match = re.search(r'https://[\w-]+\.trycloudflare\.com', line)
            if match:
                url = match.group(0)
                break

        if url:
            with open(TUNNEL_URL_FILE, "w") as f:
                f.write(url)
            return proc, url
        else:
            proc.terminate()
            if os.path.exists(TUNNEL_URL_FILE):
                os.remove(TUNNEL_URL_FILE)
            return None, None

    except Exception:
        return None, None

def _day_from_name(name: str) -> int:
    return {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,
            "friday":4,"saturday":5,"sunday":6}.get(name.lower(), None)


def _already_ran_today() -> bool:
    """
    Return True if today's poster was already generated and emailed.
    Prevents double-runs if the LaunchAgent fires more than once,
    and also lets us call this from a login/wake trigger for catch-up.
    """
    if not os.path.exists(PENDING_FILE):
        return False
    try:
        with open(PENDING_FILE) as f:
            pending = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        return pending.get("date") == today and pending.get("status") in ("pending", "approved", "posted")
    except Exception:
        return False


def _free_unapproved_verse():
    """
    If the previous pending poster was never approved (status still 'pending'
    and date is not today), return its verse to the unused pool so it can
    appear again on a future day instead of being wasted.
    """
    if not os.path.exists(PENDING_FILE):
        return
    try:
        with open(PENDING_FILE) as f:
            pending = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        if pending.get("date") == today:
            return   # today's entry — leave it alone
        if pending.get("status") not in ("pending",):
            return   # was approved, posted, or skipped intentionally — leave it
        # It was generated but never acted on — free the verse
        quote = pending.get("quote", {})
        # Support both new (_language) and legacy (_day_tag) key names
        language    = quote.get("_language") or quote.get("_day_tag")
        quote_index = quote.get("_quote_index")
        if language is not None and quote_index is not None:
            from quote_database import unmark_used
            unmark_used(language, quote_index)
            print(f"↩️   Previous unapproved verse freed (date={pending.get('date')}).")
    except Exception as e:
        print(f"    ⚠️  Could not free unapproved verse: {e}")


def _server_is_running() -> bool:
    """Return True if the approval server is listening on port 5678."""
    import socket as _sock
    try:
        s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(("127.0.0.1", 5678))
        s.close()
        return result == 0
    except Exception:
        return False


def _reapprove():
    """
    Restart the approval server + cloudflared tunnel and re-send the email
    for today's pending poster.  Safe to call repeatedly — exits silently if:
      - There is no pending poster for today
      - Today's poster was already posted or skipped
      - The server is already running (no restart needed)
    """
    import time

    if not os.path.exists(PENDING_FILE):
        print("✅  No pending poster — nothing to reapprove.")
        return

    try:
        with open(PENDING_FILE) as f:
            pending = json.load(f)
    except Exception as e:
        print(f"❌  Could not read pending_approval.json: {e}")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    status = pending.get("status", "")
    date   = pending.get("date", "")

    if date != today:
        print(f"✅  Pending poster is from {date}, not today — nothing to do.")
        return
    if status in ("posted", "skipped"):
        print(f"✅  Today's poster already {status} — nothing to do.")
        return
    if status == "approved":
        print(f"⏳  Posting already in progress (status=approved) — nothing to do.")
        return

    # status == "pending" and date == today: need to (re)start everything
    if _server_is_running():
        print("✅  Approval server already running — no restart needed.")
        return

    print(f"\n🔄  Restarting approval for {pending.get('day_label','')} {date}…")

    # ── Kill any stale processes ─────────────────────────────────────────
    subprocess.run(["pkill", "-f", "approval_server.py"], check=False)
    subprocess.run(["pkill", "-f", "cloudflared"],        check=False)
    time.sleep(2)

    # ── Start fresh approval server ──────────────────────────────────────
    server_script = os.path.join(AUTOMATION_DIR, "approval_server.py")
    log_path  = os.path.join(BASE_DIR, "output", "server.log")
    log_out   = open(log_path, "a")        # append so we keep history
    proc = subprocess.Popen(
        [sys.executable, server_script, PENDING_FILE],
        stdout=log_out, stderr=log_out,
        start_new_session=True,
    )
    time.sleep(3)
    if proc.poll() is not None:
        print(f"❌  Approval server failed to start (exit {proc.returncode}).")
        print(f"    Check output/server.log for details.")
        return
    print(f"    ✅  Approval server restarted (PID {proc.pid})")

    # ── Start fresh cloudflared tunnel ───────────────────────────────────
    tunnel_url = None
    if shutil.which("cloudflared"):
        print(f"    🌍  Starting cloudflared tunnel…")
        _, tunnel_url = _start_cloudflared_tunnel()
        if tunnel_url:
            print(f"    🌍  Remote URL: {tunnel_url}")
        else:
            print(f"    ⚠️  Tunnel unavailable — email will use local IP only.")

    # ── Re-send approval email with new tunnel URL ───────────────────────
    email_config = os.path.join(BASE_DIR, "email_config.json")
    png_path     = pending.get("png_path", "")
    quote        = pending.get("quote", {})
    day_label    = pending.get("day_label", "")
    caption      = pending.get("caption", "")

    if os.path.exists(email_config) and png_path and os.path.exists(png_path):
        print(f"    📧  Re-sending approval email…")
        try:
            from automation.send_email import send_approval_email
            send_approval_email(png_path, quote, day_label, caption,
                                base_url=tunnel_url)
            print(f"    ✅  Email re-sent!")
        except Exception as e:
            print(f"    ⚠️  Email failed: {e}")
    else:
        token = pending.get("session_token", "")
        print(f"\n    ℹ️  Open approval page manually:")
        print(f"    open 'https://localhost:5678/?token={token}'")

    print(f"\n✅  Reapprove complete. Check your email or open:")
    print(f"    https://localhost:5678/?token={pending.get('session_token','')}\n")


def _send_macos_notification(title: str, message: str):
    """Send a macOS system notification (no extra packages needed)."""
    script = (
        f'display notification "{message}" with title "{title}" '
        f'sound name "Bells"'
    )
    try:
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception:
        pass   # not on Mac or osascript unavailable


# ── Main workflow ─────────────────────────────────────────────────────────────

def run(day_of_week: int = None, skip_email: bool = False, skip_server: bool = False):
    today_str = datetime.now().strftime("%Y-%m-%d")
    if day_of_week is None:
        day_of_week = datetime.now().weekday()

    schedule  = DAY_SCHEDULE[day_of_week]
    day_label = schedule["label"]
    os.makedirs(POSTERS_DIR, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  🌅 Morning Poster — {day_label} {today_str}")
    print(f"{'='*55}\n")

    # ── 0. Free any unapproved verse from a previous day ─────────────────────
    _free_unapproved_verse()

    # ── 1. Select quote ──────────────────────────────────────────────────────
    print("📖  Selecting today's verse…")
    quote   = get_quote_for_day(day_of_week)
    caption = build_caption(quote, day_label)
    print(f"    {quote.get('author','')}, {quote['source']}")

    # ── 2. Generate poster HTML ──────────────────────────────────────────────
    html_filename = f"poster_{day_label.lower()}_{today_str}.html"
    html_path     = os.path.join(POSTERS_DIR, html_filename)
    print(f"\n🎨  Generating poster…")
    # Pass the already-selected quote so the poster and caption always match
    # (avoids a double-rotation bug where generate_poster_html would call
    # get_quote_for_day() again and pick a different quote than the caption)
    generate_poster_html(day_of_week=day_of_week, output_path=html_path, quote=quote)
    print(f"    HTML: {html_path}")

    # ── 3. Screenshot → PNG ──────────────────────────────────────────────────
    png_path = os.path.splitext(html_path)[0] + ".png"
    print(f"\n📸  Taking screenshot…")
    try:
        from automation.screenshot_poster import take_screenshot
        take_screenshot(html_path, png_path)
        print(f"    PNG: {png_path}")
    except Exception as e:
        print(f"    ⚠️  Screenshot failed: {e}")
        print(f"    Install Playwright:  pip3 install playwright && playwright install chromium")
        png_path = None

    # ── 4. Save pending approval data ────────────────────────────────────────
    # Generate a session token — included in every email link so the approval
    # page is accessible from any device on the home network, securely.
    session_token = uuid.uuid4().hex
    quote["_session_token"] = session_token   # email builder reads this

    pending = {
        "day_label":     day_label,
        "day_of_week":   day_of_week,
        "date":          today_str,
        "quote":         quote,
        "html_path":     html_path,
        "png_path":      png_path or "",
        "caption":       caption,
        "status":        "pending",
        "session_token": session_token,
        "generated_at":  datetime.now().isoformat(),
    }
    os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, indent=2, ensure_ascii=False)

    # ── 5. Start approval server (background, detached) ─────────────────────
    if not skip_server:
        print(f"\n🌐  Starting approval server…")
        # Kill any previously running approval server so it doesn't hold
        # port 5678 with a stale token that mismatches the new email link.
        subprocess.run(["pkill", "-f", "approval_server.py"], check=False)
        import time; time.sleep(1)   # brief pause for the port to free up

        server_script = os.path.join(AUTOMATION_DIR, "approval_server.py")
        log_path = os.path.join(BASE_DIR, "output", "server.log")
        log_out  = open(log_path, "w")
        proc = subprocess.Popen(
            [sys.executable, server_script, PENDING_FILE],
            stdout=log_out,
            stderr=log_out,
            start_new_session=True,   # detach from daily_runner's process group
                                      # so launchd doesn't kill it when we exit
        )
        # Give it 3 seconds and check it didn't immediately crash
        import time; time.sleep(3)
        if proc.poll() is not None:
            print(f"    ⚠️  Approval server failed to start (exit {proc.returncode}).")
            print(f"    Check output/server.log for details.")
        else:
            print(f"    ✅  Approval server running (PID {proc.pid})")

    # ── 5b. Start cloudflared tunnel for remote/mobile approval ──────────────
    tunnel_url = None
    if not skip_server:
        if shutil.which("cloudflared"):
            print(f"    🌍  Starting cloudflared tunnel (mobile access)…")
            _, tunnel_url = _start_cloudflared_tunnel()
            if tunnel_url:
                print(f"    🌍  Remote approval URL: {tunnel_url}")
            else:
                print(f"    ⚠️  Tunnel unavailable — email links will use local WiFi only.")
        # (if cloudflared not installed, fall through silently — local IP used below)

    # ── 6. Send approval email ───────────────────────────────────────────────
    if not skip_email:
        email_config = os.path.join(BASE_DIR, "email_config.json")
        if os.path.exists(email_config) and png_path and os.path.exists(png_path):
            print(f"\n📧  Sending approval email…")
            try:
                from automation.send_email import send_approval_email
                send_approval_email(png_path, quote, day_label, caption,
                                    base_url=tunnel_url)
            except Exception as e:
                print(f"    ⚠️  Email failed: {e}")
        else:
            if not os.path.exists(email_config):
                print(f"\n⚠️  No email_config.json — skipping email.")
                print(f"    Run setup_automation.py to configure email.")

    # ── 7. macOS notification ────────────────────────────────────────────────
    _send_macos_notification(
        "🌅 Morning Poster Ready!",
        f"Your {day_label} poster is ready. Open the approval link in your email to post.",
    )

    print(f"\n{'='*55}")
    print(f"  ✅  Done! Poster ready for approval.")
    print(f"      Check your email or open: http://localhost:5678")
    print(f"{'='*55}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily morning poster runner")
    parser.add_argument("--day",       type=str,        help="Day name, e.g. friday")
    parser.add_argument("--no-email",  action="store_true", help="Skip sending email")
    parser.add_argument("--no-server", action="store_true", help="Skip starting approval server")
    parser.add_argument("--catchup",   action="store_true",
                        help="Only run if today's poster hasn't been generated yet "
                             "(safe to call on every login/wake — skips silently if already done)")
    parser.add_argument("--reapprove", action="store_true",
                        help="Restart approval server + tunnel + re-send email for today's "
                             "pending poster. Safe to call repeatedly — exits silently if "
                             "already posted/skipped or server is already running.")
    args = parser.parse_args()

    if args.reapprove:
        _reapprove()
        sys.exit(0)

    if args.catchup and _already_ran_today():
        print("✅  Today's poster was already generated — nothing to do.")
        sys.exit(0)

    dow = None
    if args.day:
        dow = _day_from_name(args.day)
        if dow is None:
            print(f"Unknown day: {args.day}")
            sys.exit(1)

    run(day_of_week=dow, skip_email=args.no_email, skip_server=args.no_server)
