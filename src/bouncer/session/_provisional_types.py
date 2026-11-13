"""VANHENTUNUT: käytä `bouncer.contracts`-moduulia (S2).

B:n väliaikaiset tyypit korvattiin A:n `contracts.py`:llä. Tämä moduuli vain
uudelleenvie samat tyypit, koska `tests/a/test_sample_ingest.py` (kaista A)
tuo ne vielä täältä. Poistetaan, kun A:n testi tuo ne suoraan `contracts.py`:stä.
"""

from bouncer.contracts import (
    AsnType,
    Campaign,
    IpIntel,
    Label,
    Request,
    Session,
    SessionLabel,
    Verdict,
)

__all__ = [
    "AsnType",
    "Campaign",
    "IpIntel",
    "Label",
    "Request",
    "Session",
    "SessionLabel",
    "Verdict",
]
