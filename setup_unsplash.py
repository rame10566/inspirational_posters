"""
Quick setup helper — run this once to:
  1. Save your Unsplash API key into config.py
  2. Test the connection
  3. Download and cache photos for all 7 themes

Usage:
    python setup_unsplash.py YOUR_ACCESS_KEY_HERE

Get your free key at: https://unsplash.com/developers → New Application
"""

import sys
import os

if len(sys.argv) < 2:
    print("\nUsage: python setup_unsplash.py YOUR_ACCESS_KEY")
    print("\nGet a free key at: https://unsplash.com/developers")
    print("→ Sign in → Your apps → New Application\n")
    sys.exit(1)

key = sys.argv[1].strip()

# Patch the key into config.py
config_path = os.path.join(os.path.dirname(__file__), "config.py")
with open(config_path) as f:
    content = f.read()

if 'UNSPLASH_ACCESS_KEY = ""' in content:
    content = content.replace(
        'UNSPLASH_ACCESS_KEY = ""',
        f'UNSPLASH_ACCESS_KEY = "{key}"'
    )
    with open(config_path, "w") as f:
        f.write(content)
    print(f"\n✅  API key saved to config.py")
elif f'UNSPLASH_ACCESS_KEY = "{key}"' in content:
    print(f"\nℹ️  Key already set in config.py")
else:
    print("\n⚠️  Could not automatically update config.py.")
    print(f'    Please manually set: UNSPLASH_ACCESS_KEY = "{key}"')

# Now fetch all 7 photos
print("\n📸  Downloading background photos for all 7 themes...\n")
from photo_fetcher import refresh_all_photos, get_cache_status

refresh_all_photos(force=True)

print("\n── Cache Status ──────────────────────────────────────")
for theme, info in get_cache_status().items():
    icon = "✅" if info["valid"] else "❌"
    by = f"by {info['photographer']}" if info["photographer"] else ""
    print(f"  {icon}  {theme:<20} {by}")

print("\n✨  All done! Run 'python generate_poster.py --all' to generate posters.\n")
