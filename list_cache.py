"""
Free, no-API-cost tool. Lists the cached mp3 clips in cache/, sorted by
when they were created (i.e. roughly the order they were synthesized in),
alongside their duration. Use this to scrub through a section's clips in
sequence and find the exact clip where an unexpected extra voice appears
-- since they're already downloaded and cached, listening to them costs
nothing further.

Usage:
    python list_cache.py cache
    python list_cache.py cache --after "2025-01-01 12:00"   # narrow the window
"""
import argparse
import datetime
import os

from pydub.utils import mediainfo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cache_dir", nargs="?", default="cache")
    ap.add_argument("--after", help="Only show files created after this local time, e.g. '2025-01-01 12:00'")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    after_ts = None
    if args.after:
        after_ts = datetime.datetime.fromisoformat(args.after).timestamp()

    files = []
    for name in os.listdir(args.cache_dir):
        if not name.endswith(".mp3"):
            continue
        path = os.path.join(args.cache_dir, name)
        mtime = os.path.getmtime(path)
        if after_ts and mtime < after_ts:
            continue
        files.append((mtime, path))

    files.sort()
    if not files:
        print("No cached clips found (check --after, or the cache_dir path).")
        return

    print(f"{len(files)} clips, oldest first. Play them in this order to scrub through a run:\n")
    for mtime, path in files[: args.limit]:
        ts = datetime.datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
        try:
            info = mediainfo(path)
            dur = float(info.get("duration", 0))
        except Exception:
            dur = 0
        print(f"[{ts}]  {dur:5.1f}s  {path}")

    if len(files) > args.limit:
        print(f"\n...and {len(files) - args.limit} more (raise --limit to see them).")


if __name__ == "__main__":
    main()