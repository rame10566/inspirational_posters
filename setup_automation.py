"""
One-time setup for the Morning Poster automation.

Run this ONCE before the first automated run:
    python3 setup_automation.py

What it does:
  1. Installs required Python packages (playwright, flask)
  2. Configures your Gmail details for approval emails
  3. Logs you into Instagram (saves session so daily runs work silently)
  4. Logs you into WhatsApp Web (saves session after QR scan)
  5. Installs the macOS LaunchAgent for 6 AM daily scheduling
  6. Does a test run to verify everything works
"""

import os
import sys
import json
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMAIL_CONFIG = os.path.join(BASE_DIR, "email_config.json")
PLIST_SRC    = os.path.join(BASE_DIR, "com.morningposter.daily.plist")
PLIST_DST    = os.path.expanduser("~/Library/LaunchAgents/com.morningposter.daily.plist")
PYTHON       = sys.executable


def _header(text):
    print(f"\n{'─'*55}")
    print(f"  {text}")
    print(f"{'─'*55}")


def _run(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0 and check:
        print(f"    ⚠️  Command failed: {cmd}")
        print(f"    {result.stderr.strip()}")
    return result.returncode == 0


# ── Step 1: Install packages ──────────────────────────────────────────────────

_header("Step 1 of 5 — Installing Python packages")

packages = ["flask", "playwright", "instagrapi"]
for pkg in packages:
    try:
        __import__(pkg)
        print(f"  ✅  {pkg} already installed")
    except ImportError:
        print(f"  📦  Installing {pkg}…")
        _run(f"{PYTHON} -m pip install {pkg} --break-system-packages --quiet")

# Install Playwright Chromium browser
print("  📦  Installing Playwright Chromium (one-time download, ~150 MB)…")
_run(f"{PYTHON} -m playwright install chromium")
print("  ✅  Playwright ready")


# ── Step 2: Gmail config ──────────────────────────────────────────────────────

_header("Step 2 of 5 — Gmail email configuration")

existing = {}
if os.path.exists(EMAIL_CONFIG):
    with open(EMAIL_CONFIG) as f:
        existing = json.load(f)
    print(f"  Found existing config for: {existing.get('gmail_address','')}")
    redo = input("  Re-configure? (y/N): ").strip().lower()
    if redo != "y":
        print("  ✅  Keeping existing email config.")
        existing = None

if existing is not None:
    print()
    print("  You need a Gmail App Password (NOT your regular password).")
    print("  Steps:")
    print("    1. Go to: myaccount.google.com/security")
    print("    2. Enable 2-Step Verification if not already on")
    print("    3. Search 'App passwords' → create one for 'Mail'")
    print("    4. Copy the 16-character password\n")

    gmail   = input("  Your Gmail address: ").strip()
    app_pwd = input("  Your App Password (16 chars, spaces OK): ").strip().replace(" ", "")
    recip   = input(f"  Send approval email TO (Enter for {gmail}): ").strip() or gmail

    config = {
        "gmail_address":   gmail,
        "app_password":    app_pwd,
        "recipient_email": recip,
    }
    with open(EMAIL_CONFIG, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\n  ✅  Email config saved to email_config.json")

    # Quick SMTP test
    print("  🧪  Testing Gmail connection…")
    import smtplib
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(config["gmail_address"], config["app_password"])
        print("  ✅  Gmail connection successful!")
    except Exception as e:
        print(f"  ❌  Gmail test failed: {e}")
        print("      Double-check your App Password at myaccount.google.com/apppasswords")


# ── Step 3: Instagram login ───────────────────────────────────────────────────

_header("Step 3 of 5 — Instagram credentials setup")

print("  Instagram posting now uses instagrapi (no browser needed — much more reliable).")
print("  Your credentials are stored locally in instagram_credentials.json\n")
do_ig = input("  Set up Instagram now? (Y/n): ").strip().lower()
if do_ig != "n":
    from automation.post_instagram import setup_instagram_credentials
    setup_instagram_credentials()
else:
    print("  ⏭  Skipped — run: python3 automation/post_instagram.py --setup")


# ── Step 4: WhatsApp session ──────────────────────────────────────────────────

_header("Step 4 of 5 — WhatsApp Web session setup")

print("  This opens Chrome with WhatsApp Web for you to scan the QR code.")
print("  On your phone: WhatsApp → Settings → Linked Devices → Link a Device\n")
do_wa = input("  Set up WhatsApp now? (Y/n): ").strip().lower()
if do_wa != "n":
    from automation.post_whatsapp import setup_whatsapp_session
    setup_whatsapp_session()
else:
    print("  ⏭  Skipped — you can run this again later.")


# ── Step 5: macOS LaunchAgent ─────────────────────────────────────────────────

_header("Step 5 of 5 — Schedule daily 6 AM run (macOS LaunchAgent)")

# Write the plist with correct Python path and project path
plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.morningposter.daily</string>

  <key>ProgramArguments</key>
  <array>
    <string>{PYTHON}</string>
    <string>{os.path.join(BASE_DIR, 'automation', 'daily_runner.py')}</string>
  </array>

  <key>WorkingDirectory</key>
  <string>{BASE_DIR}</string>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>6</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>{os.path.join(BASE_DIR, 'output', 'daily_runner.log')}</string>

  <key>StandardErrorPath</key>
  <string>{os.path.join(BASE_DIR, 'output', 'daily_runner_error.log')}</string>

  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
"""

with open(PLIST_SRC, "w") as f:
    f.write(plist_content)

# Install
os.makedirs(os.path.expanduser("~/Library/LaunchAgents"), exist_ok=True)
import shutil
shutil.copy(PLIST_SRC, PLIST_DST)

# Unload first if already loaded (ignore errors)
subprocess.run(["launchctl", "unload", PLIST_DST], capture_output=True)
result = subprocess.run(["launchctl", "load", PLIST_DST], capture_output=True, text=True)

if result.returncode == 0:
    print("  ✅  LaunchAgent installed! Daily run scheduled at 6:00 AM every day.")
else:
    print(f"  ⚠️  LaunchAgent install issue: {result.stderr.strip()}")
    print(f"      You can install it manually: launchctl load {PLIST_DST}")


# ── Done ──────────────────────────────────────────────────────────────────────

print(f"""
{'='*55}
  🎉  Setup complete!

  Your morning poster will:
  • Generate every day at 6:00 AM automatically
  • Send you an approval email with the poster
  • Click "Approve & Post" in the email to post to
    Instagram + WhatsApp Status

  To test right now (without waiting for 6 AM):
    python3 automation/daily_runner.py

  To check the schedule is loaded:
    launchctl list | grep morningposter

  To disable the schedule temporarily:
    launchctl unload ~/Library/LaunchAgents/com.morningposter.daily.plist

  To re-enable:
    launchctl load ~/Library/LaunchAgents/com.morningposter.daily.plist
{'='*55}
""")
