#!/usr/bin/env python3
"""
Daily Inspirational Poster — Entry Point

Usage:
    python generate_poster.py              # Generate today's poster
    python generate_poster.py --day sunday # Generate for a specific day
    python generate_poster.py --all        # Generate all 7 days (samples)
"""

import argparse
import sys
import os

# Ensure the project directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from poster_generator import generate_poster_html, generate_all_sample_posters


def main():
    parser = argparse.ArgumentParser(description="Generate daily inspirational poster")
    parser.add_argument("--day", type=str, help="Day of week (e.g., sunday, monday)")
    parser.add_argument("--all", action="store_true", help="Generate all 7 sample posters")
    parser.add_argument("--cycle", type=int, default=0, help="Quote rotation index")
    args = parser.parse_args()

    if args.all:
        paths = generate_all_sample_posters(cycle=args.cycle)
        print(f"\nAll {len(paths)} posters generated successfully.")
        for day, path in paths.items():
            print(f"  {day}: {path}")
        return

    day_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }

    day_of_week = None
    if args.day:
        day_of_week = day_map.get(args.day.lower())
        if day_of_week is None:
            print(f"Unknown day: {args.day}. Use one of: {', '.join(day_map.keys())}")
            sys.exit(1)

    path = generate_poster_html(day_of_week=day_of_week, cycle=args.cycle)
    print(f"Poster generated: {path}")


if __name__ == "__main__":
    main()
