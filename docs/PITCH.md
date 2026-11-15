# Bounceri — three-minute pitch

Live: https://bounceri.tech · Source: https://github.com/Murtsi/Bounceri

## Three-minute spoken pitch

**Delivery note:** About 380 words, with short pauses for the demo. Rehearse once against the actual screen. The timestamps are pacing guides, not measured delivery times.

### 0:00–0:25 — The owner’s decision

Your website gets a burst of traffic. Is it a new customer, a harmless crawler, or someone trying passwords? For a small business owner, the next decision matters. Ignore a real attack and the site suffers. Interrupt an ordinary visitor and you may lose a customer.

Bounceri helps that owner investigate before acting.

### 0:25–0:50 — The product

We turn access logs into sessions, connect related HTTP activity and show the evidence behind each assessment. Request timing, paths, failed logins and shared targets become something the owner can inspect. When the evidence is insufficient, the result can be uncertain.

This is the working product, running on Hostinger.

### 0:50–1:45 — Show the product

The public demo uses signed synthetic traffic sent through our own service. It exercises the real HTTP pipeline, while keeping simulated traffic separate from real-human evidence.

Open a session. Here are the requests and the local reasons behind its assessment. The owner can check what actually happened.

Now look at a campaign. Several sessions may share a login target or a behavior pattern. That relationship gives the owner another lead to investigate. We do not turn it into a claim about who controls those visitors.

Investigations preserve a redacted evidence snapshot. Optional AI reviews are recorded separately, so an interpretation never replaces the underlying observations.

### 1:45–2:10 — How it works

The system runs on a Hostinger VPS: Caddy, a Python and FastAPI pipeline, PostgreSQL and a React dashboard. Local detection works without an AI key. Optional Featherless reviews answer bounded evidence questions and return an advisory assessment. Backend validation and a shared budget bound that process. Any test enforcement requires explicit manual action.

### 2:10–2:40 — What we have proved

We have a working traffic investigation pipeline. We have not yet proved real-world detection accuracy.

Our separate synthetic test observed zero false positives among fourteen simulated-human sessions. That sample is small: its 95 percent upper confidence bound is 21.53 percent. Accepted final AI reviews in the recorded experiment all remained uncertain. We report those limits because an owner needs to know when the evidence runs out.

### 2:40–3:00 — Next step and ask

Our team brings together platform engineering, session detection and network analysis. Next, we want a consented pilot with small website owners and Hostinger support teams: real logs, independently reviewed sessions and measured false alarms.

Help us test whether this makes their next traffic decision clearer.
