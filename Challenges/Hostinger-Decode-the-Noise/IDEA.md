# Idea — "Bouncer" (työnimi)

Haaste: **Hostinger — Decode the Noise**, suunta *Clean the traffic* + palanen *Spot the swarm*.

## One-liner

Bouncer kertoo sivuston omistajalle, kuka sivulla oikeasti käy — ihminen, hyvä botti vai hyökkääjä — ja **miksi**, ja näyttää rehellisesti kuinka usein se on väärässä.

## Problem

Jokainen julkinen sivusto saa skannereita, scrapereita ja varastettujen tunnusten kokeiluja jo tunneissa julkaisusta. Pienen sivuston omistaja näkee vain kasan lokirivejä tai "kävijämäärän", joka on täynnä botteja. Valmiit estotyökalut ovat mustia laatikoita: ne joko estävät liikaa (oikeat asiakkaat ulos) tai liian vähän, eikä kukaan kerro virheprosenttia.

## Solution

1. Sivuston liikenne kulkee Bouncerin läpi (Caddy-reverse proxy, JSON-access-log) — tai omistaja **lataa oman access-lokinsa**.
2. Pyynnöt kootaan **sessioiksi** (IP + UA + aikaikkuna), ja jokaiselle lasketaan selitettäviä piirteitä.
3. Pisteytys antaa tuloksen **ihminen / epävarma / hyvä botti / haitallinen botti** + varmuuden + syyt.
4. Samaan tapaan käyttäytyvät sessiot yhdistetään **kampanjoiksi** ("nämä 37 IP:tä ovat sama toimija").
5. Dashboard näyttää mitä sivulle tulee, ja kielimalli kirjoittaa jokaiselle tapaukselle selkokielisen selityksen ja suositellun toimenpiteen (seuraa → rajoita → haaste → estä).
6. Julkinen `/metrics`-sivu: tarkkuus, false positive rate, sekaannusmatriisi ja tunnetut heikkoudet.

## Target user

| | |
|---|---|
| Primary | Pienen/keskikokoisen sivuston tai verkkokaupan omistaja (Hostingerin tyypillinen asiakas) |
| Secondary | Hostingin tukihenkilö, joka selvittää "miksi sivu on hidas / miksi kirjautumisia tulee tuhansia" |
| Not for | Isot yritykset omalla WAF/SOC-tiimillä; sosiaalisen median sisällön moderointi |

## Why now

- Bottiliikenne on jo yli puolet webin liikenteestä, ja AI-scraperit kasvattavat sitä.
- Kielimallit tekevät selittämisestä halpaa: tunnistus voi olla läpinäkyvää ilman tietoturva-asiantuntijaa.

## Differentiation

| Alternative | Why we win |
|---|---|
| Ei mitään / lokien selaus käsin | Valmis tulkinta + toimenpide, ei lokirivejä |
| Cloudflare / kaupalliset bottisuojat | Selitys jokaiselle päätökselle + julkinen virheprosentti; ei mustaa laatikkoa |
| fail2ban / avoimen lähdekoodin säännöt | Sessiotason piirteet + malli + kampanjoiden tunnistus, ei vain yksittäisiä sääntöjä |

## Demo scenario

1. Avataan dashboard: viimeisen 24 h oikea liikenne omalta VPS:ltä — "tämän verran tuli botteja ilman että kerroimme sivusta kenellekään".
2. Klikataan yhtä sessiota → selitys: "haki 400 sivua 2 minuutissa, ei yhtään CSS/JS-tiedostoa, datakeskus-IP".
3. **Wow:** käynnistetään livenä tunnusten kokeiluhyökkäys → dashboardiin ilmestyy kampanja, joka yhdistää kymmenet IP:t samaksi toimijaksi.
4. Tuomari avaa sivun omalla puhelimellaan → näkyy itse **ihmisenä**.
5. `/metrics`: tarkkuus ja FPR testijoukolla + rehellinen lista siitä, mitä emme tunnista.

## Scope

### Must have (demo breaks without it)
- [ ] VPS pystyssä, julkinen URL, Caddy + demosivusto (jossa kirjautumislomake) + ansapolut
- [ ] Lokien keruu → sessiot → piirteet → pisteytys → Postgres
- [ ] Hyökkäys- ja ihmissimulaattorit (oikeat vastaukset arviointiin)
- [ ] `/metrics` testijoukolla (temporaalinen jako)
- [ ] Dashboard: sessiolista + yksittäisen session selitys

### Should have (judges notice)
- [ ] Kampanjat / swarm-klusterointi
- [ ] LLM-selitykset (Hostinger AI Router)
- [ ] Lokitiedoston lataus: "analysoi oma lokisi"
- [ ] Varmistetut hyvät botit (Googlebot/Bingbot käänteisellä DNS:llä)

### Won't have (say it out loud, it builds credibility)
- [ ] Automaattinen estäminen tuotannossa — me suosittelemme, emme estä
- [ ] TLS-sormenjäljet (JA3/JA4) — vaatisi oman proxyn
- [ ] Tekstipohjainen propagandatunnistus
- [ ] Käyttäjätilit / monen sivuston hallinta

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Liian vähän oikeaa bottiliikennettä | Pieni | VPS julki heti ensimmäisinä tunteina; simulaattorit täydentävät |
| Simuloitu data liian helppoa → epärealistisen hyvä tarkkuus | Suuri | Raportoidaan erikseen: simuloitu vs. ansoista/DNS:stä varmistettu oikea liikenne; yksi hyökkäysskripti pidetään piilossa testiä varten |
| Liian vähän ihmisdataa | Keskisuuri | QR-koodi tapahtumapaikalla, kaverit, Playwright-"ihmiset" erikseen merkittynä |
| Venue-verkko / VPS kaatuu | Pieni | Seed-data + varavideo |
| Scope creep | Suuri | Feature freeze T+40h |

## Metrics (what "works" means)

- **False positive rate ihmisillä** valitulla kynnyksellä (tavoite < 1 %) — tämä on pääluku.
- Precision / recall haitallisille boteille, luokittain (scraper, skanneri, tunnusten kokeilu).
- Osuus liikenteestä, joka jää "epävarma"-luokkaan (rehellisyys > näennäinen tarkkuus).
