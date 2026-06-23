from datetime import datetime
import numpy as np


def finde_anteile_ohne_steuer(max_anteile, aktueller_kurs, data, vorabpauschale, bereits_verkauft, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung):

    low = 0.0
    high = float(max_anteile)

    # prüfen ob überhaupt Steuern entstehen
    gewinn, brutto, gesamte_vorabpauschale = bestimme_steuer(
        high, aktueller_kurs, data, vorabpauschale, bereits_verkauft, tagesgenau = tagesgeanue_berechnung
    )

    steuerpflichtiger_gewinn = bestimme_steuerpflichtigen_gewinnn(
        gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag
    )

    for _ in range(100):

        mid = (low + high) / 2

        gewinn, brutto, gesamte_vorabpauschale = bestimme_steuer(
            mid, aktueller_kurs, data, vorabpauschale, bereits_verkauft, tagesgenau = tagesgeanue_berechnung
        )

        steuerpflichtiger_gewinn = bestimme_steuerpflichtigen_gewinnn(
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

    shares = data["Anzahl"].to_numpy(dtype=float)
    prices = data["Preis"].to_numpy(dtype=float)
    dates = pd.to_datetime(data["Kaufdatum"]).to_numpy()

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

    if cum_shares[-1] < anzahl_verkaufen - 1e-9:
        st.warning("Sie verfügen nicht über ausreichend Anteile für das gewünschte Netto.")
        st.stop()

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
        return gewinn, brutto, gesamte_vorabpauschale, 0

    vp_jahre = vorabpauschale["jahr"].to_numpy()
    vp_values = vorabpauschale["vorabpauschale_stueck"].to_numpy()

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



def bestimme_steuerpflichtigen_gewinnn(gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag, all = False):
    gewinn_nach_vorabpauschale = gewinn - gesamte_vorabpauschale
    gewinn_teilfreistellung = gewinn_nach_vorabpauschale * (1 - teilfreistellung_quote)
    gewinn_nach_verlusttopf = max(0, gewinn_teilfreistellung - verlusttopf)
    gewinn_steuerpflichtig = max(0, gewinn_nach_verlusttopf - freibetrag)
    if all:
        return gewinn_nach_vorabpauschale, gewinn_teilfreistellung, gewinn_nach_verlusttopf, gewinn_steuerpflichtig
    else:
        return gewinn_steuerpflichtig



def berechne_steuerfrei(payload):
    return payload  # Hier kannst du die Logik für die Berechnung der steuerfreien Anteile implementieren

    anzahl_verkaufen = finde_anteile_ohne_steuer(max_anteile-bereits_verkauft, aktueller_kurs, data, vorabpauschale, bereits_verkauft, steuersatz, teilfreistellung_quote, verlusttopf, freibetrag, tagesgeanue_berechnung)
    gewinn, brutto, gesamte_vorabpauschale = bestimme_steuer(anzahl_verkaufen, aktueller_kurs, data, vorabpauschale, bereits_verkauft, tagesgenau = tagesgeanue_berechnung)

    gewinn_nach_vorabpauschale, gewinn_teilfreistellung, gewinn_nach_verlusttopf, gewinn_steuerpflichtig = bestimme_steuerpflichtigen_gewinnn(gewinn, teilfreistellung_quote, gesamte_vorabpauschale, verlusttopf, freibetrag, all=True)
    steuer = gewinn_steuerpflichtig * steuersatz
    netto = brutto - steuer

    if gewinn_teilfreistellung < 0:
        verlusttopf_nach_verkauf = verlusttopf - gewinn_teilfreistellung
    else:
        verlusttopf_nach_verkauf = max(0, verlusttopf - gewinn_teilfreistellung)

    return f"Steuerfrei verkaufbar: {anzahl_verkaufen:.6f} Anteile\nNetto nach Steuern: {netto:.2f}€\nVerlusttopf nach Verkauf: {verlusttopf_nach_verkauf:.2f}€"