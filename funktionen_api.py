from datetime import datetime
import numpy as np
import pandas as pd
# Importiere dein Modell aus deiner models.py
from models import CalculationPayload 
import yfinance as yf
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
# from reportlab.lib.styles import getSampleStyleSheet
# from reportlab.lib.pagesizes import A4
# from reportlab.lib.units import cm
# from reportlab.platypus import TableStyle
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from models import CalculationPayload #, RechenZiel, KirchensteuerStatus
from reportlab.platypus import Image
import os
from reportlab.lib.utils import ImageReader
from reportlab.platypus import KeepTogether

def lade_kursdaten(ticker, startjahr):

    ticker_obj = yf.Ticker(ticker)

    kurs_data = ticker_obj.history(start=f"{startjahr}-01-01")

    kurs_data["jahr"] = kurs_data.index.year

    jahresstart = kurs_data.groupby("jahr").first()

    # prüfen ob Daten für startjahr existieren
    if startjahr not in jahresstart.index:
        raise ValueError(f"Überprüfen Sie, ob Sie Ihre Kaufdaten korrekt eingegeben haben. Es liegen keine automatischen Kursdaten für Ihren ältesten Kauf vor. Falls alles stimmt beachten Sie, dass die Vorabpauschale nicht richtig berechnet werden kann.")

    jahresstart = jahresstart.loc[startjahr:]

    jahresstart = jahresstart[["Close"]]

    jahresstart = jahresstart.reset_index()

    jahresstart.columns = ["jahr", "preis_1_jan"]

    return jahresstart

def berechne_vorabpauschalen(kursdaten):

    basiszins_df = pd.read_csv("basiszins.csv")

    ergebnisse = []

    for jahr in kursdaten["jahr"].unique():

        if jahr not in basiszins_df["jahr"].values or jahr == datetime.today().year:
            continue


        jahr_daten = kursdaten[kursdaten["jahr"] == jahr]
        folgejahr_daten = kursdaten[kursdaten["jahr"] == jahr + 1]


        preis_1_jan = jahr_daten.iloc[0]["preis_1_jan"]
        preis_31_dez = folgejahr_daten.iloc[0]["preis_1_jan"] if not folgejahr_daten.empty else jahr_daten.iloc[-1]["preis_1_jan"]

        wertsteigerung = max(0, preis_31_dez - preis_1_jan)

        basiszins = basiszins_df.loc[
            basiszins_df["jahr"] == jahr, "basiszins"
        ].values[0]

        basisertrag = preis_1_jan * basiszins/100 * 0.7 # gesetzliche konstante

        vorabpauschale = min(wertsteigerung, basisertrag)

        ergebnisse.append({
            "jahr": jahr,
            "wert": vorabpauschale 
        })

    # erstelle ein leeres df mit nur spaltennemen

    if not ergebnisse:
        ergebnisse = pd.DataFrame(columns=["jahr", "wert"])
    else:
        ergebnisse = pd.DataFrame(ergebnisse)

    return ergebnisse


def finde_anteile_ohne_steuer(max_anteile, aktueller_kurs, data, vorabpauschale, bereits_verkauft, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung):

    low = 0.0
    high = float(max_anteile)

    # prüfen ob überhaupt Steuern entstehen
    gewinn, brutto, gesamte_vorabpauschale= bestimme_steuer(
        high, aktueller_kurs, data, vorabpauschale, bereits_verkauft, tagesgenau = tagesgeanue_berechnung
    )

    steuerpflichtiger_gewinn = bestimme_steuerpflichtigen_gewinn(
        gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag
    )

    for _ in range(100):

        mid = (low + high) / 2

        gewinn, brutto, gesamte_vorabpauschale= bestimme_steuer(
            mid, aktueller_kurs, data, vorabpauschale, bereits_verkauft, tagesgenau = tagesgeanue_berechnung
        )

        steuerpflichtiger_gewinn = bestimme_steuerpflichtigen_gewinn(
            gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag
        )

        if abs(high - low) < 0.000001:
            return round(mid, 6)

        if steuerpflichtiger_gewinn > 0:
            high = mid
        else:
            low = mid

    return round(mid, 6)




def bestimme_steuer(anzahl_verkaufen, aktueller_kurs, data, vorabpauschale, bereits_verkauft, tagesgenau=False):
    shares = data["anzahl"].to_numpy(dtype=float)
    prices = data["preis"].to_numpy(dtype=float)
    dates = pd.to_datetime(data["datum"]).to_numpy()

    # bereits verkaufte Anteile entfernen (FIFO)
    remaining = shares.copy()
    verkauft = bereits_verkauft

    for i in range(len(remaining)):
        if verkauft <= 0:
            break
        if remaining[i] <= verkauft:
            verkauft -= remaining[i]
            remaining[i] = 0
        else:
            remaining[i] -= verkauft
            verkauft = 0

    cum_shares = np.cumsum(remaining)

    # print(anzahl_verkaufen, cum_shares[-1])

    # if cum_shares[-1] < anzahl_verkaufen - 1e-9:
    #     print("Warnung: Sie verfügen nicht über ausreichend Anteile für das gewünschte Netto. Es werden alle verfügbaren Anteile verkauft.")
    #     warnungen.append("Sie verfügen nicht über ausreichend Anteile für das gewünschte Netto. Es werden alle verfügbaren Anteile verkauft.")

    idx = np.searchsorted(cum_shares, anzahl_verkaufen)

    verkaufte_shares = np.zeros_like(remaining)

    if idx > 0:
        verkaufte_shares[:idx] = remaining[:idx]

    if idx < len(remaining):
        vorher = cum_shares[idx-1] if idx > 0 else 0
        verkaufte_shares[idx] = anzahl_verkaufen - vorher

    # Gewinn und brutto (vektorisiert)
    gewinn = np.sum((aktueller_kurs - prices) * verkaufte_shares)
    brutto = np.sum(aktueller_kurs * verkaufte_shares)

    gesamte_vorabpauschale = 0

    if len(vorabpauschale) == 0:
        return gewinn, brutto, gesamte_vorabpauschale

    vp_jahre = vorabpauschale["jahr"].to_numpy()
    vp_values = vorabpauschale["wert"].to_numpy()

    for i in np.where(verkaufte_shares > 0)[0]:

        kaufdatum = pd.Timestamp(dates[i])
        jahr_kauf = kaufdatum.year

        mask = vp_jahre >= jahr_kauf

        jahre = vp_jahre[mask]
        vp = vp_values[mask]

        if len(jahre) == 0:
            continue

        if not tagesgenau:

            monate = np.where(
                jahre == jahr_kauf,
                12 - kaufdatum.month + 1,
                12
            )

            anteil = monate / 12

        else:

            anteil = np.ones_like(jahre, dtype=float)

            first_year_mask = jahre == jahr_kauf

            if np.any(first_year_mask):

                ende = datetime(jahr_kauf, 12, 31)
                tage = (ende - kaufdatum).days + 1
                anteil[first_year_mask] = tage / 365

        gesamte_vorabpauschale += np.sum(vp * anteil) * verkaufte_shares[i]

    return gewinn, brutto, gesamte_vorabpauschale



def bestimme_steuerpflichtigen_gewinn(gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag, all = False):
    gewinn_nach_vorabpauschale = gewinn - gesamte_vorabpauschale
    gewinn_teilfreistellung = gewinn_nach_vorabpauschale * (1 - teilfreistellung_quote)
    gewinn_nach_verlusttopf = max(0, gewinn_teilfreistellung - verlusttopf)
    gewinn_steuerpflichtig = max(0, gewinn_nach_verlusttopf - freibetrag)

    if all:
        return gewinn_nach_vorabpauschale, gewinn_teilfreistellung, gewinn_nach_verlusttopf, gewinn_steuerpflichtig
    else:
        return gewinn_steuerpflichtig


def bestimme_steuerpflichtigen_gewinnn(gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag, all = False):
    gewinn_nach_vorabpauschale = gewinn - gesamte_vorabpauschale
    gewinn_teilfreistellung = gewinn_nach_vorabpauschale * (1 - teilfreistellung_quote)
    gewinn_nach_verlusttopf = max(0, gewinn_teilfreistellung - verlusttopf)
    gewinn_steuerpflichtig = max(0, gewinn_nach_verlusttopf - freibetrag)
    if all:
        return gewinn_nach_vorabpauschale, gewinn_teilfreistellung, gewinn_nach_verlusttopf, gewinn_steuerpflichtig
    else:
        return gewinn_steuerpflichtig


def bestimme_netto(brutto, gewinn, steuersatz, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag):
    gewinn_steuerpflichtig = bestimme_steuerpflichtigen_gewinnn(gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag, all = False)
                                       
    steuer = gewinn_steuerpflichtig * steuersatz
    netto = brutto - steuer

    return netto


def finde_anteile(ziel_netto, max_anteile, aktueller_kurs, data, vorabpauschale, bereits_verkauft, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung):

    low = 0.0
    high = float(max_anteile)

    for _ in range(60):   # genügend Iterationen für hohe Genauigkeit

        mid = (low + high) / 2

        gewinn, brutto, gesamte_vorabpauschale = bestimme_steuer(
            mid, aktueller_kurs, data, vorabpauschale, bereits_verkauft, tagesgenau = tagesgeanue_berechnung
        )

        netto = bestimme_netto(
            brutto, gewinn, steuersatz, teilfreistellung_quote,
            gesamte_vorabpauschale, verlusttopf, freibetrag
        )

        if abs(netto - ziel_netto) < 0.000001:
            return round(mid, 6)

        if netto < ziel_netto:
            low = mid
        else:
            high = mid

    return round(mid, 6)


# def daten_aufbereiten(payload: CalculationPayload):
#     # 1. Da payload.kaeufe eine Liste von Pydantic-Objekten (KaufEintrag) ist,
#     # wandeln wir jedes Objekt per .model_dump() in ein normales Dict um.
#     kaeufe_liste = [kauf.model_dump() for kauf in payload.kaeufe]
    
#     # 2. DataFrame aus der Liste von Dictionaries erstellen
#     df_kaeufe = pd.DataFrame(kaeufe_liste)
    
#     # Falls die Liste leer sein sollte, fangen wir das hier ab, damit es keine Fehler gibt
#     if df_kaeufe.empty:
#         raise ValueError("Die Liste der Käufe ist leer. Bitte geben Sie mindestens einen Kauf ein.")
    
#     # Optional: Da du steuerlich vermutlich nach dem FIFO-Prinzip (First-In-First-Out)
#     # rechnen musst, sortieren wir das DataFrame sicherheitshalber nach Datum.
#     data = df_kaeufe.sort_values(by='datum').reset_index(drop=True)

#     max_anteile = df_kaeufe["anzahl"].sum()
#     bereits_verkauft = payload.bereits_verkaufte_anteile
#     aktueller_kurs = payload.verkaufskurs

#     # 🎯 BEST PRACTICE: Nutzung des KirchensteuerStatus-Enums
#     if payload.kirchensteuer == KirchensteuerStatus.NEIN:
#         steuersatz = 0.26375
#     elif payload.kirchensteuer == KirchensteuerStatus.ACHT_PROZENT:
#         steuersatz = 0.2782
#     elif payload.kirchensteuer == KirchensteuerStatus.NEUN_PROZENT:
#         steuersatz = 0.2799
#     else:
#         # Sicherheits-Fallback falls unerwartet etwas schiefgeht
#         steuersatz = 0.26375

#     # Achtung: In deiner index.html / app.js übergibst du die Teilfreistellung vermutlich 
#     # bereits als Prozentwert (z.B. 30 statt 0.30) oder als Dezimalzahl?
#     # Wenn dein JS eine Zahl wie 30 schickt, konvertiert dies deine Zeile hier sauber zu 0.3.
#     teilfreistellung_quote = payload.teilfreistellung * 0.01
#     verlusttopf = payload.verlusttopf
#     freibetrag = payload.freibetrag
#     tagesgeanue_berechnung = payload.tagesgenau
#     return data, max_anteile, bereits_verkauft, aktueller_kurs, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung

# def berechne_steuerfrei(payload: CalculationPayload, vorabpauschalen: pd.DataFrame) -> pd.DataFrame:
#     """
#     Nimmt das CalculationPayload entgegen, extrahiert die Käufe,
#     wandelt sie in ein Pandas DataFrame um und berechnet wichtige Basiswerte.
#     """
#     data, max_anteile, bereits_verkauft, aktueller_kurs, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung = daten_aufbereiten(payload)
    
#     anzahl_verkaufen = finde_anteile_ohne_steuer(max_anteile-bereits_verkauft, aktueller_kurs, data, vorabpauschalen, bereits_verkauft, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung)
#     gewinn, brutto, gesamte_vorabpauschale = bestimme_steuer(anzahl_verkaufen, aktueller_kurs, data, vorabpauschalen, bereits_verkauft, tagesgenau = tagesgeanue_berechnung)

#     gewinn_nach_vorabpauschale, gewinn_teilfreistellung, gewinn_nach_verlusttopf, gewinn_steuerpflichtig = bestimme_steuerpflichtigen_gewinn(gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag, all=True)
#     steuer = gewinn_steuerpflichtig * steuersatz
#     netto = brutto - steuer

#     if gewinn_teilfreistellung < 0:
#         verlusttopf_nach_verkauf = verlusttopf - gewinn_teilfreistellung
#     else:
#         verlusttopf_nach_verkauf = max(0, verlusttopf - gewinn_teilfreistellung)

#     # 🎯 .value gibt den ursprünglichen String ("nein", "8%" oder "9%") an das PDF weiter
#     kirchensteuer = payload.kirchensteuer.value
#     gesamtkosten = sum(data["anzahl"] * data["preis"])

#     return anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, gewinn_teilfreistellung, gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, steuer, netto, gesamtkosten, aktueller_kurs, freibetrag, verlusttopf_nach_verkauf, gesamte_vorabpauschale, teilfreistellung_quote, kirchensteuer


# def berechne_wunschnetto(payload: CalculationPayload, vorabpauschalen: pd.DataFrame):
#     data, max_anteile, bereits_verkauft, aktueller_kurs, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung = daten_aufbereiten(payload)
#     gewolltes_netto = payload.wert_wunschnetto
    
#     anzahl_verkaufen = finde_anteile(gewolltes_netto, max_anteile, aktueller_kurs, data, vorabpauschalen, bereits_verkauft, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung)
#     gewinn, brutto, gesamte_vorabpauschale= bestimme_steuer(anzahl_verkaufen, aktueller_kurs, data, vorabpauschalen, bereits_verkauft, tagesgenau = tagesgeanue_berechnung)

#     gewinn_nach_vorabpauschale, gewinn_teilfreistellung, gewinn_nach_verlusttopf, gewinn_steuerpflichtig = bestimme_steuerpflichtigen_gewinn(gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag, all=True)
#     steuer = gewinn_steuerpflichtig * steuersatz
#     netto = brutto - steuer

#     if gewinn_teilfreistellung < 0:
#         verlusttopf_nach_verkauf = verlusttopf - gewinn_teilfreistellung
#     else:
#         verlusttopf_nach_verkauf = max(0, verlusttopf - gewinn_teilfreistellung)

#     # 🎯 .value gibt den ursprünglichen String ("nein", "8%" oder "9%") an das PDF weiter
#     kirchensteuer = payload.kirchensteuer.value
#     gesamtkosten = sum(data["anzahl"] * data["preis"])

#     return anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, gewinn_teilfreistellung, gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, steuer, netto, gesamtkosten, aktueller_kurs, freibetrag, verlusttopf_nach_verkauf, gesamte_vorabpauschale, teilfreistellung_quote, kirchensteuer

# def berechne_anteile_steuer(payload: CalculationPayload, vorabpauschalen: pd.DataFrame):
#     data, max_anteile, bereits_verkauft, aktueller_kurs, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung = daten_aufbereiten(payload)
#     anzahl_verkaufen = payload.wert_anteile

#     gewinn, brutto, gesamte_vorabpauschale = bestimme_steuer(anzahl_verkaufen, aktueller_kurs, data, vorabpauschalen, bereits_verkauft, tagesgenau = tagesgeanue_berechnung)

#     # Typo korrigiert: bestimme_steuerpflichtigen_gewinn (vorher drei 'n' am Ende)
#     gewinn_nach_vorabpauschale, gewinn_teilfreistellung, gewinn_nach_verlusttopf, gewinn_steuerpflichtig = bestimme_steuerpflichtigen_gewinn(gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag, all=True)
#     steuer = gewinn_steuerpflichtig * steuersatz
#     netto = brutto - steuer

#     if gewinn_teilfreistellung < 0:
#         verlusttopf_nach_verkauf = verlusttopf - gewinn_teilfreistellung
#     else:
#         verlusttopf_nach_verkauf = max(0, verlusttopf - gewinn_teilfreistellung)

#     # 🎯 .value gibt den ursprünglichen String ("nein", "8%" oder "9%") an das PDF weiter
#     kirchensteuer = payload.kirchensteuer.value
#     gesamtkosten = sum(data["anzahl"] * data["preis"])

#     return anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, gewinn_teilfreistellung, gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, steuer, netto, gesamtkosten, aktueller_kurs, freibetrag, verlusttopf_nach_verkauf, gesamte_vorabpauschale, teilfreistellung_quote, kirchensteuer

def daten_aufbereiten(payload: CalculationPayload):
    # 1. Da payload.kaeufe eine Liste von Pydantic-Objekten (KaufEintrag) ist,
    # wandeln wir jedes Objekt per .model_dump() in ein normales Dict um.
    kaeufe_liste = [kauf.model_dump() for kauf in payload.kaeufe]
    
    # 2. DataFrame aus der Liste von Dictionaries erstellen
    df_kaeufe = pd.DataFrame(kaeufe_liste)
    
    # Falls die Liste leer sein sollte, fangen wir das hier ab, damit es keine Fehler gibt
    if df_kaeufe.empty:
        raise ValueError("Die Liste der Käufe ist leer. Bitte geben Sie mindestens einen Kauf ein.")
    
    # Optional: Da du steuerlich vermutlich nach dem FIFO-Prinzip (First-In-First-Out)
    # rechnen musst, sortieren wir das DataFrame sicherheitshalber nach Datum.
    data = df_kaeufe.sort_values(by='datum').reset_index(drop=True)


    max_anteile = df_kaeufe["anzahl"].sum()
    bereits_verkauft = payload.bereits_verkaufte_anteile
    aktueller_kurs = payload.verkaufskurs


    # return df_vorabpauschale
    if payload.kirchensteuer == "keine":
        steuersatz = 0.26375
    elif payload.kirchensteuer == "8":
        steuersatz = 0.2782
    elif payload.kirchensteuer == "9":
        steuersatz = 0.2799

    teilfreistellung_quote = payload.teilfreistellung * 0.01
    verlusttopf = payload.verlusttopf
    freibetrag = payload.freibetrag
    tagesgeanue_berechnung = payload.tagesgenau
    return data, max_anteile, bereits_verkauft, aktueller_kurs, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung


def berechne_steuerfrei(payload: CalculationPayload, vorabpauschalen: pd.DataFrame) -> pd.DataFrame:
    """
    Nimmt das CalculationPayload entgegen, extrahiert die Käufe,
    wandelt sie in ein Pandas DataFrame um und berechnet wichtige Basiswerte.
    """
    data, max_anteile, bereits_verkauft, aktueller_kurs, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung = daten_aufbereiten(payload)
    
    anzahl_verkaufen = finde_anteile_ohne_steuer(max_anteile-bereits_verkauft, aktueller_kurs, data, vorabpauschalen, bereits_verkauft, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung)
    gewinn, brutto, gesamte_vorabpauschale = bestimme_steuer(anzahl_verkaufen, aktueller_kurs, data, vorabpauschalen, bereits_verkauft, tagesgenau = tagesgeanue_berechnung)

    gewinn_nach_vorabpauschale, gewinn_teilfreistellung, gewinn_nach_verlusttopf, gewinn_steuerpflichtig = bestimme_steuerpflichtigen_gewinn(gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag, all=True)
    steuer = gewinn_steuerpflichtig * steuersatz
    netto = brutto - steuer

    if gewinn_teilfreistellung < 0:
        verlusttopf_nach_verkauf = verlusttopf - gewinn_teilfreistellung
    else:
        verlusttopf_nach_verkauf = max(0, verlusttopf - gewinn_teilfreistellung)

    kirchensteuer = payload.kirchensteuer
    gesamtkosten = sum(data["anzahl"] * data["preis"])

    # return f"Steuerfrei verkaufbar: {anzahl_verkaufen:.6f} Anteile\nNetto nach Steuern: {netto:.2f}€\nVerlusttopf nach Verkauf: {verlusttopf_nach_verkauf:.2f}€"
    return anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, gewinn_teilfreistellung, gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, steuer, netto, gesamtkosten, aktueller_kurs, freibetrag, verlusttopf_nach_verkauf, gesamte_vorabpauschale, teilfreistellung_quote, kirchensteuer


def berechne_wunschnetto(payload: CalculationPayload, vorabpauschalen: pd.DataFrame):
    data, max_anteile, bereits_verkauft, aktueller_kurs, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung = daten_aufbereiten(payload)
    gewolltes_netto = payload.wert_wunschnetto
    
    anzahl_verkaufen = finde_anteile(gewolltes_netto, max_anteile, aktueller_kurs, data, vorabpauschalen, bereits_verkauft, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung)
    gewinn, brutto, gesamte_vorabpauschale= bestimme_steuer(anzahl_verkaufen, aktueller_kurs, data, vorabpauschalen, bereits_verkauft, tagesgenau = tagesgeanue_berechnung)

    gewinn_nach_vorabpauschale, gewinn_teilfreistellung, gewinn_nach_verlusttopf, gewinn_steuerpflichtig = bestimme_steuerpflichtigen_gewinn(gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag, all=True)
    steuer = gewinn_steuerpflichtig * steuersatz
    netto = brutto - steuer

    if gewinn_teilfreistellung < 0:
        verlusttopf_nach_verkauf = verlusttopf - gewinn_teilfreistellung
    else:
        verlusttopf_nach_verkauf = max(0, verlusttopf - gewinn_teilfreistellung)

    kirchensteuer = payload.kirchensteuer
    gesamtkosten = sum(data["anzahl"] * data["preis"])

    # return f"Steuerfrei verkaufbar: {anzahl_verkaufen:.6f} Anteile\nNetto nach Steuern: {netto:.2f}€\nVerlusttopf nach Verkauf: {verlusttopf_nach_verkauf:.2f}€"
    return anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, gewinn_teilfreistellung, gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, steuer, netto, gesamtkosten, aktueller_kurs, freibetrag, verlusttopf_nach_verkauf, gesamte_vorabpauschale, teilfreistellung_quote, kirchensteuer

def berechne_anteile_steuer(payload, vorabpauschalen):
    data, max_anteile, bereits_verkauft, aktueller_kurs, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung = daten_aufbereiten(payload)
    anzahl_verkaufen = payload.wert_anteile

    
    gewinn, brutto, gesamte_vorabpauschale = bestimme_steuer(anzahl_verkaufen, aktueller_kurs, data, vorabpauschalen, bereits_verkauft, tagesgenau = tagesgeanue_berechnung)

    gewinn_nach_vorabpauschale, gewinn_teilfreistellung, gewinn_nach_verlusttopf, gewinn_steuerpflichtig = bestimme_steuerpflichtigen_gewinnn(gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag, all=True)
    steuer = gewinn_steuerpflichtig * steuersatz
    netto = brutto - steuer

    if gewinn_teilfreistellung < 0:
        verlusttopf_nach_verkauf = verlusttopf - gewinn_teilfreistellung
    else:
        verlusttopf_nach_verkauf = max(0, verlusttopf - gewinn_teilfreistellung)

    kirchensteuer = payload.kirchensteuer
    gesamtkosten = sum(data["anzahl"] * data["preis"])

    # return f"Steuerfrei verkaufbar: {anzahl_verkaufen:.6f} Anteile\nNetto nach Steuern: {netto:.2f}€\nVerlusttopf nach Verkauf: {verlusttopf_nach_verkauf:.2f}€"
    return anzahl_verkaufen, max_anteile, bereits_verkauft, brutto, gewinn, gewinn_teilfreistellung, gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf, gewinn_steuerpflichtig, steuer, netto, gesamtkosten, aktueller_kurs, freibetrag, verlusttopf_nach_verkauf, gesamte_vorabpauschale, teilfreistellung_quote, kirchensteuer


def eur(x):
    return f"{x:.2f}".replace(".", ",") + " €"

def anteil(x):
    return f"{x:.5f}".replace(".", ",")

def footer(canvas, doc):
    canvas.saveState()

    # 1. Normale Schriftfarbe für das Datum / den Rest festlegen
    canvas.setFont("Helvetica", 9)
    canvas.setFillColorRGB(0, 0, 0) # Schwarz für den normalen Text

    jetzt = datetime.now().strftime("%d.%m.%Y, %H:%M Uhr")
    
    # Wir teilen den Text auf, damit wir den Link separat färben können
    text_start = "Berechnet mit "
    text_link = "etfsteuerrechner.de"
    text_end = f" am {jetzt} – Angaben ohne Gewähr."
    
    x = 2 * cm
    y = 1.5 * cm

    # Start-Text zeichnen
    canvas.drawString(x, y, text_start)
    x_link = x + canvas.stringWidth(text_start, "Helvetica", 9)
    
    # Link-Text in Blau zeichnen
    canvas.setFillColorRGB(0, 0, 1) # Reines Blau (R=0, G=0, B=1)
    canvas.drawString(x_link, y, text_link)
    
    # Klassische Unterstreichung für den Link zeichnen
    canvas.setStrokeColorRGB(0, 0, 1) # Blaue Linie
    canvas.setLineWidth(0.5)
    link_breite = canvas.stringWidth(text_link, "Helvetica", 9)
    canvas.line(x_link, y - 1, x_link + link_breite, y - 1)
    
    # Restlichen Text wieder in Schwarz zeichnen
    canvas.setFillColorRGB(0, 0, 0)
    x_end = x_link + link_breite
    canvas.drawString(x_end, y, text_end)

    # Die klickbare Box genau über den blauen Text legen
    canvas.linkURL(
        "https://www.etfsteuerrechner.de",
        (x_link, y - 2, x_link + link_breite, y + 10),
        relative=0
    )

    canvas.restoreState()


def header_later_pages(canvas, doc):
    """Zeichnet das Logo ab Seite 2 oben rechts in die Ecke."""
    canvas.saveState()

        
    # Pfad zu deinem Logo ermitteln
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(current_dir, "static", "logo.png") 
    
    # Maße auslesen für die proportionale Skalierung
    img_reader = ImageReader(logo_path)
    img_w, img_h = img_reader.getSize()
    
    # Auf den Folgeseiten machen wir es dezent (z. B. 22pt hoch)
    ziel_hoehe = 22.0
    ziel_breite = (img_w / img_h) * ziel_hoehe
    
    # --- POSITIONIERUNG OBEN RECHTS ---
    # A4 Breite ist 595.27 pt. Wir ziehen den rechten Rand (2cm = ca. 56.7pt) 
    # und die Breite des Logos ab, damit es exakt rechtsbündig abschließt.
    x_pos = 595.27 - (2 * 28.34) - ziel_breite  # 1 cm = 28.34 pt bei ReportLab
    
    # A4 Höhe ist 841.89 pt. Wir platzieren es knapp unter dem oberen Rand.
    y_pos = 841.89 - (1.5 * 28.34)
    
    # Bild direkt auf das Canvas zeichnen
    # canvas.drawImage(logo_path, x_pos, y_pos, width=ziel_breite, height=ziel_hoehe)

    canvas.drawImage(
            logo_path, 
            x_pos, 
            y_pos, 
            width=ziel_breite, 
            height=ziel_hoehe, 
            mask='auto'  # <--- Das zwingt ReportLab, die Transparenz zu erhalten!
        )
    

    
    canvas.restoreState()


def footer_and_header_later(canvas, doc):
    footer(canvas, doc)             # Ruft deinen bestehenden Footer auf
    header_later_pages(canvas, doc) # Ruft den neuen Logo-Header auf

def create_pdf(
    anzahl_verkaufen, max_anteile, bereits_verkauft,
    brutto, gewinn, gewinn_teilfreistellung,
    gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf,
    gewinn_steuerpflichtig, steuer, netto,
    gesamtkosten, vorabpauschale, aktueller_kurs, freibetrag, 
    etf_name, verlusttopf_nach_verkauf, gesamte_vorabpauschale, 
    teilfreistellung_quote, kirchensteuer
):

    aktueller_besitz = max_anteile - bereits_verkauft
    gesamtwert = aktueller_besitz * aktueller_kurs
    durchschnittlicher_kaufpreis = gesamtkosten / max_anteile if max_anteile else 0

    buffer = io.BytesIO()
    
    # 📝 SEITEN-LAYOUT DEFINIEREN (A4 hat 595.27 pt Breite)
    # Nutzen wir 2 cm Ränder (~56 pt) -> Nutzbare Breite = ca. 483 pt
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    # 🎨 FARBPALETTE (Passend zu deinem CSS-Webdesign)
    PRIMARY_COLOR = colors.HexColor("#2563eb")     # Markenblau
    TEXT_DARK = colors.HexColor("#1f2937")         # Dunkelgrau für Text
    TEXT_MUTED = colors.HexColor("#64748b")        # Slate-Grau für Subtexte
    BG_LIGHT = colors.HexColor("#f8fafc")          # Hellgrauer Kachel-Hintergrund
    BG_ZEBRA = colors.HexColor("#f1f5f9")          # Alternierende Tabellenzeilen
    BORDER_COLOR = colors.HexColor("#cbd5e1")      # Saubere Rahmenlinien
    SUCCESS_COLOR = colors.HexColor("#10b981")     # Grün für Netto
    
    # 📑 TYPOGRAFIE STYLES
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=PRIMARY_COLOR,
        alignment=0 # Linksbuendig statt zentriert für modernen Look
    )
    
    h2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=PRIMARY_COLOR,
        spaceBefore=15,
        spaceAfter=8,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=TEXT_DARK
    )
    
    muted_style = ParagraphStyle(
        'CustomMuted',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=TEXT_MUTED
    )

    legal_style = ParagraphStyle(
        'CustomLegal',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique', # Kursiv für rechtliche Hinweise üblich
        fontSize=7.5,                 # Schön klein, damit es nicht dominant ist
        leading=10,
        textColor=colors.HexColor("#94a3b8"), # Sehr dezentes Hellgrau
        spaceBefore=25                # Abstand zur Tabelle darüber
    )

    header_text_style = ParagraphStyle(
        'CustomHeaderSubtitle',
        parent=styles['Normal'], # Wir erben von der Basis
        fontName='Helvetica-Bold',
        fontSize=16,             # Kleiner als die vorherigen 24pt des TitleStyles
        leading=20,              # Zeilenabstand passend zur Schriftgröße
        textColor=TEXT_MUTED     # Nutzt dein definiertes Slate-Grau (#64748b)
    )
    


    elements = []

    current_dir = os.path.dirname(os.path.abspath(__file__))

    logo_path = os.path.join(current_dir, "static", "logo.png") 
    
    # --- FIX FÜR VERZERRUNG: Proportionen automatisch auslesen ---
    img_reader = ImageReader(logo_path)
    img_w, img_h = img_reader.getSize()
    
    # Wir wollen, dass das Logo genau 28pt hoch ist (passend zur Schrifthöhe)
    ziel_hoehe = 50.0
    ziel_breite = (img_w / img_h) * ziel_hoehe # Berechnet die perfekte Breite proportional
    
    logo_img = Image(logo_path, width=ziel_breite, height=ziel_hoehe)
    logo_img.hAlign = 'LEFT'

    header_text = Paragraph(
        ' - Steuerreport',
        header_text_style
    )

    # Wir packen Logo und Text in eine Tabelle, damit sie perfekt nebeneinander stehen
    # Spalte 1: Exakt so breit wie dein berechnetes Logo + 10pt Abstand zum Text
    # Spalte 2: Der Rest der verfügbaren Seitenbreite (483pt gesamt)
    spalten_breiten = [max(30, ziel_breite + 10), 483 - max(30, ziel_breite + 10)]
    
    header_table = Table([[logo_img, header_text]], colWidths=spalten_breiten)
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), # Zentriert Logo und Text vertikal zueinander
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    
    elements.append(header_table)
    
    # Eine feine, elegante Trennlinie unter dem kombinierten Header
    elements.append(Spacer(1, 10))
    line_table = Table([[""]], colWidths=[483])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 1, PRIMARY_COLOR),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(line_table)
    
    elements.append(Spacer(1, 10))



    # elements.append(Paragraph("Steuerreport Ergebnis", title_style))
    # elements.append(Paragraph('<font color="#2563eb"><u>etfsteuerrechner.de</u></font>', muted_style))
    elements.append(Spacer(1, 15))

    # # 2. SEKTION: ÜBERBLICK POSITION
    # elements.append(Paragraph("Überblick Ihrer Position (vor Verkauf)", h2_style))
    elements.append(Paragraph(f"<b>ETF-Name:</b> {etf_name}", body_style))
    elements.append(Paragraph(f"Teilfreistellungsquote: <b>{teilfreistellung_quote * 100:.2f} %</b> &nbsp;&nbsp;|&nbsp;&nbsp; Kirchensteuer: <b>{kirchensteuer}</b>", muted_style))
    # elements.append(Spacer(1, 10))

    # # KPI Kacheln für die Position
    # pos_data = [
    #     [
    #         Paragraph("<b>Anzahl Anteile im Besitz</b>", muted_style),
    #         Paragraph("<b>Kurs bei Verkauf</b>", muted_style),
    #         Paragraph("<b>Gesamtwert der Anteile</b>", muted_style)
    #     ],
    #     [
    #         Paragraph(f"<font size=12><b>{anteil(aktueller_besitz)}</b></font>", body_style),
    #         Paragraph(f"<font size=12><b>{eur(aktueller_kurs)}</b></font>", body_style),
    #         Paragraph(f"<font size=12><b>{eur(gesamtwert)}</b></font>", body_style)
    #     ]
    # ]
    # pos_table = Table(pos_data, colWidths=[161, 161, 161])
    # pos_table.setStyle(TableStyle([
    #     ("BACKGROUND", (0,0), (-1,-1), BG_LIGHT),
    #     ("ALIGN", (0,0), (-1,-1), "CENTER"),
    #     ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    #     ("INNERGRID", (0,0), (-1,-1), 1, BORDER_COLOR),
    #     ("BOX", (0,0), (-1,-1), 1, BORDER_COLOR),
    #     ("TOPPADDING", (0,0), (-1,-1), 10),
    #     ("BOTTOMPADDING", (0,0), (-1,-1), 10),
    # ]))
    # elements.append(pos_table)
    
    # elements.append(Spacer(1, 6))
    # elements.append(Paragraph(f"Gekaufte Anteile gesamt: {anteil(max_anteile)} &nbsp;&nbsp;|&nbsp;&nbsp; Davon bereits verkauft: {anteil(bereits_verkauft)} &nbsp;&nbsp;|&nbsp;&nbsp; Ø-Kaufpreis: {eur(durchschnittlicher_kaufpreis)}", muted_style))
    # elements.append(Spacer(1, 15))

    # 3. SEKTION: VERKAUFSÜBERBLICK (KPI-Style)
    elements.append(Paragraph("Infos über den geplanten Verkauf", h2_style))
    
    verkauf_data = [
        [
            Paragraph("<b>Zu verkaufende Anteile</b>", muted_style),
            Paragraph("<b>Brutto Verkaufserlös</b>", muted_style),
            Paragraph("<b>Netto nach Steuern</b>", muted_style)
        ],
        [
            Paragraph(f"<font size=13><b>{anteil(anzahl_verkaufen)}</b></font>", body_style),
            Paragraph(f"<font size=13><b>{eur(brutto)}</b></font>", body_style),
            Paragraph(f"<font size=13><b>{eur(netto)}</b></font>", body_style)
        ]
    ]
    verkauf_table = Table(verkauf_data, colWidths=[161, 161, 161])
    verkauf_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BG_LIGHT),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("INNERGRID", (0,0), (-1,-1), 1, BORDER_COLOR),
        ("BOX", (0,0), (-1,-1), 1, BORDER_COLOR),
        ("TOPPADDING", (0,0), (-1,-1), 7),    # Von 12 auf 7pt reduziert
        ("BOTTOMPADDING", (0,0), (-1,-1), 7), # Von 12 auf 7pt reduziert
    ]))
    elements.append(verkauf_table)
    
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Reiner Gewinn aus Verkauf: <b>{eur(gewinn)}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Allgemeiner Verlusttopf nach Verkauf: <b>{eur(verlusttopf_nach_verkauf)}</b>", muted_style))
    elements.append(Spacer(1, 15))

    # 4. SEKTION: RECHENSCHAFT / STEUERBERCHNUNG (Klassische, saubere Tabelle)
    elements.append(Paragraph("Detaillierte Steuerberechnung", h2_style))
    

    ungenutzter_freibetrag_wert = freibetrag - (gewinn_nach_verlusttopf - gewinn_steuerpflichtig)

    steuer_data = [
        [Paragraph("<b>Berechnungsschritt</b>", body_style), Paragraph("<b>Wert</b>", body_style)],
        
        # --- Positions-Historie (Anteile) ---
        ["Insgesamt gekaufte Anteile", f"{anteil(max_anteile)}"],
        ["Bereits verkaufte Anteile", f"{anteil(bereits_verkauft)}"],
        ["Anteile aktuell im Besitz", f"{anteil(max_anteile - bereits_verkauft)}"],
        
        # --- Der anstehende Verkauf (Anteile & Kurs) ---
        ["Anzahl zu verkaufender Anteile", f"{anteil(anzahl_verkaufen)}"],
        ["Kurs bei Verkauf", f"{eur(aktueller_kurs)}"],
        
        # --- Erlöse & Kosten ---
        ["Kosten bei Kauf", f"{eur(brutto - gewinn)}"],
        ["Brutto Verkaufserlös", f"{eur(brutto)}"],
        ["Gewinn vor Steuer", f"{eur(gewinn)}"],
        
        # --- Steuerliche Zwischenschritte ---
        ["Abzuziehende Vorabpauschale", f"{eur(gesamte_vorabpauschale)}"],
        ["Gewinn nach Vorabpauschale", f"{eur(gewinn_nach_vorabpauschale)}"],
        ["Gewinn nach Teilfreistellung", f"{eur(gewinn_teilfreistellung)}"],
        ["Gewinn nach Verlusttopf", f"{eur(gewinn_nach_verlusttopf)}"],
        ["Neuer Verlusttopf", f"{eur(verlusttopf_nach_verkauf)}"],
        ["Gewinn nach Sparerpauschbetrag", f"{eur(gewinn_steuerpflichtig)}"],
        ["Ungenutzter Freibetrag", f"{eur(max(0, ungenutzter_freibetrag_wert))}"], # Mit max(0, ...), falls negativ
        
        # --- Finale Steuer & Auszahlung ---
        ["Zu zahlende Steuer", f"{eur(steuer)}"],
        ["Netto", f"{eur(netto)}"],
    ]

    # Gesamtbreite = 483 pt. Links kriegt 343 pt, Rechts 140 pt.
    steuer_table = Table(steuer_data, colWidths=[343, 140])
    
    # Intelligentes Styling-Array aufbauen
    t_style = [
        ("BACKGROUND", (0,0), (-1,0), BG_ZEBRA),     # Header Zeile einfärben
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
        ("TOPPADDING", (0,0), (-1,0), 6),
        ("ALIGN", (1,0), (1,-1), "RIGHT"),            # Rechte Spalte rechtsbündig
        ("LINEBELOW", (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")), # Feine Trennlinien
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 9.5),
        ("TEXTCOLOR", (0,0), (-1,-1), TEXT_DARK),
    ]


    
    # Letzte Zeile (Netto) visuell als "Total" hervorheben
    t_style.extend([
        ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
        ("BACKGROUND", (0,-1), (-1,-1), BG_ZEBRA),
        ("TOPPADDING", (0,-1), (-1,-1), 8),
        ("BOTTOMPADDING", (0,-1), (-1,-1), 8),
    ])
    
    steuer_table.setStyle(TableStyle(t_style))
    elements.append(steuer_table)
    elements.append(Spacer(1, 15))

    # 5. SEKTION: VORABPAUSCHALE HISTORIE
    # 5. SEKTION: VORABPAUSCHALE HISTORIE
    if vorabpauschale is not None and len(vorabpauschale) > 0:
        # KeepTogether verhindert, dass Überschrift und Tabelle getrennt werden
        vp_elements = []
        vp_elements.append(Paragraph("Eingesetzte Vorabpauschalen pro Anteil", h2_style))
        
        vp_data = [[Paragraph("<b>Kalenderjahr</b>", body_style), Paragraph("<b>Vorabpauschale (€ / Anteil)</b>", body_style)]]
        
        for _, row in vorabpauschale.iterrows():
            vp_data.append([
                f"{row['jahr']:.0f}",
                f"{row['wert']:.8f}".replace(".", ",")
            ])

        vp_table = Table(vp_data, colWidths=[150, 200])
        vp_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), BG_ZEBRA),
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
            ("LINEBELOW", (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        vp_elements.append(vp_table)
        elements.append(KeepTogether(vp_elements)) # <--- Import oben: from reportlab.platypus import KeepTogether

    # --- RECHTLICHER HINWEIS (Jetzt AUSSERHALB der If-Bedingung, damit er IMMER erscheint) ---
    disclaimer_text = (
        "<b>Wichtiger Hinweis:</b> Dieser Report dient rein zu Informationszwecken und stellt keine "
        "Steuer- oder Anlageberatung dar. Trotz sorgfältiger Programmierung kann keine Gewähr für die "
        "Richtigkeit, Vollständigkeit oder steuerliche Anerkennung der Ergebnisse übernommen werden. "
        "Die Haftung für finanzielle Verluste oder Steuernachzahlungen ist ausgeschlossen."
    )
    elements.append(Paragraph(disclaimer_text, legal_style))


    # if vorabpauschale is not None and len(vorabpauschale) > 0:
    #     elements.append(Paragraph("Eingesetzte Vorabpauschalen pro Anteil", h2_style))
        
    #     vp_data = [[Paragraph("<b>Kalenderjahr</b>", body_style), Paragraph("<b>Vorabpauschale (€ / Anteil)</b>", body_style)]]
        
    #     for _, row in vorabpauschale.iterrows():
    #         vp_data.append([
    #             f"{row['jahr']:.0f}",
    #             f"{row['wert']:.8f}".replace(".", ",")
    #         ])

    #     vp_table = Table(vp_data, colWidths=[150, 200])
    #     vp_table.setStyle(TableStyle([
    #         ("BACKGROUND", (0,0), (-1,0), BG_ZEBRA),
    #         ("ALIGN", (1,0), (1,-1), "RIGHT"),
    #         ("LINEBELOW", (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
    #         ("FONTSIZE", (0,0), (-1,-1), 9),
    #         ("TOPPADDING", (0,0), (-1,-1), 5),
    #         ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    #     ]))
    #     elements.append(vp_table)


    #     disclaimer_text = (
    #         "<b>Wichtiger Hinweis:</b> Dieser Report dient rein zu Informationszwecken und stellt keine "
    #         "Steuer- oder Anlageberatung dar. Trotz sorgfältiger Programmierung kann keine Gewähr für die "
    #         "Richtigkeit, Vollständigkeit oder steuerliche Anerkennung der Ergebnisse übernommen werden. "
    #         "Die Haftung für finanzielle Verluste oder Steuernachzahlungen ist ausgeschlossen."
    #     )
    #     elements.append(Paragraph(disclaimer_text, legal_style))


    # PDF Dokument bauen
    # doc.build(
    #     elements,
    #     onFirstPage=footer,
    #     onLaterPages=footer
    # )
    doc.build(
        elements,
        onFirstPage=footer,                  # Seite 1: Nur der Footer
        onLaterPages=footer_and_header_later # Ab Seite 2: Footer + Logo oben rechts
    )

    buffer.seek(0)
    return buffer

# logo einbauen