# Hostinger — Decode the Noise

> **Status 2026-11-14:** Bouncerin synteettinen HTTP-demo, dashboard,
> investigation-tallennus ja asynkroninen kahden Featherless-roolin arviointi on
> toteutettu. Hostinger-deploy ja maksullinen synteettinen arviointi on kirjattu
> [runtime-ohjeeseen](../../docs/HOSTINGER_LIVE.md) ja
> [validointiraporttiin](../../docs/LIVE_AI_VALIDATION.md). Tämä päivitys perustuu
> koodiin ja kirjattuihin tuloksiin, ei uuteen live-terveystarkistukseen.

**Bounceri** auttaa sivuston omistajaa arvioimaan liikennettä havaintojen perusteella
ja palauttaa `uncertain`, kun näyttö ei riitä. Julkinen dashboard:
[bounceri.tech](https://bounceri.tech). Julkinen demo on synteettinen; oikea seurattu
liikenne vaatii ylläpitäjän tunnistautumisen.

| Tiedosto | Sisältö |
|---|---|
| [IDEA.md](IDEA.md), [ARCHITECTURE.md](ARCHITECTURE.md) | Alkuperäinen hackathon-suunnitelma ja rakenne; nykytila alla ja runtime-ohjeessa |
| [TEAM.md](TEAM.md) | Vastuut, nykyiset sopimusrajat ja historiallinen T+-integraatiosuunnitelma |
| [TODO.md](TODO.md) | Nykyinen vaiheistus ja erikseen säilytetty historiallinen kanban |
| [MODULES.md](../../docs/MODULES.md) | Moduulien kysymykset, syötteet, näyttö, labelit, rajat ja mittarit |
| [RUNTIME-PLAN.md](../../docs/RUNTIME-PLAN.md) | Toteutettu runtime ja seuraavat portit |

## Toteutettu ja vielä avoin

| Alue | Toteutettu | Avoin raja |
|---|---|---|
| A — alusta | Caddy-demo, allekirjoitetut simulaattorit, worker, JSON-yhteensopivuusstore/lataajat, API ja dashboard; PostgreSQL-investigations, arviointijonot/budjetti ja rajattu manuaalinen testienforcement | Yhtenäinen versioitu migraatioajo, liikenteen kestävä SQL-tallennus/checkpointit, yksityinen loki-import ja operatiiviset tarkistukset |
| B — sessiot/arviointi | Piirteet, `rules-v2`, valinnainen mallipolku, datasetti/arviointi, ablaatio ja hidden-ajotyökalut | Suostumukselliset riippumattomat ihmislabelit, vuotovapaa oikean datan arviointi ja aidosti ulkopuolisesti pidetty hyökkäys |
| C — verkosto/arviointi | IP/DNS-funktiot, HTTP-kampanjat, NAT-suodatus, selitykset sekä bounded decision → final advisory review -runner/worker | Hosted-workerin `intel_fn=None` ei osoita live-DNS-varmennusta; nykyinen redaktoitu mallipaketti ei sisällä kampanjasuhteita tai crawler-varmennuksen provenienssia |
| Uudet moduulit | Vain suunnitelma ja capability-paikkamerkit | Trust the Source, sosiaalinen Spot the Swarm ja tekstin Name the Technique: kaikki `implemented=false`, `enabled=false` |

S2:n session/kampanjasessio/label-ID:t ovat `str`. S3:n `load_sessions()` ja
`load_labels()` toimivat JSON-adapterista; tämä ei tarkoita, että liikenteen SQL
repository olisi toteutettu. S10:n labelit on allekirjoitettu; ne eivät mene
mallin havaintopakettiin. S11:n ansareitit ovat demosivussa. S7:n vanhan
selityspolun lisäksi nykyinen investigation-arviointi on toteutettu kahdella
Featherless-roolilla ja yhteisellä persistentillä kulukatolla. Native Microsoft
Decision on erikseen varmennettava, toistaiseksi unavailable-optio.

## Mitä luvut osoittavat

`models/metrics.json` on edelleen production-stub, tulokset `null`.
[Erillinen synteettinen benchmark](../../docs/EVALUATION.md) sisältää reserved-
osassa 14 simuloitua ihmissessiota: 0 väärää positiivista, mutta 95 % Wilson-yläraja
on 21,53 %. Se ei osoita alle 1 %:n oikeiden ihmisten FPR:ää. Tunnetut generaattorin
mallit eivät ole aidosti piilotettu hyökkäys.

[Kirjatussa live-mallikokeessa](../../docs/LIVE_AI_VALIDATION.md) jokainen hyväksytty
lopullinen arvio oli `uncertain`. Koe osoitti sopimusyhteensopivuutta, ei parempaa
tunnistuslaatua. Oikean liikenteen, simulaation ja aidosti piilotetun arvioinnin
tuloksia ei yhdistetä eikä mallin arviota muuteta totuuslabeliksi.

## Seuraavaksi

Nykyinen työ etenee [modules plan.md](../../modules%20plan.md) -järjestyksessä:
vaihe 0 sovittaa dokumentit ja tarkistaa lähtötason; vaihe 1 koventaa nykyisen
ytimen ennen uusien moduulien toteutusta. [TODO.md](TODO.md) kertoo työtilan.

13.11.2026 README kuvasi vielä starter-vaihetta (PR #5/#11, #6–#10/#12 ja #8):
simut, worker, API/dashboard ja live-arviointi olivat silloin handoffeja tai
vahvistamattomia. Se on historiallinen tilanne, jonka yllä oleva koodiin ja
raportteihin perustuva tilanne korvaa. Alkuperäisen T+-kanbanin ulkoisia tehtäviä,
mentorivastauksia, ihmiskeräystä, palautusta tai hidden-hyökkäystä ei merkitä
valmiiksi pelkän toteutuskoodin perusteella.
