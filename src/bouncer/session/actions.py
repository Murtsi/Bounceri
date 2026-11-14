"""Suositeltu toimenpide päätökselle (IDEA.md: seuraa → rajoita → haaste → estä).

Bouncer suosittelee, se ei estä itse. Toimenpide riippuu siitä, *miksi* sessio on
haitallinen — ei pelkästä luokasta (päätös 055):

| Peruste | Toimenpide | Miksi |
|---|---|---|
| kirjautumishyökkäys (C) | rajoita | hyökkääjä vaihtaa IP:tä → rajoita per tunnus |
| väärennetty crawler, haavoittuvuuspolut, ansa | estä | yksiselitteinen hyökkäys samasta IP:stä |
| malli: haitallinen | haaste | todennäköinen, ei varma → CAPTCHA/JS-haaste ennen estoa |
| epävarma | seuraa | ei näyttöä, ei toimenpidettä |
| ihminen, hyvä botti | ei mitään | |
"""

from __future__ import annotations

from typing import Literal

Action = Literal["none", "monitor", "rate_limit", "challenge", "block"]

ACTION_TEXT: dict[Action, str] = {
    "none": "Ei toimenpidettä",
    "monitor": "Seuraa",
    "rate_limit": "Rajoita",
    "challenge": "Haaste",
    "block": "Estä",
}

_BY_RULE: dict[str, Action] = {
    "login_attack_campaign": "rate_limit",
    "fake_crawler": "block",
    "vuln_paths": "block",
    "trap": "block",
    "verified_crawler": "none",
}


def recommend(label: str, rule_id: str | None) -> Action:
    """Toimenpide luokasta ja varmasta säännöstä (None = mallin tai ei sääntöä)."""
    if rule_id in _BY_RULE:
        return _BY_RULE[rule_id]
    if label == "bad_bot":
        return "challenge"
    if label == "uncertain":
        return "monitor"
    return "none"
