from fastapi import FastAPI, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import io
from models import CalculationPayload
import funktionen  # Deine bereits existierende Datei
import requests
from fastapi import Query
import yfinance as yf
from fastapi import HTTPException

app = FastAPI(title="ETF Steuer Rechner")
templates = Jinja2Templates(directory="templates")

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
        df = pd.read_csv(io.BytesIO(contents), decimal=".")
        
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
    # Zum Testen drucken wir die empfangenen Daten einmal sauber in der Server-Konsole aus
    print(f"Ziel: {payload.rechen_ziel}")
    print(f"Anzahl Käufe übermittelt: {len(payload.kaeufe)}")

    # Hier verknüpfst du deine funktionen.py. 
    # Du kannst entweder das ganze 'payload'-Objekt übergeben oder die Werte einzeln:
    try:
        # BEISPIEL-AUFRUF (Passe das an deine echten Funktionsnamen an!):
        # Wenn deine Funktion z.B. alle Daten braucht, kannst du ihr 'payload' übergeben.
        
        if payload.rechen_ziel == "steuerfrei":
            # ergebnis = {"nachricht": "Hier wird die Funktion für steuerfreie Anteile aufgerufen"}
            ergebnis = funktionen.berechne_steuerfrei(payload)
            
        elif payload.rechen_ziel == "wunschnetto":
            ergebnis = {"nachricht": f"Hier wird Wunschnetto für {payload.wert_wunschnetto}€ berechnet"}
            # ergebnis = funktionen.berechne_wunschnetto(payload)
            
        else:
            ergebnis = {"nachricht": f"Hier werden Steuern für {payload.wert_anteile} Anteile berechnet"}
            # ergebnis = funktionen.berechne_anteile_steuer(payload)

        # Gib das mathematische Ergebnis als Dictionary zurück. FastAPI macht daraus automatisch JSON.
        return ergebnis

    except Exception as e:
        return {"error": f"Fehler bei der Berechnung: {str(e)}"}
    

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
    

from models import SparplanPayload

@app.post("/api/generate-sparplan")
async def generate_sparplan(payload: SparplanPayload):
    try:
        ticker = yf.Ticker(payload.symbol)
        # Historische Daten für den Zeitraum laden
        df = ticker.history(start=payload.start_date, end=payload.end_date, interval="1d")
        
        if df.empty:
            return {"success": False, "error": "Keine historischen Kurse für diesen Zeitraum gefunden."}
            
        # Wir gruppieren nach Jahr und Monat, um den gewünschten Ausführungstag zu finden
        df['jahr'] = df.index.year
        df['monat'] = df.index.month
        df['tag'] = df.index.day
        
        generierte_kaeufe = []
        
        # Für jeden Monat im Zeitraum den passenden Tag suchen
        grouped = df.groupby(['jahr', 'monat'])
        for (jahr, monat), group in grouped:
            # Versuche den exakten Tag (z.B. 1. oder 15.) zu finden, sonst den nächsten verfügbaren Börsentag
            ziel_tag = payload.tag
            verfuegbare_tage = group['tag'].tolist()
            
            # Finde den Tag, der am nächsten am Ziel-Tag liegt (aber nicht davor, falls möglich)
            gueltiger_tag = min(verfuegbare_tage, key=lambda x: abs(x - ziel_tag))
            
            row = group[group['tag'] == gueltiger_tag].iloc[0]
            kauf_datum = row.name.strftime('%Y-%m-%d')
            kauf_preis = round(row['Close'], 2)
            
            # Anzahl Anteile = Sparrate / Kurs
            anzahl_anteile = round(payload.rate / kauf_preis, 5)
            
            generierte_kaeufe.append({
                "datum": kauf_datum,
                "anzahl": anzahl_anteile,
                "preis": kauf_preis
            })
            
        return {"success": True, "data": generierte_kaeufe}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    

import re  # Oben bei den Importen hinzufügen, falls noch nicht da

@app.post("/api/upload-trade-republic")
async def upload_trade_republic(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        entry_df = pd.read_csv(io.BytesIO(contents), decimal=".")
        
        erforderliche_spalten = ["datetime", "type", "symbol", "shares", "price"]
        if not set(erforderliche_spalten).issubset(entry_df.columns):
            return {
                "success": False, 
                "error": "Die CSV entspricht nicht dem erwarteten Format (Spalten datetime, type, symbol, shares, price fehlen)."
            }
            
        entry_df["datetime"] = pd.to_datetime(entry_df["datetime"], errors="coerce")
        kaeufe = entry_df[entry_df["type"] == "BUY"].copy()
        
        if "asset_class" in kaeufe.columns:
            kaeufe = kaeufe[kaeufe["asset_class"].isin(["ETF", "STOCK", "FUND"])]
            
        if kaeufe.empty:
            return {"success": False, "error": "In der CSV wurden keine ETF- oder Aktienkäufe (BUY) gefunden."}
            
        kaeufe["datum_formatiert"] = kaeufe["datetime"].dt.strftime('%Y-%m-%d')
        
        # 4. Wertpapier-Liste & Live-Kurse ermitteln
        optionen = []
        ticker_kurse = {}  # Speichert den Kurs für jedes gefundene Ticker-Symbol
        
        if "name" in kaeufe.columns:
            etf_liste = kaeufe[["symbol", "name"]].dropna(subset=["symbol"]).drop_duplicates()
            for _, row in etf_liste.iterrows():
                display_name = f"{row['name']} ({row['symbol']})"
                optionen.append(display_name)
                
                # Live-Kurs via yfinance versuchen zu laden
                try:
                    ticker_obj = yf.Ticker(row['symbol'])
                    preis = ticker_obj.fast_info.get("lastPrice")
                    if preis is None:
                        preis = ticker_obj.history(period="1d")["Close"].iloc[-1]
                    ticker_kurse[display_name] = round(preis, 2)
                except Exception:
                    ticker_kurse[display_name] = 100.00  # Fallback
                    
            kaeufe["asset_key"] = kaeufe["name"] + " (" + kaeufe["symbol"] + ")"
        else:
            einzigartige_symbole = kaeufe["symbol"].dropna().unique().tolist()
            optionen = einzigartige_symbole
            for sym in einzigartige_symbole:
                try:
                    ticker_obj = yf.Ticker(sym)
                    preis = ticker_obj.fast_info.get("lastPrice")
                    if preis is None:
                        preis = ticker_obj.history(period="1d")["Close"].iloc[-1]
                    ticker_kurse[sym] = round(preis, 2)
                except Exception:
                    ticker_kurse[sym] = 100.00  # Fallback
            kaeufe["asset_key"] = kaeufe["symbol"]

        all_data = []
        for _, row in kaeufe.iterrows():
            all_data.append({
                "asset": str(row["asset_key"]),
                "datum": str(row["datum_formatiert"]) if pd.notna(row["datum_formatiert"]) else "",
                "anzahl": float(row["shares"]),
                "preis": float(row["price"])
            })
            
        return {
            "success": True, 
            "etfs": optionen, 
            "kurse": ticker_kurse,  # NEU: Wir senden die Live-Kurse direkt mit!
            "data": all_data
        }
        
    except Exception as e:
        return {"success": False, "error": f"Fehler beim Verarbeiten: {str(e)}"}

# @app.post("/api/upload-trade-republic")
# async def upload_trade_republic(file: UploadFile = File(...)):
#     try:
#         contents = await file.read()
#         # Datei einlesen (wie in deinem Streamlit-Code)
#         entry_df = pd.read_csv(io.BytesIO(contents), decimal=".")
        
#         # 1. Spalten-Validierung aus deinem Streamlit-Code
#         erforderliche_spalten = ["datetime", "type", "symbol", "shares", "price"]
#         # Falls 'name' oder 'asset_class' nicht zwingend in jeder TR-Version sind, 
#         # prüfen wir hier die Kernspalten
#         if not set(erforderliche_spalten).issubset(entry_df.columns):
#             return {
#                 "success": False, 
#                 "error": "Die CSV entspricht nicht dem erwarteten Format (Spalten datetime, type, symbol, shares, price fehlen)."
#             }
            
#         # 2. Datum konvertieren (Fehler abgefangen)
#         entry_df["datetime"] = pd.to_datetime(entry_df["datetime"], errors="coerce")
        
#         # 3. Filterung exakt wie in deinem Streamlit-Code (BUY)
#         # Falls 'asset_class' fehlt, filtern wir nur nach BUY, um flexibel zu bleiben
#         kaeufe = entry_df[entry_df["type"] == "BUY"].copy()
        
#         if "asset_class" in kaeufe.columns:
#             kaeufe = kaeufe[kaeufe["asset_class"].isin(["ETF", "STOCK", "FUND"])]
            
#         if kaeufe.empty:
#             return {"success": False, "error": "In der CSV wurden keine ETF- oder Aktienkäufe (BUY) gefunden."}
            
#         # Formatierung des Datums für das HTML-Inputfeld (YYYY-MM-DD)
#         kaeufe["datum_formatiert"] = kaeufe["datetime"].dt.strftime('%Y-%m-%d')
        
#         # 4. Wertpapier-Liste für das Dropdown generieren
#         # Wenn die Spalte 'name' existiert, nutzen wir sie, sonst nur das Symbol
#         optionen = []
#         if "name" in kaeufe.columns:
#             # Duplikate entfernen und Liste bauen
#             etf_liste = kaeufe[["symbol", "name"]].dropna(subset=["symbol"]).drop_duplicates()
#             for _, row in etf_liste.iterrows():
#                 optionen.append(f"{row['name']} ({row['symbol']})")
#             # Wir merken uns im JSON nachher das 'name (symbol)' als Schlüssel
#             kaeufe["asset_key"] = kaeufe["name"] + " (" + kaeufe["symbol"] + ")"
#         else:
#             einzigartige_symbole = kaeufe["symbol"].dropna().unique().tolist()
#             optionen = einzigartige_symbole
#             kaeufe["asset_key"] = kaeufe["symbol"]

#         # 5. Daten für das Frontend strukturieren
#         all_data = []
#         for _, row in kaeufe.iterrows():
#             all_data.append({
#                 "asset": str(row["asset_key"]),
#                 "datum": str(row["datum_formatiert"]) if pd.notna(row["datum_formatiert"]) else "",
#                 "anzahl": float(row["shares"]),
#                 "preis": float(row["price"])
#             })
            
#         return {
#             "success": True, 
#             "etfs": optionen, 
#             "data": all_data
#         }
        
#     except Exception as e:
#         return {"success": False, "error": f"Fehler beim Verarbeiten: {str(e)}"}
    