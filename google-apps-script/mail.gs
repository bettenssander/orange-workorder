// Plak in script.google.com > Deploy > Web app (Execute as: Me, Access: Anyone).
// Script properties (Project Settings): ADMIN_KEY = zelfgekozen wachtwoord voor het aanmaakformulier.
// Het script bewaart elk PV onder een korte id (link = /sign/#id), mailt de ondertekende PDF naar TO
// en wist het PV daarna (link is dus eenmalig). Records ouder dan 30 dagen worden opgeruimd.
const TO = 'sander.bettens@orange.com'; // <-- pas aan: hierheen gaat elk getekend PV
const MAX_PER_DAY = 30, KEEP_DAYS = 30;
const P = () => PropertiesService.getScriptProperties();
const out = o => ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);

function doGet(e) {                       // ?id=...  -> PV-gegevens ophalen (of: werkt het script?)
  const id = e.parameter.id;
  if (!id) return out({ok: true, info: 'PV mailer actief'});
  const raw = P().getProperty('pv_' + id);
  return out(raw ? {data: JSON.parse(raw).data} : {error: 'not_found'});
}

function doPost(e) {
  const d = JSON.parse(e.postData.contents), p = P();
  if (!/^[a-z0-9]{8,16}$/.test(d.id || '')) return out({error: 'bad_id'});
  if (d.action === 'save') {              // aangemaakt door de engineer (vereist ADMIN_KEY)
    const key = p.getProperty('ADMIN_KEY');
    if (!key || d.key !== key) return out({error: 'bad_key'});
    const rec = JSON.stringify({data: d.data, t: Date.now()});
    if (rec.length > 8000) return out({error: 'too_long'});
    cleanup(p); p.setProperty('pv_' + d.id, rec);
    return out({ok: true});
  }
  // ondertekend door de klant: alleen toegestaan voor een bestaande, nog niet gebruikte link
  if (!p.getProperty('pv_' + d.id)) return out({error: 'not_found'});
  const dag = Utilities.formatDate(new Date(), 'Europe/Brussels', 'yyyy-MM-dd');
  const n = p.getProperty('dag') === dag ? Number(p.getProperty('n')) : 0;
  if (!d.pdf || d.pdf.length > 4000000 || n >= MAX_PER_DAY) return out({error: 'limit'});
  const blob = Utilities.newBlob(Utilities.base64Decode(d.pdf), 'application/pdf', String(d.filename).slice(0, 100));
  MailApp.sendEmail({to: TO, subject: 'Getekend PV - ' + String(d.klant).slice(0, 100), body: 'Zie bijlage.', attachments: [blob]});
  p.setProperties({dag: dag, n: String(n + 1)});
  p.deleteProperty('pv_' + d.id);
  return out({ok: true});
}

function cleanup(p) {
  const all = p.getProperties(), cut = Date.now() - KEEP_DAYS * 864e5;
  for (const k in all) if (k.indexOf('pv_') === 0) {
    try { if (JSON.parse(all[k]).t < cut) p.deleteProperty(k); } catch (e) { p.deleteProperty(k); }
  }
}
