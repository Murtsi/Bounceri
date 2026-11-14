"""`X-Sim-Run`-merkinnän allekirjoitus (S10).

Ongelma: `X-Sim-Run: <ajo>:<luokka>[:<kampanja>]` on oikea vastaus, jolla B opettaa
ja arvioi mallin. Ilman tunnistusta kuka tahansa kävijä voisi lähettää
`X-Sim-Run: x:human` ja saada bottinsa labeloitua ihmiseksi (myrkytetty malli,
väärä FPR-luku).

Ratkaisu (päätös 046): simulaattori lähettää lisäksi otsakkeen

    X-Sim-Sig: hex(HMAC-SHA256(SIM_RUN_SECRET, <X-Sim-Run-arvo>))

Kun `SIM_RUN_SECRET` on asetettu, vain oikein allekirjoitetut merkinnät
hyväksytään. Ilman avainta (paikallinen kehitys, testifixturet) allekirjoitusta ei
vaadita — tuotannossa avain on pakollinen (`.env.example`).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, field

SECRET_ENV = "SIM_RUN_SECRET"
MARKER_HEADER = "x-sim-run"
SIG_HEADER = "x-sim-sig"


def secret_from_env() -> str | None:
    return os.getenv(SECRET_ENV) or None


def sign(marker: str, secret: str) -> str:
    """Simulaattorin puoli: allekirjoitus `X-Sim-Sig`-otsakkeeseen."""
    return hmac.new(secret.encode(), marker.encode(), hashlib.sha256).hexdigest()


def verify(marker: str, signature: str, secret: str) -> bool:
    return bool(signature) and hmac.compare_digest(sign(marker, secret), signature.strip().lower())


@dataclass(slots=True)
class IngestStats:
    """Mitä lukemisessa ohitettiin. Näytetään, ei piiloteta."""

    invalid_records: int = 0
    records: int = 0
    unsigned_markers: int = 0  # avain asetettu, mutta merkintä ilman oikeaa allekirjoitusta
    invalid_markers: int = 0  # väärä muoto, esim. "pelkkä-ajo"
    conflicting_sessions: list[str] = field(default_factory=list)  # eri merkinnät samassa sessiossa
    login_events: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "records": self.records,
            "invalid_records": self.invalid_records,
            "unsigned_markers": self.unsigned_markers,
            "invalid_markers": self.invalid_markers,
            "conflicting_sessions": list(self.conflicting_sessions),
            "login_events": self.login_events,
        }
