#!/bin/bash
# Watchdog / manual reapprove wrapper.
#
# Restarts the approval server + cloudflared tunnel + re-sends the email
# if today's poster is still pending approval but the server died.
#
# Safe to call repeatedly — exits silently if:
#   - No pending poster for today
#   - Already posted or skipped
#   - Server is already running fine
#
# Called by cron every 30 min (7 PM–midnight) as a watchdog.
# Also safe to run manually anytime:
#   /bin/bash ~/Desktop/Claude-Projects/inspirational-posters/automation/run_reapprove.sh

export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HOME="/Users/jeera"
export PYTHONUNBUFFERED=1

exec /opt/homebrew/opt/python@3.14/bin/python3.14 -u \
    /Users/jeera/Desktop/Claude-Projects/inspirational-posters/automation/daily_runner.py \
    --reapprove
