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

## Kaista C — Joonas (kampanjat + selitykset) · luonnos T+38

**Beat (~30–40 s after demo session detail):**

1. **Swarm:** "Yksi IP on helppo. Me yhdistämme kymmenet IP:t samaksi toimijaksi — sama käyttäjätunnus, sama polkujärjestys, sama ajoitus."
2. **Live wow:** credential stuffing → kampanja ilmestyy dashboardiin (graafi: IP → session → campaign).
3. **Honesty:** "Jaetun NAT:n / venue-WiFin takana monta ihmistä näyttää yhdeltä — sen me *tiedämme* ja suodatamme / kirjaamme `known_weaknesses`-listaan."
4. **Explain:** "LLM ei päätä. Se vain selittää valmiit syyt Hostinger AI Routerilla — jos Router kaatuu, näytetään silti syyt."

**Slide bullets (C):**
- Kampanja = stuffing ∪ behavior-klusteri (header FP + path Jaccard)
- `campaign_metrics`: purity / coverage vs A:n sim-kampanja-id
- Known weakness: shared NAT
- Selitys = grounded reasons only

**Q&A (C):**
| Question | Answer |
|---|---|
| How is this not just Cloudflare? | We publish FPR + known weaknesses; every decision has 3 readable reasons; we recommend, we don't silently block. |
| What if DNS fails for real Googlebot? | `verified_bot=None` — we do **not** call it fake (S4). |
| Why two detection lanes? | Ablation: session features alone vs + network/campaign signals. |
