from fastapi import FastAPI, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import io
from models import CalculationPayload
import funktionen  # Deine bereits existierende Datei

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
    