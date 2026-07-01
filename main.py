########## TERMINAL EINGABE 
# uvicorn main:app --reload

from fastapi import FastAPI, Request, File, UploadFile, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
import pandas as pd
import io
import csv
import base64
import os
import uvicorn
import httpx
import yfinance as yf

from models import CalculationPayload, SparplanPayload
import funktionen_api as funktionen

# from models import CalculationPayload, RechenZiel, SparplanPayload

app = FastAPI(title="ETF Steuer Rechner")

# Mountet den Ordner "static" für CSS, Bilder oder JS-Dateien
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/sitemap.xml", include_in_schema=False)
async def get_sitemap():
    return FileResponse("sitemap.xml", media_type="application/xml")


@app.get("/robots.txt", include_in_schema=False)
async def get_robots():
    return FileResponse("robots.txt", media_type="text/plain")


@app.api_route("/api/health", methods=["GET", "HEAD"])
async def health_check():
    """
    Minimaler Health-Check-Endpunkt für UptimeRobot.
    Reagiert extrem schnell, verbraucht kaum Ressourcen und hält die Render-Instanz aktiv.
    """
    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def read_root(request: Request):
    if request.method == "HEAD":
        return HTMLResponse(content="", status_code=200)
    return templates.TemplateResponse(request, name="index.html")


# @app.route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
# async def read_root(request: Request):
#     if request.method == "HEAD":
#         return HTMLResponse(content="", status_code=200)
#     return templates.TemplateResponse(request, name="index.html")

# @app.route("/api/health", methods=["GET", "HEAD"])
# async def health_check():
#     """
#     Minimaler Health-Check-Endpunkt für UptimeRobot.
#     Reagiert extrem schnell, verbraucht kaum Ressourcen und hält die Render-Instanz aktiv.
#     """
#     return JSONResponse(content={"status": "ok"}, status_code=200)

# @app.get("/", response_class=HTMLResponse)
# async def read_root(request: Request):
#     return templates.TemplateResponse(request, name="index.html")

@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        
        # Das Parsen großer DataFrames lagern wir in den Threadpool aus
        def parse_csv():
            df = pd.read_csv(io.BytesIO(contents), sep=None, engine='python', decimal=".")
            df.columns = [c.lower() for c in df.columns]
            
            mapping = {
                'anzahl': 'anzahl', 'shares': 'anzahl',
                'preis': 'preis', 'price': 'preis',
                'kaufdatum': 'datum', 'date': 'datum', 'datetime': 'datum'
            }
            df = df.rename(columns=mapping)
            relevante_spalten = ['anzahl', 'preis', 'datum']
            df = df[[col for col in relevante_spalten if col in df.columns]].dropna()
            
            if 'datum' in df.columns:
                df['datum'] = pd.to_datetime(df['datum'], errors='coerce').dt.strftime('%Y-%m-%d')
                
            return df.to_dict(orient="records")

        daten_liste = await run_in_threadpool(parse_csv)
        return JSONResponse(content={"success": True, "data": daten_liste})
        
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=400)


# @app.post("/api/calculate")
# async def calculate_steuer(payload: CalculationPayload):
#     try:
#         aktuelle_warnungen = []
#         manuell_aktiv = payload.manuelle_vorabpauschale_aktiv
#         ticker_gesaeubert = str(payload.ticker).strip() if payload.ticker else ""
#         ticker_existiert = ticker_gesaeubert not in ["", "None", "-", "null"]
#         automatische_schätzung_aktiv = ticker_existiert and not manuell_aktiv

#         if automatische_schätzung_aktiv and payload.ticker:
#             startjahr = payload.kaeufe[0].datum.year if payload.kaeufe else None
            
#             # yfinance & Berechnung blockieren; ab in den Threadpool
#             kursdaten = await run_in_threadpool(funktionen.lade_kursdaten, payload.ticker, startjahr)
#             vorabpauschalen = await run_in_threadpool(funktionen.berechne_vorabpauschalen, kursdaten)
#             etf_name = payload.ticker
#         else:
#             if payload.vorabpauschalen:
#                 vorab_liste = [v.model_dump() for v in payload.vorabpauschalen]
#                 vorabpauschalen = pd.DataFrame(vorab_liste)
#             else:
#                 vorabpauschalen = pd.DataFrame(columns=["jahr", "wert"])
                
#             etf_name = "unbekannt" if payload.quelle == "manuell" else (payload.ticker or "unbekannt")

#         # Berechnungs-Logik blockiert CPU; ab in den Threadpool
#         def run_calculation():
#             # 🎯 BEST PRACTICE: Nutzung der Enums statt Strings
#             if payload.rechen_ziel == RechenZiel.STEUERFREI:
#                 return funktionen.berechne_steuerfrei(payload, vorabpauschalen)
#             elif payload.rechen_ziel == RechenZiel.WUNSCHNETTO:
#                 return funktionen.berechne_wunschnetto(payload, vorabpauschalen)
#             else:
#                 return funktionen.berechne_anteile_steuer(payload, vorabpauschalen)

#         calc_res = await run_in_threadpool(run_calculation)
        
#         (anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, gewinn_teilfreistellung, 
#          gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, steuer, netto, 
#          gesamtkosten, aktueller_kurs, freibetrag, verlusttopf_nach_verkauf, gesamte_vorabpauschale, 
#          teilfreistellung_quote, kirchensteuer) = calc_res

#         # 🎯 BEST PRACTICE: Nutzung der Enums statt Strings
#         if payload.rechen_ziel == RechenZiel.STEUERFREI:
#             ergebnis_kpis = {
#                 "wert1": anzahl_verkaufen,
#                 "wert2": netto,
#                 "wert3": freibetrag - (gewinn_nach_verlusttopf - gewinn_steuerpflichtig)
#             }
#         elif payload.rechen_ziel == RechenZiel.WUNSCHNETTO:
#             ergebnis_kpis = {"wert1": anzahl_verkaufen, "wert2": brutto, "wert3": netto}
#             if netto < payload.wert_wunschnetto - 0.01:
#                 aktuelle_warnungen.append(f"Warnung: Das gewünschte Netto von {payload.wert_wunschnetto}€ konnte nicht erreicht werden.")
#         else:
#             ergebnis_kpis = {"wert1": brutto, "wert2": netto, "wert3": steuer}
#             if anzahl_verkaufen < payload.wert_anteile - 0.0001:
#                 aktuelle_warnungen.append(f"Warnung: Sie besitzen nicht {payload.wert_anteile} Anteile.")

#         # PDF Generierung (CPU & IO lastig) -> Threadpool
#         pdf_buffer = await run_in_threadpool(
#             funktionen.create_pdf, anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, 
#             gewinn_teilfreistellung, gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, 
#             steuer, netto, gesamtkosten, vorabpauschalen, aktueller_kurs, freibetrag, etf_name, 
#             verlusttopf_nach_verkauf, gesamte_vorabpauschale, teilfreistellung_quote, kirchensteuer
#         )

#         pdf_bytes = pdf_buffer.getvalue()
#         pdf_buffer.close()
#         pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

#         ergebnis_tabelle = [
#             {"name": "Insgesamt gekaufte Anteile", "wert": max_anteile, "einheit": "Anteile"},
#             {"name": "Bereits verkaufte Anteile", "wert": bereits_verkauft, "einheit": "Anteile"},
#             {"name": "Anteile aktuell im Besitz", "wert": max_anteile - bereits_verkauft, "einheit": "Anteile"},
#             {"name": "Anzahl zu verkaufender Anteile", "wert": anzahl_verkaufen, "einheit": "Anteile"},
#             {"name": "Kurs bei Verkauf", "wert": aktueller_kurs, "einheit": "EUR"},
#             {"name": "Kosten bei Kauf", "wert": brutto - gewinn, "einheit": "EUR"},
#             {"name": "Brutto Verkaufserlös", "wert": brutto, "einheit": "EUR"},
#             {"name": "Gewinn vor Steuer", "wert": gewinn, "einheit": "EUR"},
#             {"name": "Abzuziehende Vorabpauschale", "wert": gesamte_vorabpauschale, "einheit": "EUR"},
#             {"name": "Gewinn nach Vorabpauschale", "wert": gewinn_nach_vorabpauschale, "einheit": "EUR"},
#             {"name": "Gewinn nach Teilfreistellung", "wert": gewinn_teilfreistellung, "einheit": "EUR"},
#             {"name": "Gewinn nach Verlusttopf", "wert": gewinn_nach_verlusttopf, "einheit": "EUR"},
#             {"name": "Neuer Verlusttopf", "wert": verlusttopf_nach_verkauf, "einheit": "EUR"},
#             {"name": "Gewinn nach Sparerpauschbetrag", "wert": gewinn_steuerpflichtig, "einheit": "EUR"},
#             {"name": "Ungenutzter Freibetrag", "wert": freibetrag - (gewinn_nach_verlusttopf - gewinn_steuerpflichtig), "einheit": "EUR"},
#             {"name": "Zu zahlende Steuer", "wert": steuer, "einheit": "EUR"},
#             {"name": "Netto ", "wert": netto, "einheit": "EUR"},
#         ]

#         # 🎯 Das .value sorgt dafür, dass das Frontend (app.js) wie gewohnt den rohen String "wunschnetto" o.ä. erhält!
#         return {
#             "success": True,
#             "kpis": ergebnis_kpis,
#             "tabelle": ergebnis_tabelle,
#             "pdf_data": pdf_base64,
#             "vorabpauschalen_ergebnis": vorabpauschalen.to_dict(orient="records"),
#             "warnings": aktuelle_warnungen
#         }
#     except Exception as e:
#         return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
    
@app.post("/api/calculate")
async def calculate_steuer(payload: CalculationPayload):
    try:
        aktuelle_warnungen = []
        manuell_aktiv = payload.manuelle_vorabpauschale_aktiv
        ticker_gesaeubert = str(payload.ticker).strip() if payload.ticker else ""
        ticker_existiert = ticker_gesaeubert not in ["", "None", "-", "null"]
        automatische_schätzung_aktiv = ticker_existiert and not manuell_aktiv

        if automatische_schätzung_aktiv and payload.ticker:
            startjahr = payload.kaeufe[0].datum.year if payload.kaeufe else None
            
            # yfinance & Berechnung blockieren; ab in den Threadpool
            kursdaten = await run_in_threadpool(funktionen.lade_kursdaten, payload.ticker, startjahr)
            vorabpauschalen = await run_in_threadpool(funktionen.berechne_vorabpauschalen, kursdaten)
            etf_name = payload.ticker
        else:
            if payload.vorabpauschalen:
                vorab_liste = [v.model_dump() for v in payload.vorabpauschalen]
                vorabpauschalen = pd.DataFrame(vorab_liste)
            else:
                vorabpauschalen = pd.DataFrame(columns=["jahr", "wert"])
                
            etf_name = "unbekannt" if payload.quelle == "manuell" else (payload.ticker or "unbekannt")

        # Berechnungs-Logik blockiert CPU; ab in den Threadpool
        def run_calculation():
            if payload.rechen_ziel == "steuerfrei":
                return funktionen.berechne_steuerfrei(payload, vorabpauschalen)
            elif payload.rechen_ziel == "wunschnetto":
                return funktionen.berechne_wunschnetto(payload, vorabpauschalen)
            else:
                return funktionen.berechne_anteile_steuer(payload, vorabpauschalen)

        calc_res = await run_in_threadpool(run_calculation)
        
        (anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, gewinn_teilfreistellung, 
         gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, steuer, netto, 
         gesamtkosten, aktueller_kurs, freibetrag, verlusttopf_nach_verkauf, gesamte_vorabpauschale, 
         teilfreistellung_quote, kirchensteuer) = calc_res

        if payload.rechen_ziel == "steuerfrei":
            ergebnis_kpis = {
                "wert1": anzahl_verkaufen,
                "wert2": netto,
                "wert3": freibetrag - (gewinn_nach_verlusttopf - gewinn_steuerpflichtig)
            }
        elif payload.rechen_ziel == "wunschnetto":
            ergebnis_kpis = {"wert1": anzahl_verkaufen, "wert2": brutto, "wert3": netto}
            if netto < payload.wert_wunschnetto - 0.01:
                aktuelle_warnungen.append(f"Warnung: Das gewünschte Netto von {payload.wert_wunschnetto}€ konnte nicht erreicht werden.")
        else:
            ergebnis_kpis = {"wert1": brutto, "wert2": netto, "wert3": steuer}
            if anzahl_verkaufen < payload.wert_anteile - 0.0001:
                aktuelle_warnungen.append(f"Warnung: Sie besitzen nicht {payload.wert_anteile} Anteile.")

        # PDF Generierung (CPU & IO lastig) -> Threadpool
        pdf_buffer = await run_in_threadpool(
            funktionen.create_pdf, anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, 
            gewinn_teilfreistellung, gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, 
            steuer, netto, gesamtkosten, vorabpauschalen, aktueller_kurs, freibetrag, etf_name, 
            verlusttopf_nach_verkauf, gesamte_vorabpauschale, teilfreistellung_quote, kirchensteuer
        )

        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        ergebnis_tabelle = [
            {"name": "Insgesamt gekaufte Anteile", "wert": max_anteile, "einheit": "Anteile"},
            {"name": "Bereits verkaufte Anteile", "wert": bereits_verkauft, "einheit": "Anteile"},
            {"name": "Anteile aktuell im Besitz", "wert": max_anteile - bereits_verkauft, "einheit": "Anteile"},
            {"name": "Anzahl zu verkaufender Anteile", "wert": anzahl_verkaufen, "einheit": "Anteile"},
            {"name": "Kurs bei Verkauf", "wert": aktueller_kurs, "einheit": "EUR"},
            {"name": "Kosten bei Kauf", "wert": brutto - gewinn, "einheit": "EUR"},
            {"name": "Brutto Verkaufserlös", "wert": brutto, "einheit": "EUR"},
            {"name": "Gewinn vor Steuer", "wert": gewinn, "einheit": "EUR"},
            {"name": "Abzuziehende Vorabpauschale", "wert": gesamte_vorabpauschale, "einheit": "EUR"},
            {"name": "Gewinn nach Vorabpauschale", "wert": gewinn_nach_vorabpauschale, "einheit": "EUR"},
            {"name": "Gewinn nach Teilfreistellung", "wert": gewinn_teilfreistellung, "einheit": "EUR"},
            {"name": "Gewinn nach Verlusttopf", "wert": gewinn_nach_verlusttopf, "einheit": "EUR"},
            {"name": "Neuer Verlusttopf", "wert": verlusttopf_nach_verkauf, "einheit": "EUR"},
            {"name": "Gewinn nach Sparerpauschbetrag", "wert": gewinn_steuerpflichtig, "einheit": "EUR"},
            {"name": "Ungenutzter Freibetrag", "wert": freibetrag - (gewinn_nach_verlusttopf - gewinn_steuerpflichtig), "einheit": "EUR"},
            {"name": "Zu zahlende Steuer", "wert": steuer, "einheit": "EUR"},
            {"name": "Netto ", "wert": netto, "einheit": "EUR"},
        ]

        return {
            "success": True,
            "kpis": ergebnis_kpis,
            "tabelle": ergebnis_tabelle,
            "pdf_data": pdf_base64,
            "vorabpauschalen_ergebnis": vorabpauschalen.to_dict(orient="records"),
            "warnings": aktuelle_warnungen
        }
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@app.get("/api/search")
async def search_etf(q: str = Query(..., min_length=2)):
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    params = {"q": q, "quotesCount": 7, "newsCount": 0}

    try:
        # Asynchroner HTTP-Aufruf via httpx statt requests
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, params=params, timeout=5.0)
            r.raise_for_status()
            data = r.json()
        
        results = []
        for q_item in data.get("quotes", []):
            if q_item.get("quoteType") in ["ETF", "EQUITY"]:
                name = q_item.get('shortname') or q_item.get('longname') or q_item.get('symbol')
                symbol = q_item.get('symbol')
                results.append({"name": name, "symbol": symbol})
                
        return results
    except Exception as e:
        return JSONResponse(content={"error": f"Suche fehlgeschlagen: {str(e)}"}, status_code=500)
    

@app.get("/api/get-price")
async def get_etf_price(symbol: str):
    try:
        def fetch_price():
            ticker_obj = yf.Ticker(symbol)
            preis = ticker_obj.fast_info.get("lastPrice")
            if preis is None:
                preis = ticker_obj.history(period="1d")["Close"].iloc[-1]
            return round(preis, 2)

        preis = await run_in_threadpool(fetch_price)
        return {"success": True, "price": preis}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
    

@app.post("/api/generate-sparplan")
async def generate_sparplan(payload: SparplanPayload):
    try:
        def fetch_history():
            ticker = yf.Ticker(payload.symbol)
            return ticker.history(start=payload.start_date, end=payload.end_date, interval="1d")

        df = await run_in_threadpool(fetch_history)
        
        if df.empty:
            return {"success": False, "error": "Keine historischen Kurse gefunden."}
            
        df['jahr'] = df.index.year
        df['monat'] = df.index.month
        df['tag'] = df.index.day
        
        generierte_kaeufe = []
        grouped = df.groupby(['jahr', 'monat'])
        
        for (jahr, monat), group in grouped:
            ziel_tag = payload.tag
            verfuegbare_tage = group['tag'].tolist()
            gueltiger_tag = min(verfuegbare_tage, key=lambda x: abs(x - ziel_tag))
            row = group[group['tag'] == gueltiger_tag].iloc[0]
            tatsaechliches_datum = row.name.date()
            
            if tatsaechliches_datum.year == payload.start_date.year and tatsaechliches_datum.month == payload.start_date.month:
                if gueltiger_tag > ziel_tag + 4:
                    continue
            
            if tatsaechliches_datum < payload.start_date:
                continue
                
            generierte_kaeufe.append({
                "datum": tatsaechliches_datum.strftime('%Y-%m-%d'),
                "anzahl": round(payload.rate / round(row['Close'], 2), 5),
                "preis": round(row['Close'], 2)
            })
            
        return {"success": True, "data": generierte_kaeufe}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
    

@app.post("/api/upload-trade-republic")
async def upload_trade_republic(file: UploadFile = File(...)):
    try:
        content = await file.read()
        
        def parse_tr_csv():
            decoded_content = content.decode("utf-8")
            csv_file = io.StringIO(decoded_content)
            sample = decoded_content[:2048]
            delimiter = ";" if ";" in sample else ","
            reader = csv.DictReader(csv_file, delimiter=delimiter)
            headers = reader.fieldnames
            
            if not headers:
                raise ValueError("Die CSV-Datei ist leer.")
                
            def find_column(options: list, available_headers: list):
                for opt in options:
                    for header in available_headers:
                        if opt.lower() == header.strip().lower():
                            return header
                return None

            col_type = find_column(["type", "typ", "transaktionsart"], headers)
            col_isin = find_column(["symbol", "isin", "isin-nummer", "wertpapiernummer"], headers)
            col_name = find_column(["name", "wertpapier", "asset", "bezeichnung"], headers)
            col_datum = find_column(["date", "datum", "zeitstempel"], headers)
            col_anzahl = find_column(["shares", "anzahl", "menge", "styk", "stücke"], headers)
            col_preis = find_column(["price", "preis", "kurs", "wert"], headers)

            if not col_type or not col_isin or not col_name:
                raise ValueError("Bitte fügen Sie hier nur originale Trade Republic CSV-Dateien hinzu.")

            gefilterte_daten = []
            isin_name_mapping = {}
            kurse = {}
            verkaufte_anteile_pro_etf = {}
            ticker_mapping = {}

            for row in reader:
                isin = row[col_isin].strip() if row[col_isin] else None
                name = row[col_name].strip() if row[col_name] else None
                order_type = row[col_type].strip().upper() if row[col_type] else ""
                
                if not isin or not name:
                    continue
                    
                isin_name_mapping[isin] = name
                    
                try:
                    anzahl = float(row[col_anzahl].replace(",", ".")) if row[col_anzahl] else 0.0
                    preis = float(row[col_preis].replace(",", ".")) if row[col_preis] else 0.0
                    datum = row[col_datum].strip() if row[col_datum] else ""
                except (ValueError, TypeError):
                    continue

                if order_type == "BUY":
                    gefilterte_daten.append({"asset": isin, "datum": datum, "anzahl": anzahl, "preis": preis})
                    kurse[isin] = str(preis)
                elif order_type == "SELL":
                    if isin not in verkaufte_anteile_pro_etf:
                        verkaufte_anteile_pro_etf[isin] = 0.0
                    verkaufte_anteile_pro_etf[isin] += abs(anzahl)

            for isin in isin_name_mapping.keys():
                try:
                    suche = yf.Search(isin, max_results=1)
                    ticker_mapping[isin] = suche.quotes[0]['symbol'] if suche.quotes else isin
                except Exception:
                    ticker_mapping[isin] = isin

            return gefilterte_daten, kurse, verkaufte_anteile_pro_etf, ticker_mapping, isin_name_mapping

        res = await run_in_threadpool(parse_tr_csv)
        gefilterte_daten, kurse, verkaufte_anteile_pro_etf, ticker_mapping, isin_name_mapping = res

        return {
            "success": True,
            "data": gefilterte_daten,
            "kurse": kurse,
            "verkaufte_anteile": verkaufte_anteile_pro_etf,
            "ticker_mapping": ticker_mapping,
            "isin_name_mapping": isin_name_mapping
        }
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=400)
    

@app.get("/api/download-pdf")
async def download_pdf(ticker: str, ziel: str, netto: float):
    try:
        # Aufruf der synchronen PDF-Funktion über den Threadpool ausgelagert
        pdf_buffer = await run_in_threadpool(funktionen.deine_pdf_funktion, ticker, ziel, netto) 
        
        return StreamingResponse(
            pdf_buffer, 
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="Steuerreport_{ticker}.pdf"'}
        )
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
    

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)