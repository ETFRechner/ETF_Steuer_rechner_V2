from datetime import datetime
import numpy as np
import pandas as pd
# Importiere dein Modell aus deiner models.py
from models import CalculationPayload 
import requests
import yfinance as yf
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import TableStyle
import io

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
    gewinn, brutto, gesamte_vorabpauschale = bestimme_steuer(
        high, aktueller_kurs, data, vorabpauschale, bereits_verkauft, tagesgenau = tagesgeanue_berechnung
    )

    steuerpflichtiger_gewinn = bestimme_steuerpflichtigen_gewinn(
        gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag
    )

    for _ in range(100):
        print(f"low: {low}, high: {high}")

        mid = (low + high) / 2

        gewinn, brutto, gesamte_vorabpauschale = bestimme_steuer(
            mid, aktueller_kurs, data, vorabpauschale, bereits_verkauft, tagesgenau = tagesgeanue_berechnung
        )

        # print(f"Gewinn: {gewinn}, Brutto: {brutto}, gesamte Vorabpauschale: {gesamte_vorabpauschale}")

        steuerpflichtiger_gewinn = bestimme_steuerpflichtigen_gewinn(
            gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag
        )
        # print(steuerpflichtiger_gewinn)

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
    print(f"cum_shares: {cum_shares}, anzahl_verkaufen: {anzahl_verkaufen}")

    if cum_shares[-1] < anzahl_verkaufen - 1e-9:
        print("Sie verfügen nicht über ausreichend Anteile für das gewünschte Netto.")

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

    # print(teilfreistellung_quote)
    print(f"Gewinn: {gewinn}")
    print(f"Gesamte Vorabpauschale: {gesamte_vorabpauschale}")
    print(f"Gewinn nach Vorabpauschale: {gewinn_nach_vorabpauschale}")
    print(f"Gewinn nach Teilfreistellung: {gewinn_teilfreistellung}")
    print(f"Gewinn nach Verlusttopf: {gewinn_nach_verlusttopf}")
    print(f"Steuerpflichtiger Gewinn: {gewinn_steuerpflichtig}")
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

    print(aktueller_kurs)
    print(anzahl_verkaufen)
    print(brutto)


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

    canvas.setFont("Helvetica", 9)

    text = "Berechnet mit etfsteuerrechner.de – Angaben ohne Gewähr."
    x = 2 * cm
    y = 1.5 * cm

    canvas.drawString(x, y, text)

    canvas.linkURL(
        "https://www.etfsteuerrechner.de",
        (x, y, x + 200, y + 10),
        relative=0
    )

    canvas.restoreState()



def create_pdf(
    anzahl_verkaufen, max_anteile, bereits_verkauft,
    brutto, gewinn, gewinn_teilfreistellung,
    gewinn_nach_vorabpauschale, gewinn_nach_verlusttopf,
    gewinn_steuerpflichtig, steuer, netto,
    gesamtkosten, vorabpauschale, aktueller_kurs, freibetrag, 
    etf_name, verlusttopf_nach_verkauf, gesamte_vorabpauschale, 
    teilfreistellung_quote, kirchensteuer
):
    print("Erstelle PDF...")

    aktueller_besitz = max_anteile - bereits_verkauft
    gesamtwert = aktueller_besitz * aktueller_kurs
    durchschnittlicher_kaufpreis = gesamtkosten / max_anteile if max_anteile else 0

    buffer = io.BytesIO()

    styles = getSampleStyleSheet()
    elements = []

    elements.append(
        Paragraph(
            '<link href="https://www.etfsteuerrechner.de">etfsteuerrechner.de</link> – Ergebnis',
            styles["Title"]
        )
    )

    elements.append(Spacer(1, 20))

    # ---------------------------------------------------
    # Überblick Position
    # ---------------------------------------------------

    elements.append(Paragraph("Überblick Ihrer Position (vor Verkauf)", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(f"<b>ETF:</b> {etf_name}", styles["Normal"]))

    elements.append(
        Paragraph(
            f"<font size=9>"
            f"Teilfreistellungsquote: <b>{teilfreistellung_quote * 100:.2f} %</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Kirchensteuer: <b>{kirchensteuer}</b>"
            f"</font>",
            styles["Normal"]
        )
    )


    elements.append(Spacer(1, 6))

    ergebnis_data = [
        [
            "Anzahl Anteile im Besitz",
            "Kurs bei Verkauf",
            "Gesamtwert der Anteile"
        ],
        [
            f"{anteil(aktueller_besitz)}",
            f"{eur(aktueller_kurs)}",
            f"{eur(gesamtwert)}"
        ]
    ]

    ergebnis_table = Table(ergebnis_data)

    ergebnis_table.setStyle(TableStyle([
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0,0), (-1,0), 8),
    ]))

    elements.append(ergebnis_table)
    elements.append(Spacer(1, 8))

    # Zusatzinfos
    elements.append(
        Paragraph(
            f"<font size=9>"
            f"Gekaufet Anteile: <b>{anteil(max_anteile)}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Davon verkauft: <b>{anteil(bereits_verkauft)}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Durchschnittlicher Kaufpreis: <b>{eur(durchschnittlicher_kaufpreis)}</b>"
            f"</font>",
            styles["Normal"]
        )
    )

    elements.append(Spacer(1, 20))

    # ---------------------------------------------------
    # Verkaufsübersicht
    # ---------------------------------------------------

    elements.append(Paragraph("Infos über Verkauf", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    verkauf_data = [
        [
            "Anzahl zu verkaufender Anteile",
            "Brutto Verkaufserlös",
            "Netto nach Steuern"
        ],
        [
            f"{anteil(anzahl_verkaufen)}",
            f"{eur(brutto)}",
            f"{eur(netto)}"
        ]
    ]

    verkauf_table = Table(verkauf_data)

    verkauf_table.setStyle(TableStyle([
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0,0), (-1,0), 8),
    ]))

    elements.append(verkauf_table)
    elements.append(Spacer(1, 12))

    # Zusatzinfos Verkauf
    elements.append(
        Paragraph(
            f"<font size=9>"
            f"Gewinn aus Verkauf: <b>{eur(gewinn)}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Ungenutzter Sparerpauschbetrag: <b>{eur(max(0, freibetrag - gewinn_nach_verlusttopf))}</b>"
            f"</font>",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"<font size=9>"
            f"Allgemeiner Verlusttopf nach Verkauf: <b>{eur(verlusttopf_nach_verkauf)}</b>"
            f"</font>",
            styles["Normal"]
        )
    )


    elements.append(Spacer(1, 20))

    # ---------------------------------------------------
    # Steuerberechnung
    # ---------------------------------------------------

    elements.append(Paragraph("Steuerberechnung", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    steuer_data = [
        ["Berechnungsschritt", "Betrag"],
        ["Anzahl zu verkaufender Anteile", f"{anteil(anzahl_verkaufen)}"],
        ["Kurs bei Verkauf", f"{eur(aktueller_kurs)}"],
        ["Brutto Verkaufserlös", eur(brutto)],
        ["Gewinn vor Steuern", eur(gewinn)],
        ["Abzuziehende Vorabpauschale", eur(gesamte_vorabpauschale)],
        ["Gewinn nach Abzug Vorabpauschale", eur(gewinn_nach_vorabpauschale)],
        ["Gewinn nach Teilfreistellung", eur(gewinn_teilfreistellung)],
        ["Gewinn nach Verlustverrechnung", eur(gewinn_nach_verlusttopf)],
        ["Neuer Verlusttopf", eur(verlusttopf_nach_verkauf)],
        ["Gewinn nach Sparerpauschbetrag", eur(gewinn_steuerpflichtig)],
        ["Ungenutzter Sparerpauschbetrag", eur(max(0, freibetrag - gewinn_nach_verlusttopf))],
        # ["Steuerpflichtiger Gewinn", eur(gewinn_steuerpflichtig)],
        ["Zu zahlende Steuer", eur(steuer)],
        ["Netto nach Steuern", eur(netto)],
    ]

    steuer_table = Table(steuer_data, colWidths=[280,120])

    steuer_table.setStyle(TableStyle([
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),   # ganze Betrag-Spalte rechts
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0,0), (-1,0), 8),
    ]))

    elements.append(steuer_table)
    elements.append(Spacer(1, 10))



    elements.append(Spacer(1, 20))

    # ---------------------------------------------------
    # Vorabpauschale Tabelle
    # ---------------------------------------------------

    if vorabpauschale is not None and len(vorabpauschale) > 0:

        elements.append(Paragraph("Vorabpauschale pro Anteil", styles["Heading2"]))
        elements.append(Spacer(1, 10))

        data = [["Kalenderjahr", "Vorabpauschale pro Anteil"]]

        for _, row in vorabpauschale.iterrows():
            data.append([
                f"{row['jahr']:.0f}",
                f"{row['wert']:.8f}".replace(".", ",")
            ])

        table = Table(data, colWidths=[150,200])

        table.setStyle(TableStyle([
            ("ALIGN", (1,0), (-1,-1), "RIGHT"),   # ganze Betrag-Spalte rechts
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0,0), (-1,0), 8),
        ]))


        elements.append(table)

    doc = SimpleDocTemplate(buffer, pagesize=A4)

    doc.build(
        elements,
        onFirstPage=footer,
        onLaterPages=footer
    )


    buffer.seek(0)

    return buffer


