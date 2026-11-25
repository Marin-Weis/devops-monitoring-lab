#!/usr/bin/env python3
"""Generate HTTP traffic against the application to populate dashboards.

Usage: python scripts/loadgen.py [--url URL] [--rps 10] [--duration 120]
"""
import argparse
import concurrent.futures
import time
import urllib.error
import urllib.request


def hit(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except OSError:
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8081/work")
    parser.add_argument("--rps", type=int, default=10, help="requests per second")
    parser.add_argument("--duration", type=int, default=120, help="duration in seconds")
    args = parser.parse_args()

    stats: dict[int, int] = {}
    end = time.time() + args.duration
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.rps * 2) as pool:
        while time.time() < end:
            tick = time.time()
            for status in pool.map(hit, [args.url] * args.rps):
                stats[status] = stats.get(status, 0) + 1
            time.sleep(max(0.0, 1.0 - (time.time() - tick)))
    print("HTTP status summary:", dict(sorted(stats.items())))


if __name__ == "__main__":
    main()
