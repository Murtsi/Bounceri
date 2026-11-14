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
- **LLM:** Featherless oletuksena selityksille/arvioijalle; eksplisiittinen `LLM_MODEL`. Hostinger AI Router säilyy suunnitellun Decision-1-vaiheen reittinä (päätös 061).
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

## 4. Kaistat (suositus, ei esto)

Kaistat kuvaavat **osaamisalueita ja oletusvastuita**, eivät kieltoa koskettaa toisen polkuja. Hackathonissa kuka tahansa saa korjata pullonkaulan millä tahansa kaistalla — kirjaa muutos changelogiin oikealla `[A]`/`[B]`/`[C]`/`[X]`-tunnisteella.

| Kaista | Kuka (oletus) | GitHub | Haarat | Tyypilliset polut |
|---|---|---|---|---|
| A — alusta + hyökkääjä | Murtsi | `@Murtsi` | `a/…` | `deploy/`, `src/site/`, `src/bouncer/{ingest,db,api}/`, `contracts.py`, `samples/`, `tools/sim/`, `frontend/`, CI |
| B — session tunnistus + arviointi | Niko | `@leppiskerttu` | `b/…` | `src/bouncer/{session,eval}/`, `models/`, `notebooks/b/`, `tests/b/` |
| C — verkosto + kampanjat + selitykset | Joonas | `@Joonaswaa` | `c/…` | `src/bouncer/{network,explain}/`, `notebooks/c/`, `tests/c/` |

- **CODEOWNERS** pyytää edelleen katselmointia omistajalta — se on review-apuri, ei merge-kielto.
- **Tietokantaan kirjoitus** pidetään yhdessä paikassa (`bouncer.db` / ingest-worker), jotta rivit eivät kilpaile.
- **Sopimukset (S1–S11)** muuttuvat mieluiten kaikkien kolmen hyväksynnällä → `BREAKING:` changelogiin + päätösmerkintä. Kiireessä tee muutos ja merkitse päätökseen `needs-ack`.
- AI-agentti: auta käyttäjän prioriteetin mukaan; älä jää odottamaan kaistarajaa jos käyttäjä pyytää toisen kaistan työtä.

## 5. Työnkulku

1. `git switch main && git pull --rebase`
2. `git switch -c <kaista>/<lyhyt-nimi>` — esim. `b/session-features` tai `a/s3-loader`
3. Pienet commitit, Conventional Commits kaistan kanssa: `feat(b/session): add inter-arrival CV feature`
4. Päivitä `CHANGELOG.md` (+ `DECISIONS.md` / `TODO.md` tarvittaessa) **samassa commitissa**
5. `make check` ennen pushia
6. PR `main`-haaraan, yksi katselmoija, merge heti kun vihreä

`main` käynnistyy aina. Rikkinäinen `main` on P0, ja sen rikkonut korjaa sen ensin.

## 6. Valmis kun

- [ ] Toimii puhtaasta checkoutista
- [ ] `make check` ja kosketettujen kaistojen testit menevät läpi
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
- Tee käyttäjän pyytämä työ; kaistarajat eivät estä A/B/C-polkuja.
- Älä pushaa `main`-haaraan äläkä tee force-pushia ilman käyttäjän lupaa.
- Älä commitoi `.env`-tiedostoa, API-avaimia tai AI Routerin avainta.
- Pidä muutokset pieninä ja kirjaa ne (kohta 3) samassa commitissa.
- Jos jokin tässä tiedostossa on vanhentunut, korjaa se ja kirjaa korjaus changelogiin.
