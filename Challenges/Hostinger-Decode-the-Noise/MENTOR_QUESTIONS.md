# PRE-4 — kysymykset Hostingerin mentoreille (Joonas / kaista C)

Status: **kysyttävä kick-offissa / Hostinger-pisteellä**. Ruksi kun vastattu; kirjaa vastaus `docs/DECISIONS.md`:hen.

## Pakolliset

- [ ] **Saaako Postgres/TimescaleDB olla muualla kuin Hostinger-VPS:llä** (esim. Aiven, Neon, Tiger Cloud), jos app + Caddy pyörivät Hostingerilla?
- [ ] **Microsoft-Decision-1 Hostinger Routerissa:** vahvista tarkka model-id, endpoint, pyyntömuoto, käyttörajat ja kreditit. Generatiivinen arvioija on Featherless (päätös 057); Gemini ei ole runtime-suunnitelmassa.
- [ ] **Kelpaako self-hosted TimescaleDB** (`timescale/timescaledb` Dockerissa VPS:llä) MLH *Best Use of Tiger Data* -sivupalkintoon, vai vaaditaanko Tiger Cloud?

## Hyödylliset

- [ ] AI Router: rate limit, saldo-näkymä, suositeltu malli selitystekstille (lyhyt, halpa)?
- [ ] Hostinger Connector / MCP: voiko domainin + VPS-deployn ajaa suoraan Cursorista hackathon-aikana?
- [ ] Onko VPS:llä valmiita outbound-rajoituksia (DNS PTR, SMTP, jne.) jotka rikkovat Googlebot-varmistuksen?

## Vastaukset

| Kysymys | Vastaus | Päätös # |
|---|---|---|
| DB muualla? | | |
| Decision-1 endpoint, model-id ja rajat? | | |
| Tiger Data self-hosted? | | |
