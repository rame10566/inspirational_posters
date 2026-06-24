#!/bin/bash
# Wrapper script for the catchup LaunchAgent.
# macOS 26 blocks direct posix_spawn of Homebrew Python from xpcproxy/XPC activities.
# Launching via /bin/bash (a trusted system binary) bypasses that restriction.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HOME="/Users/jeera"
export PYTHONUNBUFFERED=1
exec /opt/homebrew/opt/python@3.14/bin/python3.14 -u \
    /Users/jeera/Desktop/Claude-Projects/inspirational-posters/automation/daily_runner.py \
    --catchup
