import json

from bouncer.api.investigations import public_legacy


def test_public_campaign_references_cannot_expose_account_names():
    snapshot = {
        "synthetic": True,
        "sessions": [
            {
                "id": "session",
                "ip": "192.0.2.1",
                "started_at": "2026-11-14T00:00:00Z",
                "ended_at": "2026-11-14T00:00:00Z",
                "requests": [],
            }
        ],
        "campaigns": [
            {
                "id": "stuffing:private-account@example.org",
                "kind": "credential_stuffing",
                "session_ids": ["session"],
            }
        ],
        "verdicts": {
            "session": {"label": "bad_bot", "campaign_id": "stuffing:private-account@example.org"}
        },
    }
    safe = public_legacy(snapshot)
    assert "private-account" not in json.dumps(safe)
    assert safe["campaigns"][0]["id"] == safe["verdicts"]["session"]["campaign_id"]
