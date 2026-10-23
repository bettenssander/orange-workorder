"""End-to-end test met een nagebootst Apps Script (zelfde API als mail.gs).
Gebruik:  npm install && pip install playwright pdfplumber pypdfium2 && playwright install chromium
          python tests/e2e.py        (PDFLIB_JS=pad/naar/pdf-lib.min.js om een ander pdf-lib te gebruiken)
"""
import base64, functools, http.server, io, json, os, shutil, tempfile, threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import pdfplumber
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PDFLIB = Path(os.environ.get("PDFLIB_JS", ROOT / "node_modules/pdf-lib/dist/pdf-lib.min.js"))
SIG = Path(__file__).parent / "fixtures/handtekening.png"
KEY = "geheim"

def serve(directory):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    h.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

def draw(page):
    page.locator("#cv").scroll_into_view_if_needed()
    box = page.locator("#cv").bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 100); page.mouse.down()
    for i in range(30): page.mouse.move(box["x"] + 20 + i * 8, box["y"] + 60 + (i % 5) * 15)
    page.mouse.up()

def main():
    tmp = Path(tempfile.mkdtemp()); site = tmp / "docs"
    shutil.copytree(ROOT / "docs", site)
    (site / "sign/config.js").write_text("const ENGINEER = 'Test Engineer'; const MAIL_URL = 'https://script.example/exec';")
    shutil.copy(SIG, site / "sign/handtekening.png")
    srv = serve(site); base = f"http://127.0.0.1:{srv.server_address[1]}"
    store, sent, mode = {}, [], {"mail": "ok"}
    results = []
    def check(name, cond):
        results.append(cond); print(("PASS " if cond else "FAIL ") + name)

    def api(route):  # nagebootst mail.gs
        req = route.request; hdr = {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
        def ans(o): route.fulfill(status=200, headers=hdr, body=json.dumps(o))
        if req.method == "GET":
            i = parse_qs(urlparse(req.url).query).get("id", [None])[0]
            return ans({"data": store[i]} if i in store else ({"error": "not_found"} if i else {"ok": True}))
        d = json.loads(req.post_data)
        if d.get("action") == "save":
            if d.get("key") != KEY: return ans({"error": "bad_key"})
            store[d["id"]] = d["data"]; return ans({"ok": True})
        if d["id"] not in store: return ans({"error": "not_found"})
        if mode["mail"] == "fail": return ans({"error": "mail"})
        sent.append(d); del store[d["id"]]; ans({"ok": True})

    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(accept_downloads=True)
        ctx.route("**/pdf-lib.min.js", lambda r: r.fulfill(path=str(PDFLIB), content_type="text/javascript"))
        ctx.route("https://script.example/**", api)
        ctx.add_init_script("window.POLLS = 3; window.POLL_MS = 200;")
        errors = []
        def newpage():
            pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); return pg

        # 1. admin op de hoofdpagina "/"
        page = newpage(); page.goto(base + "/")
        check("admin: formulier op hoofdpagina '/'", page.locator("#sleutel").count() == 1)
        check("admin: geen handtekening-waarschuwing (png aanwezig)", page.locator("#warn").is_hidden())
        vals = {"id": "INC0012345", "onderneming": "Café Müller & Zn BV", "uitrusting": "Cloud Telephony (20 toestellen)",
                "adres": "Grote Markt 1\n3300 Tienen", "datumIS": "2026-10-22",
                "voorwerp": "Installatie en configuratie – ünïcode €uro test 日本", "opmOrange": "Geen bijzonderheden",
                "plaats": "Tienen", "datum": "2026-10-22"}
        for k, v in vals.items(): page.fill(f"[name={k}]", v)
        page.fill("#sleutel", "fout"); page.click("#btn")
        page.wait_for_function("document.querySelector('#out').textContent.includes('sleutel')")
        check("admin: verkeerde beheerssleutel wordt geweigerd", not store)
        page.fill("#sleutel", KEY); page.click("#btn")
        page.wait_for_selector("#out a"); link = page.locator("#out a").get_attribute("href")
        check(f"admin: korte link ({len(link) - len(base)} tekens na domein)", len(link) - len(base) < 25)
        check("admin: record bewaard onder die id", link.split("#")[1] in store)
        # /admin/ stuurt door naar /
        a = newpage(); a.goto(base + "/admin/"); a.wait_for_url(base + "/")
        check("admin: /admin/ stuurt door naar /", True)

        # 2. klant
        cust = newpage(); cust.goto(link); cust.wait_for_selector("#main:not([hidden])")
        check("sign: gegevens zichtbaar", "Café Müller" in cust.inner_text("#d") and "INC0012345" in cust.inner_text("#d"))
        cust.fill("#naam", "Jan Klant"); cust.click("#ok")
        check("sign: weigert zonder handtekening", "teken" in cust.inner_text("#msg").lower() and not sent)
        cust.fill("#opm", "Alles in orde, bedankt!"); draw(cust)
        with cust.expect_download() as dl: cust.click("#ok")
        pdf_path = tmp / "out.pdf"; dl.value.save_as(pdf_path)
        cust.wait_for_function("document.querySelector('#msg').textContent.includes('verstuurd')", timeout=10000)
        check("sign: bevestigd 'verstuurd' (script wiste het PV)", "gedownload en verstuurd" in cust.inner_text("#msg"))
        with pdfplumber.open(pdf_path) as pdf:
            t = pdf.pages[0].extract_text()
            for n in ["INC0012345", "Test Engineer", "Jan Klant", "Alles in orde", "22/10/2026", "Tienen", "Proces-verbaal"]:
                check(f"pdf: bevat '{n}'", n in t)
            check("pdf: handtekening engineer + klant aanwezig (2 afbeeldingen)", len(pdf.pages[0].images) == 2)
        check("mail: 1 mail met PDF identiek aan download", len(sent) == 1 and base64.b64decode(sent[0]["pdf"]) == pdf_path.read_bytes())
        pdfium_png = tmp / "run.png"
        import pypdfium2 as pdfium
        pdfium.PdfDocument(str(pdf_path))[0].render(scale=1.5).to_pil().save(ROOT / "tests/last_run.png")

        # 3. link is eenmalig
        again = newpage(); again.goto(link)
        again.wait_for_function("document.querySelector('#st').textContent.includes('ongeldig')")
        check("sign: tweede keer openen -> 'al ondertekend'", again.locator("#main").is_hidden())

        # 4. mail mislukt -> geen valse bevestiging, PDF wel gedownload
        mode["mail"] = "fail"; store["failfail1"] = vals
        c2 = newpage(); c2.goto(base + "/sign/#failfail1"); c2.wait_for_selector("#main:not([hidden])")
        c2.fill("#naam", "X"); draw(c2)
        with c2.expect_download(): c2.click("#ok")
        c2.wait_for_function("document.querySelector('#msg').textContent.includes('niet bevestigd')", timeout=10000)
        check("sign: bij mislukte mail GEEN 'verstuurd' + knop weer actief", c2.locator("#ok").is_enabled())
        mode["mail"] = "ok"

        # 5. ongeldige link / geen id
        for h in ("#bestaatniet", ""):
            c3 = newpage(); c3.goto(base + "/sign/" + h)
            c3.wait_for_function("document.querySelector('#st').textContent.includes('ongeldig')")
        check("sign: ongeldige of lege link netjes afgehandeld", True)

        # 6. handtekening als JPG + ontbrekende handtekening
        (site / "sign/handtekening.png").unlink()
        Image.open(SIG).convert("RGBA").resize((300, 90)).convert("RGB").save(site / "sign/handtekening.jpg")
        store["jpgjpgjp1"] = vals
        c4 = newpage(); c4.goto(base + "/sign/#jpgjpgjp1"); c4.wait_for_selector("#main:not([hidden])")
        c4.fill("#naam", "Y"); draw(c4)
        with c4.expect_download() as d4: c4.click("#ok")
        d4.value.save_as(tmp / "jpg.pdf")
        with pdfplumber.open(tmp / "jpg.pdf") as pdf: check("pdf: handtekening als .jpg werkt (2 afbeeldingen)", len(pdf.pages[0].images) == 2)
        (site / "sign/handtekening.jpg").unlink()
        w = newpage(); w.goto(base + "/"); w.wait_for_function("!document.querySelector('#warn').hidden")
        check("admin: waarschuwing als handtekening ontbreekt", True)

        # 7. zeer lange tekst
        store["longlong1"] = dict(vals, voorwerp="woord " * 200)
        c5 = newpage(); c5.goto(base + "/sign/#longlong1"); c5.wait_for_selector("#main:not([hidden])")
        c5.fill("#naam", "Z"); draw(c5)
        with c5.expect_download() as d5: c5.click("#ok")
        d5.value.save_as(tmp / "long.pdf")
        with pdfplumber.open(tmp / "long.pdf") as pdf: check("pdf: zeer lange tekst blijft op 1 pagina", len(pdf.pages) == 1)
        check("geen JS-fouten in de pagina's", not errors)
        if errors: print(errors)
        b.close()
    srv.shutdown(); shutil.rmtree(tmp)
    print(f"\n{sum(results)}/{len(results)} geslaagd"); raise SystemExit(0 if all(results) else 1)

if __name__ == "__main__": main()
