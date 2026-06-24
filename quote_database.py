"""
Quote database — language-rotating with no verse repeats.

How rotation works:
- Three language pools: english, tamil, sanskrit
- Each day a language is chosen so the same language never appears
  on two consecutive days (true 3-cycle: en → ta → sa → en …)
- Language history is persisted in output/language_history.json
- Within each language pool, verses rotate and never repeat until
  every verse in that pool has been shown — then the cycle resets

Tracking design:
- Verses are identified by "author|||source" (NOT by index position).
  This means adding, removing, or reordering verses in the JSON files
  never corrupts the history — a verse you've seen stays seen regardless
  of where it sits in the file.
- usage_log.json stores used_ids (list of "author|||source" strings)
  per language, plus a last_used date.
"""

import json
import os
from datetime import datetime, timedelta
from config import QUOTES_DIR, DAY_SCHEDULE, LANGUAGES

BASE_DIR           = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR         = os.path.join(BASE_DIR, "output")
USAGE_LOG_PATH     = os.path.join(OUTPUT_DIR, "usage_log.json")
LANG_HISTORY_PATH  = os.path.join(OUTPUT_DIR, "language_history.json")


# ─── Quote loading ────────────────────────────────────────────────────────────

def load_quotes(language: str) -> list:
    """Load all quotes for a given language from its JSON file."""
    filepath = os.path.join(QUOTES_DIR, f"{language}_quotes.json")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _quote_id(quote: dict) -> str:
    """
    Stable, unique identifier for a verse.
    Uses author + source — survives any reordering of the JSON file.
    """
    return f"{quote.get('author', '')}|||{quote.get('source', '')}"


# ─── Language history ─────────────────────────────────────────────────────────

def _load_lang_history() -> dict:
    """Return {date_str: language} mapping."""
    if os.path.exists(LANG_HISTORY_PATH):
        with open(LANG_HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_lang_history(history: dict):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(LANG_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def get_language_for_today(day_of_week: int = None) -> str:
    """
    Determine which language to use today.

    Rules:
    1. If today already has an entry in language_history, return it (idempotent).
    2. Never return the same language as yesterday.
    3. Among the remaining candidates, prefer the language not seen in last 2 days
       (promotes true 3-cycle rather than always alternating two).
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    history   = _load_lang_history()

    if today_str in history:
        return history[today_str]

    yesterday_str     = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    two_days_ago_str  = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    yesterday_lang    = history.get(yesterday_str)
    two_days_ago_lang = history.get(two_days_ago_str)

    candidates = [lang for lang in LANGUAGES if lang != yesterday_lang]
    if not candidates:
        candidates = list(LANGUAGES)

    preferred = [c for c in candidates if c != two_days_ago_lang]
    chosen = preferred[0] if preferred else candidates[0]

    # Persist and trim to last 30 days
    cutoff  = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    history = {k: v for k, v in history.items() if k >= cutoff}
    history[today_str] = chosen
    _save_lang_history(history)

    return chosen


# ─── Usage tracking ───────────────────────────────────────────────────────────

def _load_usage_log() -> dict:
    if os.path.exists(USAGE_LOG_PATH):
        with open(USAGE_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_usage_log(log: dict):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(USAGE_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def _ensure_entry(log: dict, language: str) -> dict:
    """Return the usage entry for a language, creating it if absent."""
    if language not in log:
        log[language] = {"used_ids": [], "last_used": None}
    # Migrate any old index-only entries (used_indices key) to id-based
    if "used_ids" not in log[language]:
        log[language]["used_ids"] = []
    return log[language]


def _mark_used(language: str, quote: dict):
    """Record that a verse has been shown."""
    log   = _load_usage_log()
    entry = _ensure_entry(log, language)
    qid   = _quote_id(quote)
    if qid not in entry["used_ids"]:
        entry["used_ids"].append(qid)
    entry["last_used"] = datetime.now().strftime("%Y-%m-%d")
    _save_usage_log(log)


def unmark_used(language: str, quote_index: int, quote: dict = None):
    """
    Return a verse to the unused pool.

    Called when a poster is skipped or expires without approval so the verse
    can appear again on a future day.  Pass the quote dict when available
    (preferred); falls back to loading by index from the JSON file.

    Also silently ignores legacy day_tag strings (e.g. "monday_poetry")
    that may appear in old pending_approval.json files.
    """
    if language not in LANGUAGES:
        # Legacy day_tag key — ignore gracefully
        return

    # Resolve quote dict if not supplied
    if quote is None:
        try:
            quotes = load_quotes(language)
            if 0 <= quote_index < len(quotes):
                quote = quotes[quote_index]
        except Exception:
            pass

    if quote is None:
        return

    log   = _load_usage_log()
    entry = _ensure_entry(log, language)
    qid   = _quote_id(quote)
    if qid in entry["used_ids"]:
        entry["used_ids"].remove(qid)
        _save_usage_log(log)
        print(f"↩️   Verse '{qid}' returned to '{language}' pool.")


def _get_next_unused(language: str, quotes: list) -> tuple:
    """
    Return (index, quote) of the next verse in this language pool that has
    not yet been shown.  If all have been shown, resets the cycle and starts
    from the beginning of the list.
    """
    log      = _load_usage_log()
    entry    = _ensure_entry(log, language)
    used_ids = set(entry["used_ids"])

    for i, q in enumerate(quotes):
        if _quote_id(q) not in used_ids:
            return i, q

    # Full reset — every verse has been shown; start the cycle over
    entry["used_ids"] = []
    _save_usage_log(log)
    print(f"🔄  All {len(quotes)} {language} verses shown — resetting pool.")
    return 0, quotes[0]


# ─── Main retrieval ───────────────────────────────────────────────────────────

def get_quote_for_day(day_of_week: int = None, cycle: int = None) -> dict:
    """
    Get the next unseen quote for today.

    Args:
        day_of_week: 0=Monday … 6=Sunday.  None = today's actual weekday.
        cycle:       If set, overrides rotation and picks quote at this index
                     (useful for testing — does NOT mark as used).

    Returns:
        Quote dict with all source fields plus injected metadata:
            _language     — which language pool this came from
            _quote_index  — index in the JSON file (informational)
            _quote_id     — stable "author|||source" identifier
    """
    if day_of_week is None:
        day_of_week = datetime.now().weekday()

    language = get_language_for_today(day_of_week)
    quotes   = load_quotes(language)

    if not quotes:
        raise ValueError(f"No quotes found in {language}_quotes.json")

    if cycle is not None:
        index = cycle % len(quotes)
        quote = dict(quotes[index])
    else:
        index, quote = _get_next_unused(language, quotes)
        quote = dict(quote)   # copy so we don't mutate the source list

    # Inject metadata
    quote["_language"]    = language
    quote["_quote_index"] = index
    quote["_quote_id"]    = _quote_id(quote)
    quote["_day_tag"]     = language   # backward-compat alias

    if cycle is None:
        _mark_used(language, quote)

    return quote


def get_quote_for_day_name(day_name: str) -> dict:
    name_to_weekday = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    return get_quote_for_day(name_to_weekday[day_name.lower()])


def get_all_quotes_for_week(cycle: int = 0) -> dict:
    """One quote per day for the full week (cycle mode, no usage log changes)."""
    quotes = {}
    for weekday in range(7):
        schedule = DAY_SCHEDULE[weekday]
        quotes[schedule["label"]] = get_quote_for_day(weekday, cycle=cycle)
    return quotes


def get_rotation_status() -> dict:
    """Summary of how many verses used vs. remaining in each language pool."""
    log    = _load_usage_log()
    status = {}
    for lang in LANGUAGES:
        try:
            total    = len(load_quotes(lang))
            used_ids = log.get(lang, {}).get("used_ids", [])
            used     = len(used_ids)
            status[lang] = {
                "total":     total,
                "used":      used,
                "remaining": total - used,
                "last_used": log.get(lang, {}).get("last_used"),
            }
        except Exception as e:
            status[lang] = {"error": str(e)}
    return status


def add_quote(language: str, quote_dict: dict):
    """Append a new quote to the database JSON file."""
    filepath = os.path.join(QUOTES_DIR, f"{language}_quotes.json")
    with open(filepath, "r", encoding="utf-8") as f:
        quotes = json.load(f)
    quotes.append(quote_dict)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(quotes, f, indent=2, ensure_ascii=False)
    print(f"Added quote to {language}_quotes.json (now {len(quotes)} total)")


def mark_all_as_used(language: str):
    """
    Mark every verse in a language pool as used.
    Useful for seeding history after a migration (so old verses don't repeat).
    """
    quotes = load_quotes(language)
    log    = _load_usage_log()
    entry  = _ensure_entry(log, language)
    for q in quotes:
        qid = _quote_id(q)
        if qid not in entry["used_ids"]:
            entry["used_ids"].append(qid)
    _save_usage_log(log)
    print(f"Marked all {len(quotes)} {language} verses as used.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Language Rotation Status:")
    print("=" * 55)
    history = _load_lang_history()
    for i in range(6, -1, -1):
        d    = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        lang = history.get(d, "(none)")
        marker = " ← today" if i == 0 else ""
        print(f"  {d}  {lang}{marker}")

    print("\nQuote Pool Status:")
    print("=" * 55)
    status = get_rotation_status()
    for lang, info in status.items():
        if "error" in info:
            print(f"  {lang:10s}: ERROR — {info['error']}")
        else:
            bar = "▓" * info["used"] + "░" * info["remaining"]
            print(f"  {lang:10s}: {info['used']:2d}/{info['total']:2d} used  "
                  f"[{bar}]  (last: {info['last_used']})")

    print(f"\nToday's language: {get_language_for_today()}")
