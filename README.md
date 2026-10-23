# Digitaal proces-verbaal (Orange Belgium – oplevering installatie)

Engineer vult het PV in → deelt een korte link → klant tekent op zijn telefoon → de **originele Orange-PDF**
wordt ingevuld, door de klant gedownload en via jouw Gmail naar een zelf gekozen mailadres gemaild. Statische site + Google Apps Script, gratis.

## Structuur
```
werkbon/
├── docs/                       # de website: serveer deze map als webroot
│   ├── index.html              # formulier voor de engineer (hoofdpagina "/")
│   ├── admin/index.html        # stuurt oude bladwijzers door naar "/"
│   ├── CNAME                   # alleen voor GitHub Pages
│   └── sign/
│       ├── index.html          # klantpagina  (link: /sign/#<korte id>)
│       ├── fill.js             # helpers + vult template.pdf in (pdf-lib)
│       ├── config.js           # JOUW NAAM + MAIL_URL (Apps Script)
│       ├── template.pdf        # origineel Orange-PV
│       └── handtekening.png    # JOUW handtekening (.png of .jpg, zelf toevoegen)
├── google-apps-script/mail.gs  # bewaart de PV's (korte id), mailt de getekende PDF
├── tests/e2e.py                # Playwright-test met nagebootst script (25 checks)
└── README.md, package.json, .gitignore
```

## Werking
1. Je opent `https://jouwdomein/`, vult het PV in + je beheerssleutel. Het Apps Script bewaart de gegevens
   onder een korte willekeurige id en je krijgt een link zoals `https://jouwdomein/sign/#k7x2m9qa8d`.
2. De klant opent die link, ziet het PV, vult optioneel opmerkingen + naam in en tekent.
3. De browser maakt de PDF (originele template + invulling + beide handtekeningen) en downloadt hem.
4. De PDF gaat naar het Apps Script, dat hem mailt naar `TO` en daarna het PV wist. De site controleert dat
   wissen en meldt pas "verstuurd" als het echt gelukt is. De link werkt dus maar één keer.

## Installatie
1. `docs/sign/config.js`: je naam. Zet je handtekening in `docs/sign/handtekening.png` (exact die naam, kleine letters).
2. **Apps Script** (script.google.com): nieuw project, plak `mail.gs`, zet `TO` op het ontvangende adres.
   *Project Settings → Script properties*: `ADMIN_KEY` = zelfgekozen wachtwoord.
   *Deploy → New deployment → Web app* (Execute as: Me · Access: Anyone), toestemming geven, URL naar `MAIL_URL` in `config.js`.
   Na elke wijziging van `mail.gs`: *Manage deployments → bewerk → Version: New version → Deploy*.
   Test: open de `MAIL_URL` in je browser; je moet `{"ok":true,"info":"PV mailer actief"}` zien.
3. Zet de map `docs/` online (GitHub Pages: branch main, map /docs, of je eigen webserver met `docs/` als webroot).
4. Open de hoofdpagina, vul de beheerssleutel in en maak een testlink.

## Problemen oplossen
- **PDF komt niet aan**: de site meldt nu "kon niet bevestigd worden". Controleer: `MAIL_URL` is niet meer `XXXX`,
  de nieuwe versie is gedeployed, en kijk in Apps Script → *Executions* voor foutmeldingen (bv. toestemming of limiet).
- **Handtekening ontbreekt**: het formulier toont een rode waarschuwing als `handtekening.png/.jpg` niet gevonden wordt.
  Bestandsnaam is hoofdlettergevoelig en moet in `docs/sign/` staan.

## Let op
- Het formulier op "/" is openbaar zichtbaar maar onbruikbaar zonder `ADMIN_KEY` (die staat enkel in het script).
  Wil je het toch afschermen, zet er Cloudflare Access voor.
- De klantlink is geheim-door-onraadbaarheid (10 willekeurige tekens) en eenmalig; PV's ouder dan 30 dagen worden gewist.
- Het script beperkt misbruik: mailen kan alleen voor een bestaand PV, max. 4 MB, max. 30 mails/dag.
- Tekens buiten Latijns/WinAnsi worden `?`; lange tekst wordt kleiner gezet (max. 3 regels per veld).
- Een getekende afbeelding is geen gekwalificeerde e-handtekening.

## Testen
```
npm install && pip install playwright pdfplumber pypdfium2 && playwright install chromium
npm test
```
Lokaal bekijken: `cd docs && python3 -m http.server 8000` → http://localhost:8000/
