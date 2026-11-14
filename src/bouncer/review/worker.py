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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Claim at most one job and exit")
    mode.add_argument("--capabilities", action="store_true", help="Report sanitized capabilities")
    mode.add_argument(
        "--close-interrupted", metavar="JOB", help="Close one job owned by a stopped worker"
    )
    parser.add_argument(
        "--confirm-worker-stopped",
        action="store_true",
        help="Acknowledge that the specified owning worker has stopped before closing its job",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("BOUNCER_DATABASE_URL", os.getenv("BOUNCERI_DATABASE_URL", "")),
    )
    parser.add_argument("--worker-id", help="Worker identity (required explicitly for recovery)")
    parser.add_argument("--poll-seconds", type=float, default=5)
    args = parser.parse_args(argv)
    if args.close_interrupted:
        if not args.confirm_worker_stopped or not args.worker_id or not args.worker_id.strip():
            parser.error("--close-interrupted requires --worker-id and --confirm-worker-stopped")
    elif args.confirm_worker_stopped:
        parser.error("--confirm-worker-stopped requires --close-interrupted")
    if args.capabilities:
        print(json.dumps(capabilities(ReviewSettings.from_env()), sort_keys=True))
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
        if args.close_interrupted:
            store.close_interrupted_job(args.close_interrupted, args.worker_id)
            print("Interrupted review closed; dispatched charge reservations retained; no retry.")
            return 0
        runner = ReviewRunner(
            store,
            ReviewSettings.from_env(),
            transport=transport,
            worker_id=args.worker_id or "review-worker-1",
        )
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
