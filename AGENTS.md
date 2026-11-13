# AGENTS.md

Ohjeet **kaikille**, jotka muuttavat tätä repoa: tiimiläisille ja AI-agenteille (Claude Code, Codex, Cursor, Copilot…). Lue tämä ennen ensimmäistä muutosta. Jos tämä ja jokin muu ohje ovat ristiriidassa, tämä voittaa — korjaa ristiriita.

## 1. Mikä tämä repo on

Junction 2026 -hackathonin tiimirepo. Kolme henkeä, 48 tuntia.

| Polku | Mitä |
|---|---|
| `Challenges/<haaste>/` | Haastekohtaiset suunnitelmat: `IDEA.md`, `ARCHITECTURE.md`, `TEAM.md` (kaistat ja sopimukset), `TODO.md` (kortit) |
| `docs/DECISIONS.md` | Päätösloki — stack ja kaikki, mitä joku voisi kyseenalaistaa |
| `CHANGELOG.md` | **Jokainen muutos** (ks. kohta 3) |
| `src/bouncer/` | Python-backend (FastAPI, worker, tunnistus) |
| `frontend/` | TypeScript + React -frontend |
| `deploy/` | Caddy, Docker Compose VPS:lle |
| `tools/` | Simulaattorit ja apuskriptit |
| `tests/` | Testit kaistoittain |

Aktiivinen haaste: **Hostinger — Decode the Noise** (`Challenges/Hostinger-Decode-the-Noise/`), ellei `docs/DECISIONS.md` sano toisin.

## 2. Stack

Kiinnitetty `docs/DECISIONS.md` (004–012). Älä vaihda teknologiaa ilman uutta päätösmerkintää.

- **Backend:** Python 3.12, FastAPI, Pydantic v2, `uv`, `ruff`, `pytest`
- **Frontend:** TypeScript, React 19, Vite, Tailwind CSS v4, shadcn/ui, TanStack Query, Recharts, `pnpm`
- **Tietokanta:** PostgreSQL 16 + TimescaleDB, `psycopg` 3, SQL-migraatiot `src/bouncer/db/migrations/NNN_*.sql`
- **LLM:** Hostinger AI Router (OpenAI-yhteensopiva), malli `LLM_MODEL`-muuttujasta
- **Ajo:** Docker Compose + Caddy Hostinger-VPS:llä (KVM 2: 2 vCPU, 8 GB RAM, 100 GB NVMe — mitoita sen mukaan)
- **Hostingerin työkalut:** VPS:n hallinta ja deploy Hostinger Connectorin / MCP-palvelimen kautta (docs.hostinger.com/hostinger-connector, github.com/hostinger/api-mcp-server); etusivu Hostinger AI Builderilla
- **AI Router -saldo on koko tiimin yhteinen:** älä aja LLM-kutsuja silmukassa testeissä, käytä välimuistia

## 3. Muutosten kirjaaminen — pakollinen

**Mikään muutos ei ole valmis ennen kuin se on kirjattu.** CI hylkää pushin tai PR:n, joka ei päivitä `CHANGELOG.md`:tä (`scripts/check-changelog.sh`).

### 3.1 `CHANGELOG.md` — jokainen muutos

Lisää rivi `## [Unreleased]` -osion oikeaan alaotsikkoon (`Added` / `Changed` / `Fixed` / `Removed`) **samassa commitissa** kuin muutos:

```
- [B] Session-piirteet v1: tahti, aikavälien vaihtelu, staattisten resurssien osuus (B-2)
- [A] BREAKING: `Session.ua` → `Session.user_agent` (S2, päätös 0NN)
```

Säännöt:
- `[A]`, `[B]`, `[C]` = kaista, `[X]` = yhteinen. Lopussa kortin ID suluissa, jos on.
- Kirjoita **mitä muuttui käyttäjälle tai tiimille**, ei mitä tiedostoja koskit.
- Sopimuksen (S1–S11) tai skeeman muutos alkaa sanalla `BREAKING:`.
- Luvut (`metrics.json`) muuttuvat → kirjaa uusi `model_version` ja miksi luvut muuttuivat.
- Ainoa poikkeus: pelkkä kirjoitusvirheen korjaus — lisää commit-viestiin `[skip changelog]`.

### 3.2 `docs/DECISIONS.md` — jokainen valinta

Kirjaa uusi rivi, kun valitset teknologian, muutat sopimusta, kynnystä, train/test-jakoa tai jätät jotain tietoisesti pois. Muoto on tiedoston lopussa. Jos joku voisi sunnuntaina kysyä "miksi näin?", se kuuluu tänne.

### 3.3 `TODO.md` — korttien tila

Siirrä kortti tilasta toiseen, kun aloitat tai lopetat sen. Jos jäät jumiin yli 15 minuutiksi, kirjaa se *Blocked*-osioon.

## 4. Kaistat ja omistajuus

Lue aktiivisen haasteen `TEAM.md`. Tiivistettynä:

- **Muokkaa vain oman kaistasi polkuja.** Tarvitsetko muutoksen toisen kaistan tiedostoon? Pyydä omistajaa — sopimus puuttuu.
- **Vain kaista A kirjoittaa tietokantaan.** B ja C tekevät puhtaita funktioita.
- **Sopimukset (S1–S11)** muuttuvat vain kaikkien kolmen hyväksynnällä → `BREAKING:` changelogiin + päätösmerkintä.
- AI-agentti: kysy käyttäjältä, mikä kaista hän on, jos se ei käy ilmi haarasta (`a/…`, `b/…`, `c/…`).

## 5. Työnkulku

1. `git switch main && git pull --rebase`
2. `git switch -c <kaista>/<lyhyt-nimi>` — esim. `b/session-features`
3. Pienet commitit, Conventional Commits kaistan kanssa: `feat(b/session): add inter-arrival CV feature`
4. Päivitä `CHANGELOG.md` (+ `DECISIONS.md` / `TODO.md` tarvittaessa) **samassa commitissa**
5. `make check` ennen pushia
6. PR `main`-haaraan, yksi katselmoija, merge heti kun vihreä

`main` käynnistyy aina. Rikkinäinen `main` on P0, ja sen rikkonut korjaa sen ensin.

## 6. Valmis kun

- [ ] Toimii puhtaasta checkoutista
- [ ] `make check` ja oman kaistan testit menevät läpi
- [ ] `CHANGELOG.md` päivitetty (ja `DECISIONS.md`, jos tehtiin valinta)
- [ ] `.env.example` päivitetty, jos lisättiin ympäristömuuttuja
- [ ] Ei salaisuuksia, ei debug-jäänteitä

## 7. Rehellisyyssäännöt (tunnistus ja luvut)

Haasteessa pisteytetään tunnistuksen **rehellisyyttä**. Siksi:

- **Älä koskaan keksi tai pyöristä lukuja edullisemmiksi.** `metrics.json` tulee vain arviointiskriptistä.
- Älä opeta mallia testijoukolla äläkä piilotetulla hyökkäyksellä.
- Raportoi simuloitu, oikea ja piilotettu liikenne erikseen.
- Kun löydät heikkouden, kirjaa se `known_weaknesses`-listaan — älä piilota sitä.
- LLM ei tee tunnistuspäätöksiä; se vain selittää valmiin päätöksen.

## 8. AI-agenteille erikseen

- Lue ennen työtä: tämä tiedosto, aktiivisen haasteen `TEAM.md` ja `TODO.md`, `CHANGELOG.md`:n `[Unreleased]`.
- Pysy käyttäjän kaistassa ja kortissa. Älä "siivoa" muiden kaistojen koodia.
- Älä pushaa `main`-haaraan äläkä tee force-pushia ilman käyttäjän lupaa.
- Älä commitoi `.env`-tiedostoa, API-avaimia tai AI Routerin avainta.
- Pidä muutokset pieninä ja kirjaa ne (kohta 3) samassa commitissa.
- Jos jokin tässä tiedostossa on vanhentunut, korjaa se ja kirjaa korjaus changelogiin.
