# 🫀 Sintetski angiogrami iz proceduralno generiranih vaskularnih mreža

Napredni računalni cjevovod napisan u programskom jeziku Python za proceduralno generiranje realističnih sintetskih koronarnih angiograma u svrhu treniranja i evaluacije modela za segmentaciju krvnih žila u kardiologiji.

---

## 📋 Sadržaj
- [O projektu](#-o-projektu)
- [Arhitektura sustava (Ključni slojevi)](#-arhitektura-sustava-ključni-slojevi)
- [Glavne značajke](#-glavne-značajke)
- [Tehnička specifikacija i alati](#-tehnička-specifikacija-i-alati)
- [Analiza i zaključak](#-analiza-i-zaključak)
- [Autor](#-autor)

---

## 🚀 O projektu
U suvremenoj obradi medicinskih slika, treniranje dubokih neuronskih mreža često nailazi na prepreku u nedostatku opsežnih i raznolikih stvarnih kliničkih skupova podataka (poput malog broja anotiranih snimaka u javnim bazama poput ASOCA-e)[cite: 17, 21]. Ovaj projekt rješava taj problem generiranjem sintetskih podataka kroz proceduralno modeliranje virtualnih vaskularnih struktura, čime se dobivaju slike koje već u startu sadrže potpuno točne i automatski generirane oznake.

---

## 🏗️ Arhitektura sustava (Ključni slojevi)
Sustav je strukturiran kroz četiri odvojena sloja čiji se doprinosi linearno zbrajaju u jedinstvenu sliku, čime se vjerno simulira fizikalni proces prolaska rendgenskih zraka kroz tkiva:

1. **Watercolor pozadina (Domain Warping):** 
   * Deformacija koordinatnog sustava pomoću dvaju neovisnih polja pomaka dobivenih iz glatkog fraktalnog šuma (5 oktava opadajuće amplitude).
   * Stvara meke, organski razmazane mrlje i izbjegava pravilne kružne uzorke klasičnog Perlinovog šuma.
2. **Vaskularno stablo (Radius-Aware Tube-Shading):**
   * Rekurzivni algoritam grananja od kateterskog uvoda do mikrovaskularnih ogranaka.
   * Primjena Murrayevog zakona za pravilan odnos radijusa roditelja i kćeri grana ($r^3 = \sum r_i^3$).
   * Normalizacija Euklidske udaljenosti na lokalni polumjer žile radi postizanja ispravnog profila s tamnijim rubovima i svjetlijom sredinom lumena.
3. **Anatomska silueta srca:**
   * Elipsoidna implicitna jednadžba s nasumičnim pomacima i polumjerima unutar fizioloških granica.
   * Rubovi su dodatno distorzirani trigonometrijskim funkcijama i zaglađeni Gaussovim filtrom kako bi se uklonio efekt oštre prozirne folije.
4. **Sjene rebara i detektorski efekti:**
   * Simulacija sjena koje rebra ostvaruju kroz radijalne maske i funkcije šuma.
   * Dodavanje kvantnog šuma, usmjerenog zamućenja (motion blur) za simulaciju srčanih pokreta te radijalnog vinjetiranja.

---

## 🛠️ Glavne značajke
* **Potpuna neovisnost uzoraka (`seed`):** Svaki generirani angiogram koristi jedinstvenu cjelobrojnu klicu koja upravlja svim slojevima, osiguravajući kreiranje potpuno novih anatomskih konfiguracija.
* **Fleksibilan pipeline:** Prilagodljivi parametri za kontrast žila, gustoću grananja, razinu šuma i intenzitet vinjetiranja.
* **Vizualizacija:** Skripta automatski generira i prikazuje mrežu od 10 neovisnih sintetskih uzoraka u obliku usporedne matrice.

---

## 📊 Analiza i zaključak
Vizualna analiza generiranih primjera potvrđuje da algoritam uspješno oponaša ključne elemente medicinskih prikaza (prirodno stanjivanje žila, prisutnost katetera, realističnu pozadinu i efekt raspršenja rendgenskih zraka). Iako su uočena određena topološka i fizikalna ograničenja (poput spoja katetera i nedostatka naprednog efekta dubine), projekt predstavlja iznimno brzu i računalno jeftinu alternativu za izgradnju baza podataka namijenjenih unaprjeđenju modela računalnog vida u kardiologiji.

---

## 👤 Autor
* **Lara Lacić**[cite: 15]
* Fakultet elektrotehnike, računarstva i informacijskih tehnologija Osijek (FERIT)
* Sveučilišni diplomski studij Računarstvo
