"""Run one bounded review worker: python -m bouncer.review.worker [--once]."""

from __future__ import annotations

import argparse
import json
import os
import time

from .config import ReviewSettings, capabilities
from .runner import ReviewRunner


def main(argv=None, *, store_factory=None, transport=None) -> int:
    parser = argparse.ArgumentParser(description="Bounceri advisory review worker (no retries)")
    parser.add_argument("--once", action="store_true", help="Claim at most one job and exit")
    parser.add_argument("--capabilities", action="store_true", help="Report sanitized capabilities")
    parser.add_argument(
        "--database-url",
        default=os.getenv("BOUNCER_DATABASE_URL", os.getenv("BOUNCERI_DATABASE_URL", "")),
    )
    parser.add_argument("--worker-id", default="review-worker-1")
    parser.add_argument("--poll-seconds", type=float, default=5)
    args = parser.parse_args(argv)
    settings = ReviewSettings.from_env()
    if args.capabilities:
        print(json.dumps(capabilities(settings), sort_keys=True))
        return 0
    if not args.database_url:
        parser.error("BOUNCER_DATABASE_URL or --database-url is required")
    if not 1 <= args.poll_seconds <= 60:
        parser.error("--poll-seconds must be between 1 and 60")
    if store_factory is None:
        from bouncer.investigations import InvestigationStore

        store_factory = InvestigationStore
    try:
        store = store_factory(args.database_url)
        runner = ReviewRunner(store, settings, transport=transport, worker_id=args.worker_id)
        while True:
            processed = runner.run_once()
            if args.once:
                return 0
            if not processed:
                time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        return 0
    except Exception:
        # Leave running jobs/unknown reservations intact, do not restart an inference here.
        # Operational errors can contain DSN credentials, so expose a fixed diagnostic only.
        print("Review worker stopped after a persistence/runtime error; no request was retried.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
