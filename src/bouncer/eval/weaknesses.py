"""Tunnetut heikkoudet → `metrics.json`:n `known_weaknesses` (S8, AGENTS.md §7).

Kun heikkous löytyy, se lisätään tänne — ei piiloteta. Jokainen rivi kertoo, mitä
emme tunnista tai missä voimme erehtyä, ja miksi. Poista rivi vain, kun korjaus on
`main`issa ja testattu.
"""

from __future__ import annotations

KNOWN_WEAKNESSES: tuple[str, ...] = (
    # Detection coverage
    "The certain rules (rules-v1) do not catch scrapers that use a browser User-Agent and no "
    "vulnerability paths; they stay 'uncertain' until the model (B-6) is trained on real data "
    "and saved (models/model.json).",
    "Rules never decide 'human'; classifying someone as human needs the model and calibrated "
    "thresholds.",
    "Login attacks are only detected through C's campaigns (decision 053): a single "
    "credential-guessing session that is not part of a campaign of ≥ 3 sessions stays "
    "'uncertain', and the model only learns the weight of campaign membership if the training "
    "data contains campaigns.",
    "C's behaviour clustering (behavior_cluster) grouped six simulated humans into one campaign "
    "in the MVP (same browser header fingerprint, similar paths); real people on the same "
    "browser version can look alike. B's campaign rule therefore only covers credential "
    "guessing.",
    "The model (lr-v1) is linear: feature interactions (e.g. a fast pace only without CSS/JS "
    "requests) are invisible unless added as features.",
    "A fake Googlebot/Bingbot from an IP with no PTR record gets verified_bot=None and is not "
    "caught by the fake-crawler rule (decision 027: safer for humans, but some attackers get "
    "through).",
    "The fake-crawler rule only covers Googlebot and Bingbot (decision 026); other crawler "
    "User-Agents (Applebot, YandexBot, …) cannot be verified.",
    # Feature limits
    "Header consistency is only checked on HTML requests and relies on Caddy logging request "
    "headers; a bot that copies browser headers bypasses it.",
    "Sec-CH-UA is only expected from Chromium 89+ over HTTPS; on plain HTTP the feature would "
    "give false signals.",
    "Session = (IP, User-Agent) + 5 min of silence: a bot that rotates its User-Agent or IP "
    "splits into many short sessions, none of which looks suspicious on its own (campaign "
    "detection, lane C, partly covers this).",
    "A shared IP (office, venue Wi-Fi, mobile NAT) merges different people into one session "
    "if their User-Agent is the same.",
    # Data limits
    "Simulated traffic is written by our own attacker team; numbers are reported separately "
    "for simulated and real traffic, and the simulated numbers are probably too good.",
)
