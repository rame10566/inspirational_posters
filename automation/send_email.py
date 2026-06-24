"""
Send the daily approval email with the poster image and Approve / Skip buttons.

Uses Gmail + App Password (no third-party libraries needed).

Setup (one time):
  1. Enable 2-Step Verification on your Google account.
  2. Go to myaccount.google.com → Security → App passwords.
  3. Create an App password for "Mail" and paste it into email_config.json.

The email contains:
  - The poster embedded as an inline image
  - An "Approve & Post" button → http://localhost:5678/approve
  - A "Skip Today" button → http://localhost:5678/skip
"""

import os
import sys
import json
import smtplib
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "email_config.json",
)

APPROVAL_PORT = 5678


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        print(f"❌  email_config.json not found. Run setup_automation.py first.")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def send_approval_email(png_path: str, quote: dict, day_label: str, caption: str,
                        base_url: str = None) -> bool:
    """
    Send the morning poster approval email.

    Args:
        png_path:   Absolute path to the poster PNG.
        quote:      Quote dict (original_text, source, author, good_morning_message …).
        day_label:  e.g. "Sunday", "Monday" …
        caption:    Instagram caption string.
        base_url:   Optional public URL (e.g. cloudflared tunnel) to use in links.
                    Falls back to local network IP if not provided.

    Returns:
        True on success, False on failure.
    """
    cfg = load_config()
    sender       = cfg["gmail_address"]
    app_password = cfg["app_password"]
    recipient    = cfg.get("recipient_email", sender)

    # ── Build email ─────────────────────────────────────────────────────────
    msg = MIMEMultipart("related")
    from datetime import datetime as _dt
    _date_str = _dt.now().strftime("%d %b")   # e.g. "25 May"
    msg["Subject"] = f"🌅 Morning Poster — {day_label} {_date_str} | Approve to post?"
    msg["From"]    = sender
    msg["To"]      = recipient

    verse_snippet = quote.get("original_text", "")[:120].replace("\n", " ")
    source        = quote.get("source", "")
    author        = quote.get("author", "")
    source_line   = f"— {author}, {source}" if author else f"— {source}"
    morning_msg   = quote.get("good_morning_message", "")

    # Use cloudflared public URL if provided (works from any network/device),
    # otherwise fall back to the Mac's local network IP (same-WiFi only).
    if base_url:
        base = base_url.rstrip("/")
    else:
        import socket as _socket
        try:
            _s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            _s.connect(("8.8.8.8", 80))
            local_ip = _s.getsockname()[0]
            _s.close()
        except Exception:
            local_ip = "localhost"
        base = f"https://{local_ip}:{APPROVAL_PORT}"

    token         = quote.get("_session_token", "")
    base          = base
    tok           = f"token={token}" if token else ""
    def _url(path): return f"{base}{path}{'&' if '?' in path else '?'}{tok}" if tok else f"{base}{path}"

    approve_url   = _url("/approve")
    skip_url      = _url("/skip")
    new_image_url = _url("/regenerate?type=image")
    new_verse_url = _url("/regenerate?type=verse")
    review_url    = _url("/")

    html_body = f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:30px;background:#fff8f0;font-family:Georgia,serif;">
<div style="max-width:560px;margin:0 auto;">

  <h2 style="color:#8b4513;margin-bottom:4px;">🌅 Good Morning, Jeera!</h2>
  <p style="color:#777;margin-top:0;">Your {day_label} poster is ready. Here's a preview:</p>

  <img src="cid:poster_img"
       style="width:100%;border-radius:14px;display:block;margin:16px 0;
              box-shadow:0 4px 20px rgba(0,0,0,0.15);">

  <blockquote style="background:#fff;border-left:4px solid #d4a574;
                     padding:16px 20px;border-radius:0 10px 10px 0;margin:0 0 20px;">
    <p style="font-style:italic;margin:0 0 10px;color:#333;line-height:1.6;">
      {verse_snippet}…
    </p>
    <p style="color:#999;font-size:13px;margin:0;">{source_line}</p>
    <p style="color:#555;font-size:14px;margin:10px 0 0;font-style:italic;">
      ✨ {morning_msg}
    </p>
  </blockquote>

  <!-- Regenerate options -->
  <div style="text-align:center;margin:20px 0 8px;">
    <a href="{new_image_url}"
       style="background:#ff9800;color:#fff;padding:12px 24px;border-radius:10px;
              text-decoration:none;font-size:14px;display:inline-block;
              font-family:Georgia,serif;">
      🔄 New Image
    </a>
    &nbsp;
    <a href="{new_verse_url}"
       style="background:#9c27b0;color:#fff;padding:12px 24px;border-radius:10px;
              text-decoration:none;font-size:14px;display:inline-block;
              font-family:Georgia,serif;">
      📝 New Verse
    </a>
    &nbsp;
    <a href="{review_url}"
       style="background:#607d8b;color:#fff;padding:12px 24px;border-radius:10px;
              text-decoration:none;font-size:14px;display:inline-block;
              font-family:Georgia,serif;">
      👁 Review
    </a>
  </div>
  <p style="color:#bbb;font-size:11px;text-align:center;margin:4px 0 20px;">
    Not happy with the image or verse? Tap above — then open Review to see the updated poster.
  </p>

  <!-- Post actions -->
  <div style="text-align:center;margin:16px 0;">
    <a href="{approve_url}"
       style="background:#405DE6;color:#fff;padding:16px 36px;border-radius:10px;
              text-decoration:none;font-size:16px;display:inline-block;
              font-family:Georgia,serif;letter-spacing:0.5px;">
      ✅ Approve &amp; Post
    </a>
    &nbsp;&nbsp;
    <a href="{skip_url}"
       style="background:#eee;color:#555;padding:16px 28px;border-radius:10px;
              text-decoration:none;font-size:16px;display:inline-block;
              font-family:Georgia,serif;">
      ⏭ Skip Today
    </a>
  </div>

  <p style="color:#bbb;font-size:12px;text-align:center;margin-top:8px;">
    All buttons require your Mac to be on and the poster app to be running.
  </p>

  <details style="margin-top:16px;">
    <summary style="color:#999;font-size:12px;cursor:pointer;">Caption preview</summary>
    <pre style="font-size:12px;color:#555;background:#f5f5f5;padding:12px;
                border-radius:8px;white-space:pre-wrap;margin-top:8px;">{caption[:600]}</pre>
  </details>

</div>
</body>
</html>
"""

    msg.attach(MIMEText(html_body, "html"))

    # Attach poster as inline image
    with open(png_path, "rb") as f:
        img = MIMEImage(f.read(), _subtype="png")
    img.add_header("Content-ID", "<poster_img>")
    img.add_header("Content-Disposition", "inline", filename="morning_poster.png")
    msg.attach(img)

    # ── Send via Gmail SMTP ──────────────────────────────────────────────────
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, app_password)
            server.send_message(msg)
        print(f"📧  Approval email sent to {recipient}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌  Gmail authentication failed.")
        print("    Make sure you're using an App Password (not your regular Gmail password).")
        print("    See: myaccount.google.com → Security → App passwords")
        return False
    except Exception as e:
        print(f"❌  Email send failed: {e}")
        return False
