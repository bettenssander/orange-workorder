// Gedeelde helpers + PDF-invuller. Coördinaten in pt, vanaf linksboven (top).
const FILL_BASE = document.currentScript.src;
const POLLS = window.POLLS || 8, POLL_MS = window.POLL_MS || 1000;
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function lookup(id) { // PV ophalen (null = netwerkfout; {error:'not_found'} = bestaat niet/al gebruikt)
  try { return await (await fetch(MAIL_URL + '?id=' + encodeURIComponent(id), {cache: 'no-store'})).json(); } catch (e) { return null; }
}
async function fetchBytes(name) {
  try { const r = await fetch(new URL(name, FILL_BASE), {cache: 'no-store'}); return r.ok ? new Uint8Array(await r.arrayBuffer()) : null; } catch (e) { return null; }
}
async function findSignature() { // handtekening.png / .jpg; controleert of het echt een afbeelding is
  for (const n of ['handtekening.png', 'handtekening.PNG', 'handtekening.jpg', 'handtekening.jpeg']) {
    const b = await fetchBytes(n);
    if (b && ((b[0] === 0x89 && b[1] === 0x50) || (b[0] === 0xFF && b[1] === 0xD8))) return b;
  } return null;
}
// Vult het originele Orange-PDF in (template.pdf) met pdf-lib.
async function buildPdf(D, opm, naam, sigClient, sigEng, engineer, tpl) {
  const {PDFDocument, StandardFonts, rgb} = globalThis.PDFLib;
  const doc = await PDFDocument.load(tpl), pg = doc.getPage(0), H = pg.getHeight();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const fmt = s => s ? s.split('-').reverse().join('/') : '';
  const ok = new Set(font.getCharacterSet()), clean = t => [...(t || '')].map(c => ok.has(c.codePointAt(0)) ? c : '?').join('');
  const txt = (t, x, top, size = 10) => pg.drawText(clean(t), {x, y: H - top, size, font, color: rgb(0, 0, 0.55)});
  const wrapW = (t, ws, size) => { // greedy wrap met een breedte per regel; null bij overflow
    const out = []; let cur = '';
    for (const par of (t || '').split('\n')) {
      for (const word of clean(par).split(' ')) {
        const w = ws[Math.min(out.length, ws.length - 1)], n = cur ? cur + ' ' + word : word;
        if (font.widthOfTextAtSize(n, size) > w && cur) { out.push(cur); cur = word; } else cur = n;
      } out.push(cur); cur = ''; }
    return out.length <= ws.length ? out : null; };
  const wrap = (t, w, size) => wrapW(t, [w, w, w, w, w, w], size) || [];
  // 3 rijen: 1e naast het label (x=252), 2e en 3e op de lijnen eronder
  const block = (t, top) => {
    const rows = [{x: 262, w: 300, y: top - 2}, {x: 45, w: 515, y: top + 15}, {x: 45, w: 515, y: top + 32}];
    for (const sz of [10, 9, 8, 7, 6]) { const l = wrapW(t, rows.map(r => r.w), sz);
      if (l) { l.forEach((x, i) => txt(x, rows[i].x, rows[i].y, sz)); return; } } };
  const img = async (png, x0, top0, x1, top1) => {
    if (!png) return; const im = (png[0] === 0xFF && png[1] === 0xD8) ? await doc.embedJpg(png) : await doc.embedPng(png);
    const k = Math.min((x1 - x0 - 4) / im.width, (top1 - top0 - 4) / im.height);
    pg.drawImage(im, {x: x0 + 2, y: H - top1 + 2, width: im.width * k, height: im.height * k}); };
  txt(D.id, 345, 155);
  txt(D.onderneming, 272, 180); txt(D.uitrusting, 272, 206);
  wrap(D.adres, 285, 10).slice(0, 2).forEach((l, i) => txt(l, 272, 226 + i * 10, 9));
  txt(fmt(D.datumIS), 378, 319);
  block(D.voorwerp, 363);
  block(opm, 431);
  block(D.opmOrange, 499);
  txt(D.plaats, 242, 579); txt(fmt(D.datum), 434, 578);
  txt(naam, 314, 634); await img(sigClient, 309, 640, 565, 674);
  txt(engineer, 314, 714); await img(sigEng, 309, 720, 565, 750);
  return doc.save();
}
