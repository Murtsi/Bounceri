# Valio Aimo — Trusted Trade Agents (idea-taso)

> **Status: luonnos.** Nämä ovat alustavia suunnitelmia, eivät päätöksiä. Kun tiimi valitsee haasteen, hyväksytyt osat siirretään repon juuren `docs/`- ja `TODO.md`-tiedostoihin.

Työnimi **Tiski**: Valio Aimon palvelutiski ostoboteille. Agentti hakee tuotteet, hinnat ja saatavuuden ja tilaa itse — vain sen valtuutuksen rajoissa, jonka asiakkaan ihminen on antanut. Kaikki muu menee ihmiselle hyväksyttäväksi, ja jokainen päätös jää luettavaksi lokiksi.

| Tiedosto | Sisältö |
|---|---|
| [IDEA.md](IDEA.md) | Ongelma, ratkaisu, demo, rajaus, riskit, mittarit |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Rakenne, MCP-työkalut, mandaatit, datasuodatin, loki, tietomalli |
| [TEAM.md](TEAM.md) | Kolmen hengen roolit ja rajapinnat |
| [TODO.md](TODO.md) | Vaiheistettu kanban T+0 → palautus |

## Roolit lyhyesti

| | Rooli | Yhdellä lauseella |
|---|---|---|
| **A** | Tukkurin järjestelmä | Rakentaa "Valio Aimon": tuotteet, hinnat, saatavuus, tarjoukset ja tilaukset |
| **B** | Agenttiportti + luottamus | Rakentaa oven, jonka kautta agentit tulevat sisään, ja säännöt siitä mitä ne saavat tehdä |
| **C** | Agentti + ihminen + pitch | Rakentaa ostoagentin, hyväksyntänäkymän ja aikajanan — ja kertoo tarinan |

## Avoimet kysymykset

- [ ] Kuka on A, B, C?
- [ ] Valiolta: tuleeko oma mock-data/API? Mitkä ovat arviointikriteerit?
- [ ] Mikä LLM ostoagentille (sivupalkinnot: Gemini, Nemotron, Codex)?
- [ ] Virallinen palautusaika?
