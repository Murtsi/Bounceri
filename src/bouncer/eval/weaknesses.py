"""Tunnetut heikkoudet → `metrics.json`:n `known_weaknesses` (S8, AGENTS.md §7).

Kun heikkous löytyy, se lisätään tänne — ei piiloteta. Jokainen rivi kertoo, mitä
emme tunnista tai missä voimme erehtyä, ja miksi. Poista rivi vain, kun korjaus on
`main`issa ja testattu.
"""

from __future__ import annotations

KNOWN_WEAKNESSES: tuple[str, ...] = (
    # Tunnistuksen kattavuus
    "Varmat säännöt (rules-v1) eivät tunnista scrapereita, jotka käyttävät selain-UA:ta "
    "ilman haavoittuvuuspolkuja; ne jäävät 'uncertain'-luokkaan, kunnes malli (B-6) on "
    "opetettu oikealla datalla ja tallennettu (models/model.json).",
    "Säännöt eivät koskaan päätä 'human'; ihmiseksi luokittelu vaatii mallin ja kalibroidut "
    "kynnykset.",
    "Kirjautumishyökkäykset tunnistetaan vain C:n kampanjan kautta (päätös 053): yksittäinen "
    "tunnusten kokeilu -sessio, joka ei kuulu ≥ 3 session kampanjaan, jää 'uncertain'-"
    "luokkaan, ja malli oppii kampanjajäsenyyden painon vain, jos opetusdatassa on kampanjoita.",
    "C:n käyttäytymisklusterointi (behavior_cluster) niputti MVP:ssä kuusi simuloitua ihmistä "
    "samaksi kampanjaksi (sama selain-otsakesormenjälki, samankaltaiset polut); samaa "
    "selainversiota käyttävät oikeat ihmiset voivat näyttää samalta. B:n kampanjasääntö "
    "koskee siksi vain tunnusten kokeilua.",
    "Malli (lr-v1) on lineaarinen: piirteiden yhteisvaikutukset (esim. nopea tahti vain "
    "ilman CSS/JS-pyyntöjä) eivät näy, ellei niitä lisätä piirteiksi.",
    "Väärennetty Googlebot/Bingbot IP-osoitteesta, jolla ei ole PTR-tietuetta, saa "
    "verified_bot=None eikä jää kiinni väärennössäännöstä (päätös 027: turvallisempi "
    "ihmisille, mutta osa hyökkääjistä menee läpi).",
    "Väärennössääntö kattaa vain Googlebotin ja Bingbotin (päätös 026); muut crawler-UA:t "
    "(Applebot, YandexBot, …) eivät ole varmistettavissa.",
    # Piirteiden rajat
    "Otsakkeiden johdonmukaisuus tarkistetaan vain HTML-pyynnöistä ja riippuu siitä, että "
    "Caddy lokittaa pyynnön otsakkeet; botti, joka kopioi selaimen otsakkeet, ohittaa sen.",
    "Sec-CH-UA odotetaan vain Chromium 89+ -selaimilta HTTPS:llä; HTTP-liikenteellä "
    "piirre antaisi vääriä havaintoja.",
    "Sessio = (IP, User-Agent) + 5 min hiljaisuus: UA:ta tai IP:tä vaihtava botti hajoaa "
    "moneksi lyhyeksi sessioksi, joista yksikään ei näytä epäilyttävältä yksinään "
    "(kampanjatunnistus, kaista C, paikkaa osittain).",
    "Jaettu IP (toimisto, venue-WiFi, mobiili-NAT) yhdistää eri ihmisiä samaan sessioon, "
    "jos UA on sama.",
    # Datan rajat
    "Simuloitu liikenne on hyökkääjätiimin itse kirjoittamaa; luvut raportoidaan erikseen "
    "simuloidulle ja oikealle liikenteelle, ja simuloidun luvut ovat todennäköisesti liian hyviä.",
)
