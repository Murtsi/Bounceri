# `src/bouncer/explain` — kaista C (Joonas)

| Funktio | Sopimus | Status |
|---|---|---|
| `explain(verdict, session, campaign)` | S7 | Featherless kun avain ja eksplisiittinen malli on asetettu; groundedness-tarkistus, muuten fallback |

Nykyinen S7-moduuli selittää paikallisen tunnistimen päätöksen. Se ei vielä toteuta suunniteltua Decision-1 → lopullinen arvioija -orkestrointia.

## Featherless

- `LLM_PROVIDER=featherless` (oletus)
- `FEATHERLESS_API_KEY`: vain palvelimen salaisessa ympäristökonfiguraatiossa
- `LLM_MODEL`: kopioi tarkka, tilillä sallittu `org/model`-tunniste Featherlessin malliluettelosta; oletusmallia ei arvata
- API: `https://api.featherless.ai/v1`; Pythonin `openai`-SDK tarvitaan vain LLM-polulle

Ilman avainta, mallia tai SDK:ta käytetään paikallista varatekstiä. Kutsun aikaraja on 20 s, automaattisia SDK-uusintoja ei tehdä ja vastausraja on 220 tokenia. Virhe ei vaihda toiseen maksulliseen palveluntarjoajaan. Kokonaisbudjetin kirjanpito kuuluu tulevaan orkestraattoriin; tämä ei yksin takaa 5 dollarin kokonaisrajaa.

Vanha Hostinger-selityspolku on edelleen käytettävissä vain valinnalla `LLM_PROVIDER=hostinger`, eksplisiittisellä `LLM_MODEL`:lla ja Hostinger/OpenAI-avainmuuttujilla. Gemini-oletus on poistettu. Välimuistin avain sisältää valitun palveluntarjoajan ja mallin.

API-avainta ei ole tallennettu tai live-yhteyttä testattu tässä muutoksessa. Katso [valittu runtime-suunnitelma](../../../docs/RUNTIME-PLAN.md).
