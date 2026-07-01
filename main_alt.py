from fastapi import FastAPI, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import io
from models import CalculationPayload
import funktionen_api as funktionen  # Deine bereits existierende Datei
import requests
from fastapi import Query
import yfinance as yf
from fastapi import HTTPException
import csv
# from fastapi import app, UploadFile, File
import re  # Oben bei den Importen hinzufügen, falls noch nicht da
from fastapi.responses import StreamingResponse
import base64
from models import SparplanPayload
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
from fastapi.responses import FileResponse

########## TERMINAL EINGABE 
# uvicorn main:app --reload

app = FastAPI(title="ETF Steuer Rechner")
# Mountet den Ordner "static" für CSS, Bilder oder JS-Dateien
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/sitemap.xml", include_in_schema=False)
def get_sitemap():
    return FileResponse("sitemap.xml", media_type="application/xml")

@app.get("/robots.txt", include_in_schema=False)
def get_robots():
    return FileResponse("robots.txt", media_type="text/plain")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request, name="index.html")

# NEU: Endpunkt für den CSV-Upload
@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    try:
        # Datei in den Speicher lesen
        contents = await file.read()
        
        # Mit Pandas einlesen (wie in deinem Streamlit-Code)
        # df = pd.read_csv(io.BytesIO(contents), decimal=".")
        df = pd.read_csv(io.BytesIO(contents), sep=None, engine='python', decimal=".")
        
        # Spaltennamen normalisieren (Groß-/Kleinschreibung ignorieren für Flexibilität)
        df.columns = [c.lower() for c in df.columns]
        
        # Mappe deutsche oder englische Spaltennamen auf unseren Standard
        mapping = {
            'anzahl': 'anzahl', 'shares': 'anzahl',
            'preis': 'preis', 'price': 'preis',
            'kaufdatum': 'datum', 'date': 'datum', 'datetime': 'datum'
        }
        df = df.rename(columns=mapping)
        
        # Nur die relevanten Spalten behalten und NaNs entfernen
        relevante_spalten = ['anzahl', 'preis', 'datum']
        df = df[[col for col in relevante_spalten if col in df.columns]].dropna()
        
        # Datum in Text-Format konvertieren, damit JSON es versteht
        if 'datum' in df.columns:
            df['datum'] = pd.to_datetime(df['datum'], errors='coerce').dt.strftime('%Y-%m-%d')
            
        # Daten als Liste von Dictionaries an das Frontend senden
        daten_liste = df.to_dict(orient="records")
        return JSONResponse(content={"success": True, "data": daten_liste})
        
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=400)
    

@app.post("/api/calculate")
async def calculate_steuer(payload: CalculationPayload):
    aktuelle_warnungen = []

    # 1. Zustand des manuellen Häkchens direkt aus Pydantic lesen
    manuell_aktiv = payload.manuelle_vorabpauschale_aktiv

    ticker_gesaeubert = str(payload.ticker).strip() if payload.ticker else ""
    ticker_existiert = ticker_gesaeubert not in ["", "None", "-", "null"]

    # 3. Automatische Schätzung nur, wenn ein ECHTER Ticker da ist und der Haken aus ist
    automatische_schätzung_aktiv = ticker_existiert and not manuell_aktiv

    if automatische_schätzung_aktiv and payload.ticker:
        # Bestimme Startjahr für die historische Abfrage
        startjahr = payload.kaeufe[0].datum.year if payload.kaeufe else None

        # Vorabpauschale automatisch über Kurshistorie schätzen
        kursdaten = funktionen.lade_kursdaten(payload.ticker, startjahr)
        vorabpauschalen = funktionen.berechne_vorabpauschalen(kursdaten)

        etf_name = payload.ticker
    else:
        # FALLBACK: Der Haken ist an ODER wir sind in der rein manuellen Zeilen-Eingabe.
        # Wir nutzen ausschließlich die vom User übermittelten Tabellenwerte.
        if payload.vorabpauschalen:
            vorab_liste = [v.model_dump() for v in payload.vorabpauschalen]
            vorabpauschalen = pd.DataFrame(vorab_liste)
        else:
            # Falls die Tabelle leer übergeben wurde, ein leeres DataFrame bereitstellen,
            # damit nachfolgende mathematische Berechnungen nicht mit einem AttributeError abstürzen.
            vorabpauschalen = pd.DataFrame(columns=["jahr", "wert"])
            
        etf_name = "unbekannt" if payload.quelle == "manuell" else (payload.ticker or "unbekannt")
        

    if payload.rechen_ziel == "steuerfrei":
        # ergebnis = {"nachricht": "Hier wird die Funktion für steuerfreie Anteile aufgerufen"}
        anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, gewinn_teilfreistellung, gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, steuer, netto, gesamtkosten, aktueller_kurs, freibetrag, verlusttopf_nach_verkauf, gesamte_vorabpauschale, teilfreistellung_quote, kirchensteuer = funktionen.berechne_steuerfrei(payload, vorabpauschalen)
        ergebnis_kpis = {
            "wert1": anzahl_verkaufen,  # Als Float oder Integer (kein String!)
            "wert2": netto,
            "wert3": freibetrag - (gewinn_nach_verlusttopf - gewinn_steuerpflichtig)
        }
    elif payload.rechen_ziel == "wunschnetto":
        # ergebnis = {"nachricht": f"Hier wird Wunschnetto für {payload.wert_wunschnetto}€ berechnet"}
        anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, gewinn_teilfreistellung, gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, steuer, netto, gesamtkosten, aktueller_kurs, freibetrag, verlusttopf_nach_verkauf, gesamte_vorabpauschale, teilfreistellung_quote, kirchensteuer= funktionen.berechne_wunschnetto(payload, vorabpauschalen)
        ergebnis_kpis = {
            "wert1": anzahl_verkaufen,  # Als Float oder Integer (kein String!)
            "wert2": brutto,
            "wert3": netto
        }
        if netto < payload.wert_wunschnetto - 0.01:  # Berücksichtigung von Rundungsfehlern
            aktuelle_warnungen.append(f"Warnung: Das gewünschte Netto von {payload.wert_wunschnetto}€ konnte nicht erreicht werden. Es wird mit dem Verkauf aller verfügbaren Anteile gerechnet.")

    else:
        # ergebnis = {"nachricht": f"Hier werden Steuern für {payload.wert_anteile} Anteile berechnet"}
        anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, gewinn_teilfreistellung, gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, steuer, netto, gesamtkosten, aktueller_kurs, freibetrag, verlusttopf_nach_verkauf, gesamte_vorabpauschale, teilfreistellung_quote, kirchensteuer = funktionen.berechne_anteile_steuer(payload, vorabpauschalen)  # Passe den Funktionsaufruf an
        ergebnis_kpis = {
            "wert1": brutto,  # Als Float oder Integer (kein String!)
            "wert2": netto,
            "wert3": steuer
        }
        if anzahl_verkaufen < payload.wert_anteile - 0.0001:  # Berücksichtigung von Rundungsfehlern
            aktuelle_warnungen.append(f"Warnung: Sie besitzen nicht {payload.wert_anteile} Anteile. Es wird mit dem Verkauf aller verfügbaren Anteile gerechnet.")

        # hier vielleicht lieber iregndeine form gewinn aufführen


    pdf_buffer = funktionen.create_pdf(anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, gewinn_teilfreistellung, gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, steuer, netto, gesamtkosten, vorabpauschalen, aktueller_kurs, freibetrag,  etf_name, verlusttopf_nach_verkauf, gesamte_vorabpauschale,  teilfreistellung_quote, kirchensteuer)

    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()  # Buffer sauber schließen

    # 3. 🎯 DIE WICHTIGE ZEILE: Erst b64encode, DANN als utf-8 Text decodieren!
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    ergebnis_tabelle = [
        {"name": "Insgesamt gekaufte Anteile", "wert": max_anteile, "einheit": "Anteile"},
        {"name": "Bereits verkaufte Anteile", "wert": bereits_verkauft, "einheit": "Anteile"},
        {"name": "Anteile aktuell im Besitz", "wert": max_anteile - bereits_verkauft, "einheit": "Anteile"},
        {"name": "Anzahl zu verkaufender Anteile", "wert": anzahl_verkaufen, "einheit": "Anteile"},
        {"name": "Kurs bei Verkauf", "wert": aktueller_kurs, "einheit": "EUR"},
        {"name": "Kosten bei Kauf", "wert": brutto-gewinn, "einheit": "EUR"},
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
                "pdf_data": pdf_base64,  # 📦 Die PDF reist als Text getarnt mit!
                "vorabpauschalen_ergebnis":vorabpauschalen.to_dict(orient="records"),  # Optional: Vorabpauschalen-Ergebnis zurückgeben
                "warnings": aktuelle_warnungen
            }


@app.get("/api/search")
async def search_etf(q: str = Query(..., min_length=2)):
    """
    Sucht nach ETFs via Yahoo Finance API (migriert aus deinem Streamlit-Code)
    """
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    params = {
        "q": q,
        "quotesCount": 7,  # Kompakt halten für die Live-Liste
        "newsCount": 0
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=5)
        data = r.json()
        
        results = []
        for q_item in data.get("quotes", []):
            # Nur ETFs und Aktien zulassen
            if q_item.get("quoteType") in ["ETF", "EQUITY"]:
                name = q_item.get('shortname') or q_item.get('longname') or q_item.get('symbol')
                symbol = q_item.get('symbol')
                results.append({"name": name, "symbol": symbol})
                
        return results
    except Exception as e:
        return {"error": f"Suche fehlgeschlagen: {str(e)}"}
    

@app.get("/api/get-price")
async def get_etf_price(symbol: str):
    """
    Hält den aktuellen Marktpreis für ein Ticker-Symbol bereit
    """
    try:
        ticker_obj = yf.Ticker(symbol)
        # fast_info ist extrem schnell und blockiert den Server nicht lange
        preis = ticker_obj.fast_info.get("lastPrice")
        
        if preis is None:
            # Fallback falls fast_info fehlschlägt
            preis = ticker_obj.history(period="1d")["Close"].iloc[-1]
            
        return {"success": True, "price": round(preis, 2)}
    except Exception as e:
        return {"success": False, "error": str(e)}
    
@app.post("/api/generate-sparplan")
async def generate_sparplan(payload: SparplanPayload):
    try:
        ticker = yf.Ticker(payload.symbol)
        df = ticker.history(start=payload.start_date, end=payload.end_date, interval="1d")
        
        if df.empty:
            return {"success": False, "error": "Keine historischen Kurse für diesen Zeitraum gefunden."}
            
        df['jahr'] = df.index.year
        df['monat'] = df.index.month
        df['tag'] = df.index.day
        
        generierte_kaeufe = []
        
        grouped = df.groupby(['jahr', 'monat'])
        for (jahr, monat), group in grouped:
            ziel_tag = payload.tag
            verfuegbare_tage = group['tag'].tolist()
            
            # Findet den Tag mit dem geringsten Abstand zum Wunschtag
            gueltiger_tag = min(verfuegbare_tage, key=lambda x: abs(x - ziel_tag))
            
            row = group[group['tag'] == gueltiger_tag].iloc[0]
            tatsaechliches_datum = row.name.date()
            
            # --- DIESE PRÜFUNG ERSETZT DIE ALTEN VERSUCHE ---
            # Wenn wir im Startmonat sind, darf der gefundene Tag nicht WEIT nach dem Wunschtag liegen.
            # Beispiel: Wunschtag = 1, Startdatum = 25.06., gefundener Tag = 25. -> 25 > 1 -> Überspringen!
            if tatsaechliches_datum.year == payload.start_date.year and tatsaechliches_datum.month == payload.start_date.month:
                if gueltiger_tag > ziel_tag + 4: # +4 puffert Wochenenden/Feiertage ab, falls der 1. ein Samstag war
                    continue
            
            # Sicherheitsnetz für kalendarisch davor liegende Tage
            if tatsaechliches_datum < payload.start_date:
                continue
            # ------------------------------------------------
                
            kauf_datum = tatsaechliches_datum.strftime('%Y-%m-%d')
            kauf_preis = round(row['Close'], 2)
            
            anzahl_anteile = round(payload.rate / kauf_preis, 5)
            
            generierte_kaeufe.append({
                "datum": kauf_datum,
                "anzahl": anzahl_anteile,
                "preis": kauf_preis
            })
            
        return {"success": True, "data": generierte_kaeufe}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    


@app.post("/api/upload-trade-republic")
async def upload_trade_republic(file: UploadFile = File(...)):
    try:
        content = await file.read()
        decoded_content = content.decode("utf-8")
        csv_file = io.StringIO(decoded_content)
        
        sample = decoded_content[:2048]
        delimiter = ";" if ";" in sample else ","
        reader = csv.DictReader(csv_file, delimiter=delimiter)
        headers = reader.fieldnames
        
        if not headers:
            return {"success": False, "error": "Die CSV-Datei ist leer."}
            
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
            return {"success": False, "error": f"Bitte fügen Sie hier nur originale Trade Republic CSV-Dateien hinzu."}

        gefilterte_daten = []
        isin_name_mapping = {} # Merkt sich, welcher Name zu welcher ISIN gehört {"IE00B4L5Y983": "Core S&P 500 USD (Acc)"}
        kurse = {}
        verkaufte_anteile_pro_etf = {}
        ticker_mapping = {}  # Übersetzt ISIN -> Ticker {"IE00B4L5Y983": "SXR8.DE"}

        for row in reader:
            isin = row[col_isin].strip() if row[col_isin] else None
            name = row[col_name].strip() if row[col_name] else None
            order_type = row[col_type].strip().upper() if row[col_type] else ""
            
            if not isin or not name:
                continue
                
            # Name zur ISIN merken
            isin_name_mapping[isin] = name
                
            try:
                anzahl = float(row[col_anzahl].replace(",", ".")) if row[col_anzahl] else 0.0
                preis = float(row[col_preis].replace(",", ".")) if row[col_preis] else 0.0
                datum = row[col_datum].strip() if row[col_datum] else ""
            except (ValueError, TypeError):
                continue

            if order_type == "BUY":
                gefilterte_daten.append({
                    "asset": isin,  # WICHTIG: Wir filtern im Frontend jetzt auf Basis der ISIN!
                    "datum": datum,
                    "anzahl": anzahl,
                    "preis": preis
                })
                kurse[isin] = str(preis)

            elif order_type == "SELL":
                if isin not in verkaufte_anteile_pro_etf:
                    verkaufte_anteile_pro_etf[isin] = 0.0
                verkaufte_anteile_pro_etf[isin] += abs(anzahl)

        # Nun suchen wir für jede eindeutige ISIN den yfinance-Ticker
        for isin in isin_name_mapping.keys():
            try:
                # yfinance Search funktioniert hervorragend mit 12-stelligen ISINs!
                suche = yf.Search(isin, max_results=1)
                if suche.quotes:
                    ticker_mapping[isin] = suche.quotes[0]['symbol']
                else:
                    ticker_mapping[isin] = isin  # Fallback
            except Exception as e:
                ticker_mapping[isin] = isin

        return {
            "success": True,
            "data": gefilterte_daten,
            "kurse": kurse,
            "verkaufte_anteile": verkaufte_anteile_pro_etf,
            "ticker_mapping": ticker_mapping,
            "isin_name_mapping": isin_name_mapping  # NEU: Schickt die Klarnamen mit
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
    

@app.get("/api/download-pdf")
def download_pdf(ticker: str, ziel: str, netto: float):
    try:
        # 1. Rufe deine Funktion auf, die den Buffer zurückgibt
        # (Passe die Argumente so an, wie deine Funktion sie braucht)
        pdf_buffer = funktionen.deine_pdf_funktion(ticker, ziel, netto) 
        
        # 2. Die StreamingResponse schickt den Inhalt des Buffers direkt zum Browser
        return StreamingResponse(
            pdf_buffer, 
            media_type="application/pdf",
            headers={
                # "attachment" erzwingt den Download im Browser direkt als Datei
                "Content-Disposition": f'attachment; filename="Steuerreport_{ticker}.pdf"'
            }
        )
    except Exception as e:
        return {"success": False, "error": str(e)}
    


if __name__ == "__main__":
    # Render übergibt den Port als Umgebungsvariable, lokal wird 8000 genutzt
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)