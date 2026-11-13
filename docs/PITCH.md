# Pitch

Target: **3 minutes** + Q&A. Write it out, then cut 20%.

## Structure

| Time | Beat | Content |
|---|---|---|
| 0:00–0:15 | Hook | One sentence the judges remember. No "hi, we are team..." |
| 0:15–0:45 | Problem | Who, how often, what it costs. One story. |
| 0:45–1:45 | Demo | Live flow, 3 clicks, visible outcome. Narrate the value, not the UI. |
| 1:45–2:15 | How | Architecture in one breath: "web app, API, Postgres, one external model". |
| 2:15–2:45 | Impact | Market size, one traction signal, what happens Monday. |
| 2:45–3:00 | Ask | What you want from the judges/partners. Be specific. |

## Slide skeleton (max 6)

1. Product name + one-liner + screenshot
2. Problem (one stat, one face)
3. Solution in one diagram
4. Live demo (blank slide — the product is the slide)
5. Traction / validation (even if it is "5 users, 3 said they'd pay")
6. Team + ask

## One-liner variants

- **For judges:** "We turn X into Y in Z seconds."
- **For a stranger:** "You know how ...? We fix that."
- **For the track sponsor:** tie directly to their API/business goal.

## Q&A bank

| Question | Answer (30s max) |
|---|---|
| How is this different from <incumbent>? | |
| How do you make money? | |
| What is the hardest technical part? | |
| What breaks at 10k users? | |
| What did you not have time to do? | Answer honestly, then name the next step. |
| Why this team? | |

## Delivery rules

- Rehearse twice out loud with a timer; cut anything that does not earn its seconds.
- Never read slides. Never apologize for what is missing.
- If the demo fails: switch to the backup video in 5 seconds, keep talking.

---

## Kaista C — Joonas (kampanjat + selitykset) · C-11 luonnos

**Spoken beat (~35 s, after session detail in demo):**

1. **Swarm:** "One IP is easy. We stitch dozens of IPs into one actor — same username, same path order, same timing window."
2. **Live wow:** Point at stuffing campaign on the graph (IP → session → campaign). "That is not one bot. That is a campaign."
3. **Honesty:** "Shared NAT and venue Wi-Fi look like one actor — we detect that pattern, suppress the false campaign, and list it under known weaknesses."
4. **Explain:** "The LLM never decides. Hostinger AI Router only narrates B and C reasons; if the router is down, you still see the reasons."

**Slide bullets (C) — one slide:**
- Campaign = credential stuffing ∪ behavior cluster (header FP + path Jaccard + time overlap)
- Metrics: purity / coverage vs simulator `campaign_id` (S9) — locked only on labeled traffic
- Known weakness: shared NAT / venue Wi-Fi / mobile carrier NAT
- Explain = grounded reasons only (fallback without API key)

**Integration note for demo (A):** `network_pass(sessions)` → `campaigns_api` + `graph` for UI; B gets `intel_by_ip_contract` + `campaign_by_session`.

**Q&A (C):**
| Question | Answer |
|---|---|
| How is this not just Cloudflare? | We publish FPR + known weaknesses; every decision has ≤3 readable reasons; we recommend, we don't silently block. |
| What if DNS fails for real Googlebot? | `verified_bot=None` — we do **not** call it fake (S4). |
| Why two detection lanes? | Ablation: session features alone vs + network/campaign signals — C's value is one number. |
| Can the LLM invent threats? | Groundedness check rejects text outside the reason tokens; otherwise fallback. |
