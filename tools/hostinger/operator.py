"""Authenticated operator smoke test on the owned Bounceri deployment only.

Uses the private generated credential file without printing bearer tokens.
No model inference is requested by the enforcement check.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx

from bouncer.enforcement import issue_token

API = "https://bounceri.srv2159025.hstgr.cloud"
DEMO = "https://demo-bounceri.srv2159025.hstgr.cloud"


def smoke(secrets: dict, *, local: bool = False) -> dict:
    api, demo = ("http://127.0.0.1:18181", "http://127.0.0.1:18180") if local else (API, DEMO)
    admin = {"Authorization": "Bearer " + secrets["BOUNCER_ADMIN_TOKEN"]}
    actor = lambda name: {  # noqa: E731
        "Authorization": "Bearer " + issue_token(name, secrets["BOUNCER_DEMO_ACTOR_SECRET"])
    }
    policies = []
    with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
        cases_response = client.get(api + "/api/investigations")
        cases_response.raise_for_status()
        cases = cases_response.json()
        if not cases:
            raise ValueError("No published synthetic investigation; wait for ingestion")
        case = cases[0]
        route = api + f"/api/investigations/{case['id']}/enforcements"

        def approve(action, ttl):
            response = client.post(
                route,
                headers=admin,
                json={
                    "actor_id": "attack",
                    "action": action,
                    "ttl_seconds": ttl,
                    "evidence_version": case["evidence_version"],
                    "evidence_hash": case["evidence_hash"],
                },
            )
            response.raise_for_status()
            policy = response.json()
            policies.append(policy["id"])
            return policy

        def probe(name):
            return client.get(
                demo + f"/enforcement-demo/{name}/probe", headers=actor(name)
            ).status_code

        try:
            approve("rate_limit", 30)
            rate_statuses = [probe("attack") for _ in range(4)]
            benign = probe("benign")
            assert rate_statuses == [200, 200, 200, 429], "Rate-limit HTTP effect mismatch"
            assert benign == 200, "Benign demo actor was affected"
            policy = approve("temporary_block", 3)
            block_status = probe("attack")
            assert block_status == 403, "Temporary-block HTTP effect mismatch"
            assert probe("benign") == 200
            assert client.get(api + "/api/healthz").status_code == 200
            time.sleep(max(0, policy["expires_at"] - time.time()) + 0.3)
            expired_status = probe("attack")
            assert expired_status == 200, "Expired test policy still affected actor"
            approve("temporary_block", 30)
            revoke = client.delete(api + f"/api/enforcements/{policies[-1]}", headers=admin)
            revoke.raise_for_status()
            revoked_status = probe("attack")
            assert revoked_status == 200, "Revocation did not restore access"
            return {
                "rate_limit_statuses": rate_statuses,
                "temporary_block_status": block_status,
                "benign_actor_status": benign,
                "after_expiry_status": expired_status,
                "after_revoke_status": revoked_status,
                "paid_model_requests": 0,
                "scope": "Authenticated synthetic demo actors only",
            }
        finally:
            for policy_id in policies:
                client.delete(api + f"/api/enforcements/{policy_id}", headers=admin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("smoke-enforcement",))
    parser.add_argument(
        "--secrets", type=Path, required=True, help="Generated .env.hostinger JSON file"
    )
    parser.add_argument("--local", action="store_true")
    args = parser.parse_args()
    try:
        private = json.loads(args.secrets.read_text(encoding="utf-8"))
        print(json.dumps(smoke(private, local=args.local), indent=2))
    except Exception as exc:
        # Remote errors and credential-bearing URLs are never printed.
        print(f"Operator check failed ({type(exc).__name__}); inspect sanitized service status.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
