
function openModal(id) {
  document.getElementById(id).style.display = "block";
}

function closeModal(id) {
  document.getElementById(id).style.display = "none";
}

window.onclick = function(event) {
  let modals = document.getElementsByClassName("modal");
  for (let modal of modals) {
    if (event.target == modal) {
      modal.style.display = "none";
    }
  }
}


// Ermittelt das heutige Datum im Format YYYY-MM-DD
const heute = new Date().toISOString().split('T')[0];

// Beim Laden der Seite direkt 1 leere Zeilen anzeigen, falls keine CSV da ist
window.onload = function() {
    for(let i=0; i<1; i++) {
        fuegeZeileHinzu();
    }
};

function toggleEingabeOptionen() {
    let option = document.getElementById("eingabe_option").value;
    document.getElementById("bereich_manuell").style.display = (option === "manuell") ? "block" : "none";
    document.getElementById("bereich_sparplan").style.display = (option === "sparplan") ? "block" : "none";
    document.getElementById("bereich_csv").style.display = (option === "trade") ? "block" : "none";
}


function loescheZeile(button) {
    // Sauberere Variante, um die Zeile zu löschen
    button.closest("tr").remove();
    if (typeof aktualisiereVorabpauschaleTabelle === "function") {
        aktualisiereVorabpauschaleTabelle();
    }
    aktualisiereTabellenAnsicht();
}

        // ASYNC FUNCTION: Bleibt genau so, da sie jetzt fehlerfreie Daten übergibt!
async function uploadCSV() {
    let fileInput = document.getElementById("csv_file");
    if (fileInput.files.length === 0) return;

    let file = fileInput.files[0];
    let formData = new FormData();
    formData.append("file", file);

    let response = await fetch("/api/upload-csv", {
        method: "POST",
        body: formData
    });

    let result = await response.json();

    if (result.success) {
        document.getElementById("tabelle_body").innerHTML = "";
        result.data.forEach(kauf => {
            // Reicht die Daten jetzt erfolgreich an die korrigierte Funktion weiter
            fuegeZeileHinzu(kauf.datum, kauf.anzahl, kauf.preis);
        });
    
        if (typeof aktualisiereVorabpauschaleTabelle === "function") {
            aktualisiereVorabpauschaleTabelle();
        }

        isTableCollapsed = true; 
        aktualisiereTabellenAnsicht();
    } else {
        alert("Fehler beim Laden der CSV: Die hochgeladene Datei muss die Spalten 'datum', 'anzahl' und 'preis' enthalten.");
    }
    // Feld zurücksetzen, damit man dieselbe Datei erneut hochladen kann
    fileInput.value = "";
}


document.addEventListener("DOMContentLoaded", () => {
    // Beide Dropzones registrieren
    einrichtenDropzone("dropzone", "csv_file", handleFileSelect);
    einrichtenDropzone("dropzone_suche", "csv_file_suche", handleFileSelectSuche);
    einrichtenDropzone("dropzone_tr", "tr_csv_file", handleFileSelectTR);
});

// Allgemeine Hilfsfunktion, um doppelten Code für die Drag & Drop Events zu vermeiden
function einrichtenDropzone(dropzoneId, inputId, selectCallback) {
    const dropzone = document.getElementById(dropzoneId);
    const fileInput = document.getElementById(inputId);

    if (!dropzone || !fileInput) return;

    ["dragenter", "dragover", "dragleave", "drop"].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => e.preventDefault(), false);
    });

    ["dragenter", "dragover"].forEach(eventName => {
        dropzone.addEventListener(eventName, () => dropzone.classList.add("dragover"), false);
    });

    ["dragleave", "drop"].forEach(eventName => {
        dropzone.addEventListener(eventName, () => dropzone.classList.remove("dragover"), false);
    });
        
    dropzone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
    
        if (files.length > 0 && files[0].name.endsWith(".csv")) {
            fileInput.files = files;
            selectCallback(fileInput); // Ruft die jeweilige Funktion auf
        } else {
            alert("Bitte lade eine gültige .csv Datei hoch.");
        }
    });
}

// 🎯 NEU: Hilfsfunktion für die Suche-Dropzone
function handleFileSelectSuche(input) {
    const displaySpan = document.getElementById("file_name_display_suche");
    if (input.files.length > 0) {
        const dateiName = input.files[0].name;
        displaySpan.innerText = `Ausgewählt: ${dateiName}`
        // Startet direkt deine bestehende Upload-Logik für die Suche!
        uploadCSVSuche();
    } else {
        displaySpan.innerText = "Keine Datei ausgewählt";
    }
}

function handleFileSelectTR(input) {
    const displaySpan = document.getElementById("file_name_display_tr");
    if (input.files.length > 0) {
        const dateiName = input.files[0].name;
        displaySpan.innerText = `Ausgewählt: ${dateiName}`;
        // Startet direkt deine bestehende Upload-Logik für Trade Republic!
        uploadTradeRepublicCSV();
    } else {
        displaySpan.innerText = "Keine Datei ausgewählt";
    }
}

function handleFileSelect(input) {
    const displaySpan = document.getElementById("file_name_display");
    if (input.files.length > 0) {
        const dateiName = input.files[0].name;
        displaySpan.innerText = `Ausgewählt: ${dateiName}`;
        displaySpan.style.color = "#2563eb"; // Highlightet den Dateinamen blau

        // 1. Startet deine bestehende Upload-Logik
        uploadCSV();

        // 2. 🎯 REPARIERT: Keine 'kein_etf_auswahl'-Checkbox mehr!
        // Wir ermitteln dynamisch, ob der freie, manuelle Modus ohne ETF aktiv ist
        const sucheInputFeld = document.getElementById('etf_suche_input');
        const symbolAnzeige = document.getElementById('etf_symbol_anzeige')?.innerText || "-";
        const etfBoxSichtbar = document.getElementById('ausgewählter_etf_box').style.display !== 'none';
        const keinEtfGewaehlt = (sucheInputFeld.value.trim() === "" && (!etfBoxSichtbar || symbolAnzeige === "-"));

        // Wenn ein ETF gewählt ist, steuert das Häkchen die Vorabpauschale (sonst ist sie dauerhaft offen)
        if (!keinEtfGewaehlt) {
            toggleVorabpauschale();
        }
    } else {
        displaySpan.innerText = "Keine Datei ausgewählt";
        displaySpan.style.color = "";
    }
    isTableCollapsed = true; // Nach Upload standardmäßig einklappen
    if (typeof aktualisiereTabellenAnsicht === "function") {
        aktualisiereTabellenAnsicht();
    }
}

function aktualisiereVorabpauschaleTabelle() {
    let datumsFelder = document.querySelectorAll(".row-datum");
    let MindestJahr = 2018; 
    let aktuellesJahr = new Date().getFullYear(); // 2026
    let aeltestesJahr = aktuellesJahr;

    // 1. Finde das älteste eingetragene Kaufdatum
    datumsFelder.forEach(feld => {
        if (feld.value) {
            let kaufJahr = new Date(feld.value).getFullYear();
            if (kaufJahr < aeltestesJahr) {
                aeltestesJahr = kaufJahr;
            }
        }
    });

    if (aeltestesJahr < MindestJahr) {
        aeltestesJahr = MindestJahr;
    }

    let vorabBereich = document.getElementById("bereich_vorabpauschale");
    let tbody = document.getElementById("vorab_tabelle_body");
    if (!tbody) return;
    
    tbody.innerHTML = ""; // Vorherige Zeilen löschen

    // 2. Schleife von ältestem Jahr bis zum Vorjahr des aktuellen Jahres (Befüllen)
    if (aeltestesJahr < aktuellesJahr) {
        for (let jahr = aeltestesJahr; jahr < aktuellesJahr; jahr++) {
            let row = tbody.insertRow();
            row.innerHTML = `
                <td><input type="number" class="vorab-jahr" value="${jahr}" disabled ></td>
                <td><input type="number" class="vorab-wert" value="0.00000000" step="0.00000001" min="0"></td>
            `;
        }

        // 3. 🎯 SAUBERE SICHTBARKEITS-LOGIK: Wann darf die Tabelle zu sehen sein?
        const symbolAnzeige = document.getElementById('etf_symbol_anzeige')?.innerText || "-";
        const etfBoxSichtbar = document.getElementById('ausgewählter_etf_box').style.display !== 'none';
        const etfWurdeAusgewaehlt = (etfBoxSichtbar && symbolAnzeige !== "-");
        
        const hakenManuellAktiv = document.getElementById('haken_vorabpauschale')?.checked || false;

        if (!etfWurdeAusgewaehlt || hakenManuellAktiv) {
            if (vorabBereich) vorabBereich.style.display = "block";
        } else {
            if (vorabBereich) vorabBereich.style.display = "none";
        }

    } else {
        if (vorabBereich) vorabBereich.style.display = "none"; // Ausblenden, wenn alles im aktuellen Jahr gekauft wurde
    }
}


function toggleRechenZielFelder() {
    let ziel = document.getElementById("rechen_ziel").value;
    let fNetto = document.getElementById("feld_wunschnetto");
    let fAnteile = document.getElementById("feld_anteile");

    fNetto.style.display = (ziel === "wunschnetto") ? "block" : "none";
    fAnteile.style.display = (ziel === "steuer_berechnen") ? "block" : "none";
}


async function sendeBerechnung() {
    // --- VALIDIERUNG VOR DEM ABSENDEN ---
    versteckeHinweis(); // Alte Meldungen löschen
    // 1. Daten aus der Kaufhistorie-Tabelle auslesen
    let kaeufe = [];
    let kaufZeilen = document.querySelectorAll("#tabelle_body tr");
    kaufZeilen.forEach(zeile => {
        let datum = zeile.querySelector(".row-datum")?.value;
        let anzahl = parseFloat(zeile.querySelector(".row-anzahl")?.value);
        let preis = parseFloat(zeile.querySelector(".row-preis")?.value);
    
        // Nur hinzufügen, wenn die Zeile vollständig ausgefüllt ist
        if (datum && !isNaN(anzahl) && !isNaN(preis)) {
            kaeufe.push({ datum: datum, anzahl: anzahl, preis: preis });
        }
    });

    // 2. Daten aus der Vorabpauschale-Tabelle auslesen
    let vorabpauschalen = [];
    let vorabZeilen = document.querySelectorAll("#vorab_tabelle_body tr");
    vorabZeilen.forEach(zeile => {
        let jahrField = zeile.querySelector(".vorab-jahr");
        let wertField = zeile.querySelector(".vorab-wert");
        if (jahrField && wertField) {
            let jahr = parseInt(jahrField.value);
            let wert = parseFloat(wertField.value);
            if (!isNaN(jahr) && !isNaN(wert)) {
                vorabpauschalen.push({ jahr: jahr, wert: wert });
            }
        }
    });


    // Prüfen, ob ein valider Ticker existiert. Wenn dort "-" steht oder die Box versteckt ist, ist es null.
    let etfBoxSichtbar = document.getElementById("ausgewählter_etf_box").style.display !== "none";
    let aktuellerTicker = etfBoxSichtbar ? document.getElementById("etf_symbol_anzeige")?.innerText : null;
    if (aktuellerTicker === "-") aktuellerTicker = null;

    // 3. Das gesamte Daten-Paket (Payload) schnüren
    let payload = {
        rechen_ziel: document.getElementById("rechen_ziel").value,
        wert_wunschnetto: parseFloat(document.getElementById("wert_wunschnetto").value) || 0,
        wert_anteile: parseFloat(document.getElementById("wert_anteile").value) || 0,
        verkaufskurs: parseFloat(document.getElementById("verkaufskurs").value),
        freibetrag: parseFloat(document.getElementById("freibetrag").value),
        verlusttopf: parseFloat(document.getElementById("verlusttopf").value),
        kirchensteuer: document.getElementById("kirchensteuer").value,
        tagesgenau: (document.getElementById("tagesgenau").value === "true"),
        
        // 🎯 AUTOMATISIERTE LOGIK: Wenn kein Ticker existiert, IST die manuelle Vorabpauschale automatisch aktiv (true)!
        manuelle_vorabpauschale_aktiv: aktuellerTicker ? document.getElementById("haken_vorabpauschale").checked : true,
        
        kaeufe: kaeufe,
        vorabpauschalen: vorabpauschalen,
        teilfreistellung: parseFloat(document.getElementById("teilfreistellung").value),
        ist_thesaurierend: (document.getElementById("ertragsverwendung").value === "thesaurierend"),
        bereits_verkaufte_anteile: parseFloat(document.getElementById("bereits_verkauft_manuell").value) || 0,
        quelle: "manuell",
        ticker: aktuellerTicker
    };

    // --- FRONTEND-VALIDIERUNGEN ---
    // 🛑 KRITISCHER FEHLER: Verkaufskurs fehlt oder ist <= 0
    if (!payload.verkaufskurs || payload.verkaufskurs <= 0) {
        zeigeHinweis("🛑 Berechnung gestoppt: Der Verkaufskurs muss größer als 0 sein!", "error");
        return; 
    }

    // 🛑 KRITISCHER FEHLER: Keine Käufe eingetragen
    if (payload.kaeufe.length === 0) {
        zeigeHinweis("🛑 Berechnung gestoppt: Bitte tragen Sie mindestens eine Kaufhistorie-Zeile ein!", "error");
        return; 
    }

    // 🛑 KRITISCHER FEHLER: Wunschnetto gewählt, aber Betrag ist 0
    if (payload.rechen_ziel === "wunschnetto" && payload.wert_wunschnetto <= 0) {
        zeigeHinweis("🛑 Berechnung gestoppt: Für das Rechenziel 'Wunschnetto' muss ein Betrag größer als 0 eingegeben werden!", "error");
        return;
    }

    // ⚠️ WARNUNG: Verlusttopf unrealistisch hoch (wir rechnen weiter)
    if (payload.verlusttopf > 50000) {
        zeigeHinweis("⚠️ Hinweis: Der eingegebene Verlusttopf ist sehr hoch. Die Berechnung läuft normal weiter.", "warning");
    }
    // --- VALIDIERUNG ENDE ---

    try {
        // 4. Per POST an FastAPI senden
        let response = await fetch("/api/calculate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
    
        let result = await response.json();
    
        // 5. Ergebnis schön visualisieren
        if (result.success) {
            // Render die KPIs und Tabellen im Frontend
            zeigeErgebnisseImFrontend(result, payload.rechen_ziel);
            // 🎯 NEU: Prüfen, ob das Backend unkritische Warnungen mitgeliefert hat
            if (result.warnings && result.warnings.length > 0) {
                let warnText = "⚠️ " + result.warnings.join("\n⚠️ ");
                zeigeHinweis(warnText, "warning"); 
            } else {
                // Wenn alles glatt lief und keine Frontend-Warnung aktiv war, Box schließen
                if (payload.verlusttopf <= 50000) {
                    versteckeHinweis();
                }
            }
        
            // Optionale alte Textbox aktualisieren (falls noch verwendet)
            if (document.getElementById("rechen_ergebnis_suche")) {
                document.getElementById("rechen_ergebnis_suche").style.display = "block";
                document.getElementById("ergebnis_text_suche").innerHTML = `<pre>Berechnung erfolgreich!</pre>`;
            }
        } else {
            // 🎯 KORRIGIERT: Kritische Fehler aus dem Backend elegant anzeigen (kein alert mehr)
            console.error("Kompletter Backend-Fehler:", result);
            let fehlerText = result.error || result.detail || "Ein unerwarteter Fehler ist aufgetreten.";
            zeigeHinweis("🛑 " + fehlerText, "error");
        }
    
    } catch (error) {
        console.error("Netzwerkfehler beim Senden:", error);
        zeigeHinweis("💥 Netzwerkfehler: Der Server antwortet nicht oder sendet fehlerhafte Daten.", "error");
    }
}

async function liveSuche(suchbegriff, modus = 'manuell') {
    // Bestimmt die ID dynamisch je nach Modus ('manuell' oder 'sparplan')
    const suffix = modus === 'sparplan' ? '_sparplan' : '';
    let ergebnisDiv = document.getElementById("such_ergebnisse" + suffix);

    // 🎯 Wenn das Feld leer ist oder weniger als 2 Zeichen hat -> Alles zurücksetzen!
    if (!suchbegriff || suchbegriff.trim().length < 2) {
        if (ergebnisDiv) {
            ergebnisDiv.innerHTML = "";
            ergebnisDiv.style.display = "none";
        }

        // 🎯 Blendet die jeweilige Warnbox aus, wenn das Feld geleert wird
        let aktuelleWarnung = document.getElementById("etf_suche_warnung" + suffix);
        if (aktuelleWarnung) aktuelleWarnung.style.display = "none";

        // Wenn wir im manuellen Modus sind, setzen wir die manuelle Box zurück
        if (modus === 'manuell') {
            let etfBox = document.getElementById("ausgewählter_etf_box");
            if (etfBox) etfBox.style.display = "none";
            
            let symbolAnzeige = document.getElementById("etf_symbol_anzeige");
            if (symbolAnzeige) symbolAnzeige.innerText = "-";
            
            let nameAnzeige = document.getElementById("etf_name_anzeige");
            if (nameAnzeige) nameAnzeige.innerText = "-";

            // Schaltet das Layout sofort wieder in den freien, manuellen Modus um
            aktualisiereManuelleAnsicht();
        } 
        // 🎯 NEU: Wenn wir im Sparplan-Modus sind, setzen wir die Sparplan-Box zurück
        else if (modus === 'sparplan') {
            let etfBoxSparplan = document.getElementById("ausgewählter_etf_box_sparplan");
            if (etfBoxSparplan) etfBoxSparplan.style.display = "none";
            
            let symbolAnzeigeSparplan = document.getElementById("etf_symbol_anzeige_sparplan");
            if (symbolAnzeigeSparplan) symbolAnzeigeSparplan.innerText = "-";
            
            let nameAnzeigeSparplan = document.getElementById("etf_name_anzeige_sparplan");
            if (nameAnzeigeSparplan) nameAnzeigeSparplan.innerText = "-";

            // Schaltet das Layout sofort wieder in den freien Sparplan-Modus um
            aktualisiereSparplanAnsicht();
        }
        return;
    }

    // --- INTERNET-ABFRAGE DER LIVE-SUCHE ---
    let response = await fetch(`/api/search?q=${encodeURIComponent(suchbegriff)}`);
    let treffer = await response.json();

    if (ergebnisDiv) {
        ergebnisDiv.innerHTML = "";
    }

    if (treffer && treffer.length > 0 && !treffer.error) {
        if (ergebnisDiv) ergebnisDiv.style.display = "block";
    
        treffer.forEach(item => {
            let eintrag = document.createElement("div");
            eintrag.className = "search-suggestion";
            eintrag.innerText = `${item.name} (${item.symbol})`;
        
            // Wir übergeben den Modus an die waehleETF-Funktion weiter!
            eintrag.onclick = () => waehleETF(item.name, item.symbol, modus);
        
            if (ergebnisDiv) ergebnisDiv.appendChild(eintrag);
        });
    } else {
        if (ergebnisDiv) ergebnisDiv.style.display = "none";
    }

    // 🎯 NEU: Am Ende delegieren wir die Ansichts- und Warnungssteuerung an das jeweilige System
    if (modus === 'sparplan') {
        aktualisiereSparplanAnsicht();
    } else if (modus === 'manuell') {
        aktualisiereManuelleAnsicht();
    }
}

function waehleETF(name, symbol, modus = 'manuell') {
    console.log("🎯 waehleETF wurde aufgerufen! Ticker:", symbol);
    console.log("Suffix-Check:", modus === 'sparplan' ? '_sparplan' : '');
    console.log("Gibt es Suchergebnisse?", document.getElementById("such_ergebnisse" + (modus === 'sparplan' ? '_sparplan' : '')));
    console.log("Gibt es Inputfeld?", document.getElementById("etf_suche_input" + (modus === 'sparplan' ? '_sparplan' : '')));
    console.log("Gibt es globalen Namen?", document.getElementById("etf_name_anzeige"));
    console.log("Gibt es globales Symbol?", document.getElementById("etf_symbol_anzeige"));
    console.log("Gibt es globale Box?", document.getElementById("ausgewählter_etf_box"));

    const suffix = modus === 'sparplan' ? '_sparplan' : '';

    // 1. Ergebnisse schließen und Input-Feld befüllen
    const suchErgebnisDiv = document.getElementById("such_ergebnisse" + suffix);
    if (suchErgebnisDiv) suchErgebnisDiv.style.display = "none";
    
    const suchInput = document.getElementById("etf_suche_input" + suffix);
    if (suchInput) suchInput.value = `${name} (${symbol})`;

    // 2. Im manuellen Modus die globalen Box-Werte setzen und Box AKTIVIEREN
    if (modus === 'manuell') {
        const globalName = document.getElementById("etf_name_anzeige");
        const globalSymbol = document.getElementById("etf_symbol_anzeige");
        const globalBox = document.getElementById("ausgewählter_etf_box");

        if (globalName) globalName.innerText = name;
        if (globalSymbol) globalSymbol.innerText = symbol;
        if (globalBox) globalBox.style.display = "block"; // Zwingend auf block für die UI-Logik!

        // 🎯 SOFORT DIE ANSICHT AKTUALISIEREN (Damit die Tabelle sofort einklappt)
        console.log("🔄 Schalte Ansicht auf ETF-Modus um...");
        aktualisiereManuelleAnsicht();
    }

    if (modus === 'sparplan') {
        const sparplanName = document.getElementById("etf_name_anzeige_sparplan");
        const sparplanSymbol = document.getElementById("etf_symbol_anzeige_sparplan");
        const sparplanBox = document.getElementById("ausgewählter_etf_box_sparplan");

        if (sparplanName) sparplanName.innerText = name;
        if (sparplanSymbol) sparplanSymbol.innerText = symbol;
        if (sparplanBox) sparplanBox.style.display = "block"; // Auf block setzen für die Logik!

        // 🎯 Ansicht für den Sparplan triggern
        aktualisiereSparplanAnsicht();
    }

    // 3. Den aktuellen Kurs laden (wird fehlerisoliert danach ausgeführt)
    if (typeof ladeAktuellenKurs === "function") {
        try {
            ladeAktuellenKurs(symbol, modus);
        } catch (error) {
            console.error("Fehler beim Kursladen, Berechnung läuft aber weiter:", error);
        }
    }

    // Sparplan-Warnung ausblenden
    let sparplanWarnung = document.getElementById("etf_suche_warnung_sparplan");
    if (sparplanWarnung) sparplanWarnung.style.display = "none";
}


async function ladeAktuellenKurs(symbol, modus = 'manuell') {
    // Dynamische IDs basierend auf dem Modus wählen
    const kursFeldId = modus === 'sparplan' ? 'verkaufskurs_sparplan' : 'verkaufskurs';
    const statusId = modus === 'sparplan' ? 'kurs_lade_status_sparplan' : 'kurs_lade_status';

    let statusSpan = document.getElementById(statusId);
    let kursInput = document.getElementById(kursFeldId);

    // Falls das Status-Element im HTML existiert, Farbe setzen
    if (statusSpan) {
        statusSpan.style.color = "#666";
    }

    try {
        // Abfrage an deinen FastAPI-Endpunkt
        let response = await fetch(`/api/get-price?symbol=${encodeURIComponent(symbol)}`);
        let result = await response.json();
    
        if (result.success) {
            // Wert in das richtige Input-Feld eintragen
            kursInput.value = result.price;
            if (statusSpan) statusSpan.style.color = "#28a745";
        } else {
            if (statusSpan) statusSpan.style.color = "#dc3545";
        }
    } catch (e) {
        if (statusSpan) statusSpan.style.color = "#dc3545";
    }
}

let alterOnload = window.onload;
window.onload = function() {
    if (alterOnload) alterOnload();
    // 1. Dynamische Default-Daten für den Sparplan berechnen (Letzte 12 Monate)
    let heute = new Date();
    let vorEinemJahr = new Date();
    vorEinemJahr.setFullYear(heute.getFullYear() - 1);
    // Hilfsfunktion zur Formatierung auf YYYY-MM-DD
    let formatiertesDatum = (dateObj) => {
        let j = dateObj.getFullYear();
        let m = String(dateObj.getMonth() + 1).padStart(2, '0');
        let t = String(dateObj.getDate()).padStart(2, '0');
        return `${j}-${m}-${t}`;
    };
    // Felder befüllen, falls sie auf der Seite existieren
    if (document.getElementById("sparplan_start")) {
        document.getElementById("sparplan_start").value = formatiertesDatum(vorEinemJahr);
    }
    if (document.getElementById("sparplan_ende")) {
        document.getElementById("sparplan_ende").value = formatiertesDatum(heute);
    }
    // 2. Leere Zeile NUR einfügen, wenn der manuelle Pfad gewählt ist
    let kaufOption = document.getElementById("suche_kauf_option")?.value;
    if (kaufOption === "suche_manuell") {
        fuegeZeileHinzuSuche();
    }
    aktualisiereManuelleAnsicht();
};


async function generiereSparplan() {
    // 1. IDs angepasst: Holt das Symbol jetzt aus der Sparplan-Suchbox
    let symbol = document.getElementById("etf_symbol_anzeige_sparplan").innerText;
    if (symbol === "-") {
        alert("Bitte wählen Sie zuerst einen ETF über die Suche aus!");
        return;
    }

    // 2. IDs angepasst: Liest die Parameter aus den Sparplan-Feldern aus
    let payload = {
        symbol: symbol,
        start_date: document.getElementById("sparplan_start").value,
        end_date: document.getElementById("sparplan_ende").value,
        tag: parseInt(document.getElementById("sparplan_tag").value),
        rate: parseFloat(document.getElementById("sparplan_rate").value)
    };

    let response = await fetch("/api/generate-sparplan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

    let result = await response.json();

    if (result.success) {
        // Zuerst die Sparplan-Tabelle leeren, damit alte Generierungen überschrieben werden (optional)
        // document.getElementById("sparplan_tabelle_body").innerHTML = "";

        // 3. Funktion angepasst: Schreibt die Käufe in die Sparplan-Tabelle
        result.data.forEach(kauf => {
            fuegeZeileHinzuSparplan(kauf.datum, kauf.anzahl, kauf.preis);
        });
        
        // 4. Funktion angepasst: Aktualisiert die Vorabpauschalen-Jahre für den Sparplan
        if (typeof aktualisiereVorabpauschaleTabelleSparplan === "function") {
            aktualisiereVorabpauschaleTabelleSparplan();
        }
        
        alert(`${result.data.length} Sparplan-Käufe erfolgreich der Tabelle unten hinzugefügt!`);
    } else {
        alert("Fehler bei Sparplan-Generierung: " + result.error);
    }

    // 🎯 KORREKTUR: Prüft nun sauber, ob das Ergebnis-Array leer ist oder existiert, statt nach der toten Variable 'datum' zu suchen
    if (!result.data || result.data.length === 0) { 
        isSparplanTableCollapsed = false; 
    }
    
    if (typeof aktualisiereTabellenAnsichtSparplan === "function") {
        aktualisiereTabellenAnsichtSparplan();
    }
}


// 4. AKTUALISIERT: Generiert eine CSV-Datei direkt aus der aktuell aktiven Tabelle
function downloadCSVFromTable() {
    // 1. Herausfinden, welche Option ausgewählt ist
    const eingabeOption = document.getElementById("eingabe_option");
    let istSuche = (eingabeOption && eingabeOption.value === "suche");

    // Den richtigen Tabellen-Body ansteuern
    let selector = istSuche ? "#suche_tabelle_body_manuell tr" : "#tabelle_body tr";
    let kaufZeilen = document.querySelectorAll(selector);
    if(kaufZeilen.length === 0) {
        alert("Die Tabelle ist leer. Es gibt nichts herunterzuladen.");
        return;
    }

    // Für deutsche Excel-Versionen nutzen wir ein Semikolon (;) als Trennzeichen
    let csvContent = "data:text/csv;charset=utf-8,Kaufdatum;Anzahl;Preis\n";

    kaufZeilen.forEach(zeile => {
        // Holt alle Input-Felder der aktuellen Zeile (0 = Datum, 1 = Anzahl, 2 = Preis)
        let inputs = zeile.querySelectorAll("input");
        if(inputs.length >= 3) {
            let datum = inputs[0].value;
            let anzahl = inputs[1].value;
            let preis = inputs[2].value;
        
            if(datum || anzahl || preis) {
                csvContent += `${datum};${anzahl};${preis}\n`;
            }
        }
    });

    // Erzeuge einen unsichtbaren Download-Link und klicke ihn via JS an
    let encodedUri = encodeURI(csvContent);
    let link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    // Dynamischer Dateiname je nachdem, welche Tabelle exportiert wurde
    let dateiName = istSuche ? "etf_kaufhistorie_suche.csv" : "etf_kaufhistorie_manuell.csv";
    link.setAttribute("download", dateiName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}


async function sendeBerechnungSparplan() {
    versteckeHinweis(); // Alte Meldungen direkt zu Beginn löschen

    // 1. Prüfen, ob ein ETF für den Sparplan gewählt wurde
    let symbol = document.getElementById("etf_symbol_anzeige_sparplan")?.innerText;
    if (!symbol || symbol === "-") {
        zeigeHinweis("🛑 Bitte wählen Sie zuerst einen gültigen ETF über die Suche aus! Probieren Sie die ISIN oder den Ticker, falls Ihr ETF nicht über den Namen gefunden wird. Ansonsten nutzen Sie bitte die manuelle Eingabe.", "error");
        return;
    }

    // 2. Daten aus der Sparplan-Kaufhistorie auslesen
    let kaeufe = [];
    let kaufZeilen = document.querySelectorAll("#sparplan_tabelle_body tr");
    kaufZeilen.forEach(zeile => {
        let datum = zeile.querySelector(".row-datum-sparplan")?.value;
        let anzahl = parseFloat(zeile.querySelector(".row-anzahl-sparplan")?.value);
        let preis = parseFloat(zeile.querySelector(".row-preis-sparplan")?.value);
    
        if (datum && !isNaN(anzahl) && !isNaN(preis)) {
            kaeufe.push({ datum: datum, anzahl: anzahl, preis: preis });
        }
    });

    // 3. Daten aus der Sparplan-Vorabpauschale auslesen (nur wenn Haken gesetzt)
    let vorabpauschalen = [];
    if (document.getElementById("haken_vorabpauschale_sparplan").checked) {
        let vorabZeilen = document.querySelectorAll("#vorab_tabelle_body_sparplan tr");
        vorabZeilen.forEach(zeile => {
            let jahrField = zeile.querySelector(".vorab-jahr-sparplan");
            let wertField = zeile.querySelector(".vorab-wert-sparplan");
        
            if (jahrField && wertField) {
                let jahr = parseInt(jahrField.value);
                let wert = parseFloat(wertField.value);
                if (!isNaN(jahr) && !isNaN(wert)) {
                    vorabpauschalen.push({ jahr: jahr, wert: wert });
                }
            }
        });
    }

    // 4. Das Daten-Paket (Payload) für den Sparplan schnüren
    let payload = {
        rechen_ziel: document.getElementById("rechen_ziel_sparplan").value,
        wert_wunschnetto: parseFloat(document.getElementById("wert_wunschnetto_sparplan").value) || 0,
        wert_anteile: parseFloat(document.getElementById("wert_anteile_sparplan").value) || 0,
        verkaufskurs: parseFloat(document.getElementById("verkaufskurs_sparplan").value),
        freibetrag: parseFloat(document.getElementById("freibetrag").value) || 0,       
        verlusttopf: parseFloat(document.getElementById("verlusttopf").value) || 0,     
        kirchensteuer: document.getElementById("kirchensteuer").value,             
        tagesgenau: (document.getElementById("tagesgenau_sparplan").value === "true"),
        
        // 🎯 KORREKTUR: Jetzt wird das Sparplan-Häkchen abgefragt!
        manuelle_vorabpauschale_aktiv: document.getElementById("haken_vorabpauschale_sparplan").checked,
        
        kaeufe: kaeufe,
        vorabpauschalen: vorabpauschalen,
        teilfreistellung: parseFloat(document.getElementById("teilfreistellung").value) || 0,
        ist_thesaurierend: (document.getElementById("ertragsverwendung").value === "thesaurierend"),
        bereits_verkaufte_anteile: parseFloat(document.getElementById("bereits_verkauft_sparplan").value) || 0,
        ticker: symbol,
        quelle: "sparplan" // Kennzeichnung für dein Backend
    };

    // --- FRONTEND-VALIDIERUNGEN ---
    if (!payload.verkaufskurs || payload.verkaufskurs <= 0) {
        zeigeHinweis("🛑 Berechnung gestoppt: Der Verkaufskurs muss größer als 0 sein!", "error");
        return; 
    }

    if (!payload.kaeufe || payload.kaeufe.length === 0) {
        zeigeHinweis("🛑 Berechnung gestoppt: Bitte generieren oder tragen Sie mindestens eine Kaufhistorie-Zeile ein!", "error");
        return; 
    }

    if (payload.rechen_ziel === "wunschnetto" && payload.wert_wunschnetto <= 0) {
        zeigeHinweis("🛑 Berechnung gestoppt: Für das Rechenziel 'Wunschnetto' muss ein Betrag größer als 0 eingegeben werden!", "error");
        return;
    }

    if (payload.verlusttopf > 50000) {
        zeigeHinweis("⚠️ Hinweis: Der eingegebene Verlusttopf ist sehr hoch. Die Berechnung läuft normal weiter.", "warning");
    }

    try {
        // 5. Per POST an den FastAPI-Endpunkt senden
        let response = await fetch("/api/calculate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
    
        let result = await response.json();
    
        // 6. Ergebnis im Dashboard visualisieren
        if (result.success) {
            zeigeErgebnisseImFrontend(result, payload.rechen_ziel);

            if (result.warnings && result.warnings.length > 0) {
                let warnText = "⚠️ " + result.warnings.join("\n⚠️ ");
                zeigeHinweis(warnText, "warning"); 
            } else {
                if (payload.verlusttopf <= 50000) {
                    versteckeHinweis();
                }
            }
        } else {
            console.error("Kompletter Backend-Fehler:", result);
            let fehlerText = result.error || result.detail || "Ein unerwarteter Fehler ist aufgetreten.";
            zeigeHinweis("🛑 " + fehlerText, "error");
        }
    
    } catch (error) {
        console.error("Netzwerkfehler beim Senden:", error);
        zeigeHinweis("💥 Netzwerkfehler: Der Server antwortet nicht oder sendet fehlerhafte Daten.", "error");
    }
}


let aktuelleTRDaten = null;
let aktuelleTRKurse = {}; // NEU: Speichert die vom Server gelieferten Kurse global
let aktuelleTRVerkaeufe = {};
let aktuellerTRTicker = null; // Speichert den aktuell aktiven Ticker für die Berechnung
let aktuelleTRTickerMapping = {}; // NEU: Merkt sich die Ticker-Übersetzungen
let aktuellerPdfBase64 = null;

async function uploadTradeRepublicCSV() {
    let fileInput = document.getElementById("tr_csv_file");
    if (fileInput.files.length === 0) return;
    let formData = new FormData();
    formData.append("file", fileInput.files[0]);
    let response = await fetch("/api/upload-trade-republic", { method: "POST", body: formData });
    let result = await response.json();
    if (result.success) {
        aktuelleTRDaten = result.data; 
        aktuelleTRKurse = result.kurse; 
        aktuelleTRVerkaeufe = result.verkaufte_anteile;
        aktuelleTRTickerMapping = result.ticker_mapping; // Merkt sich ISIN -> Ticker
    
        let dropdown = document.getElementById("tr_etf_dropdown");
        dropdown.innerHTML = '<option value="">-- Bitte wählen --</option>';
    
        // Wir loopen durch das neue isin_name_mapping
        for (let isin in result.isin_name_mapping) {
            let name = result.isin_name_mapping[isin];
            let opt = document.createElement("option");
            opt.value = isin;      // Im Hintergrund arbeitet JavaScript mit der ISIN!
            opt.innerText = name;  // Der Nutzer sieht weiterhin den schönen Klarnamen!
            dropdown.appendChild(opt);
        }
    
        document.getElementById("tr_etf_auswahl_container").style.display = "block";
        document.getElementById("tr_tabelle_container").style.display = "none";
    } else {
        alert("Fehler: " + result.error);
    }
}


function waehleTradeRepublicETF() {
    let gewaehlteISIN = document.getElementById("tr_etf_dropdown").value;
    let tableContainer = document.getElementById("tr_tabelle_container");
    let tbody = document.getElementById("tr_tabelle_body");
    let verkaufskursInput = document.getElementById("verkaufskurs_tr");
        
    tbody.innerHTML = ""; 
        
    if (!gewaehlteISIN) {
        tableContainer.style.display = "none";
        aktuellerTRTicker = null;
        return;
    }

    // Live-Kurs setzen via ISIN-Schlüssel
    if (aktuelleTRKurse && aktuelleTRKurse[gewaehlteISIN]) {
        verkaufskursInput.value = aktuelleTRKurse[gewaehlteISIN];
    } else {
        verkaufskursInput.value = "100.00";
    }

    // 🎯 HIER PASSIERT DIE MAGIE: 
    // Wir setzen den Ticker für das Berechnungs-Backend auf das yfinance-Symbol, das zur ISIN gehört!
    if (aktuelleTRTickerMapping && aktuelleTRTickerMapping[gewaehlteISIN]) {
        aktuellerTRTicker = aktuelleTRTickerMapping[gewaehlteISIN];
    } else {
        aktuellerTRTicker = gewaehlteISIN; // Fallback
    }

    // Käufe filtern (da 'item.asset' im neuen Backend nun die ISIN ist)
    let gefilterteKaeufe = aktuelleTRDaten.filter(item => item.asset === gewaehlteISIN);
    gefilterteKaeufe.forEach(kauf => {
        fuegeZeileHinzuTR(kauf.datum, kauf.anzahl, kauf.preis);
    });

    tableContainer.style.display = "block"; 
    if (typeof toggleVorabpauschaleTR === "function") {
        toggleVorabpauschaleTR();
    }
    isTRTableCollapsed = true; // Nach ETF-Auswahl standardmäßig einklappen
    aktualisiereTabellenAnsichtTR();
}


function fuegeZeileHinzuTR(datum = "", anzahl = "", preis = "") {
    let tbody = document.getElementById("tr_tr_tabelle_body") || document.getElementById("tr_tabelle_body");
    let row = tbody.insertRow();
        
    // 📅 Ermittelt das heutige Datum live im Format YYYY-MM-DD
    const heute = new Date().toISOString().split('T')[0];
        
    row.innerHTML = `
        <td>
            <input type="date" class="row-datum-tr" max="${heute}" value="${datum}" onchange="
                if(this.value > this.max) { 
                    this.value = this.max; 
                }
                if (typeof toggleVorabpauschaleTR === 'function') {
                    toggleVorabpauschaleTR();
                }
            ">
        </td>
        <td>
            <input type="number" class="row-anzahl-tr" step="0.00001" min="0.00001" placeholder="0.0" value="${anzahl}" onchange="
                if(this.value !== '') {
                    if(parseFloat(this.value) < parseFloat(this.min)) this.value = this.min;
                }
            ">
        </td>
        <td>
            <input type="number" class="row-preis-tr" step="0.01" min="0.01" placeholder="0.00" value="${preis}" onchange="
                if(this.value !== '') {
                    if(parseFloat(this.value) < parseFloat(this.min)) this.value = this.min;
                }
            ">
        </td>
    `;
    isTRTableCollapsed = false; // Bei manuellem Hinzufügen aufklappen
    aktualisiereTabellenAnsichtTR();
}

// Umschalter für Berechnungsfelder im TR-Pfad
function toggleRechenZielFelderTR() {
    let ziel = document.getElementById("rechen_ziel_tr").value;
    document.getElementById("feld_wunschnetto_tr").style.display = (ziel === "wunschnetto") ? "block" : "none";
    document.getElementById("feld_anteile_tr").style.display = (ziel === "steuer_berechnen") ? "block" : "none";
}
            
        
async function sendeBerechnungTR() {
    // 1. Welcher ETF ist aktuell im Dropdown ausgewählt?
    let gewaehlterETF = document.getElementById("tr_etf_dropdown").value;
        
    let kaeufe = [];
    document.querySelectorAll("#tr_tabelle_body tr").forEach(zeile => {
        let datum = zeile.querySelector(".row-datum-tr")?.value;
        let anzahl = parseFloat(zeile.querySelector(".row-anzahl-tr")?.value);
        let preis = parseFloat(zeile.querySelector(".row-preis-tr")?.value);
        if (datum && !isNaN(anzahl) && !isNaN(preis)) {
            kaeufe.push({ datum: datum, anzahl: anzahl, preis: preis });
        }
    });

    // 2. Vorabpauschalen auslesen
    let vorabpauschalen = [];
    if (document.getElementById("haken_vorabpauschale_tr").checked) {
        let vorabZeilen = document.querySelectorAll("#vorab_tabelle_body_tr tr");
        vorabZeilen.forEach(zeile => {
            let jahrField = zeile.querySelector(".vorab-jahr-tr");
            let wertField = zeile.querySelector(".vorab-wert-tr");
        
            if (jahrField && wertField) {
                let jahr = parseInt(jahrField.value);
                let wert = parseFloat(wertField.value);
                if (!isNaN(jahr) && !isNaN(wert)) {
                    vorabpauschalen.push({ jahr: jahr, wert: wert });
                }
            }
        });
    }

    // Bereits verkaufte Anteile für diesen spezifischen ETF ermitteln
    let verkaufteAnteile = 0.0;
    if (aktuelleTRVerkaeufe && aktuelleTRVerkaeufe[gewaehlterETF]) {
        verkaufteAnteile = parseFloat(aktuelleTRVerkaeufe[gewaehlterETF]);
    }

    // 3. Das Payload-Objekt schnüren
    let payload = {
        rechen_ziel: document.getElementById("rechen_ziel_tr").value,
        wert_wunschnetto: parseFloat(document.getElementById("wert_wunschnetto_tr").value) || 0,
        wert_anteile: parseFloat(document.getElementById("wert_anteile_tr").value) || 0,
        verkaufskurs: parseFloat(document.getElementById("verkaufskurs_tr").value),
        freibetrag: parseFloat(document.getElementById("freibetrag").value),
        verlusttopf: parseFloat(document.getElementById("verlusttopf").value),
        kirchensteuer: document.getElementById("kirchensteuer").value,
        // tagesgenau: document.getElementById("tagesgenau_tr").checked,
        tagesgenau: (document.getElementById("tagesgenau_tr").value === "true"),
        manuelle_vorabpauschale_aktiv: document.getElementById("haken_vorabpauschale_tr").checked,
        kaeufe: kaeufe,
        vorabpauschalen: vorabpauschalen,
        teilfreistellung: parseFloat(document.getElementById("teilfreistellung").value),
        ist_thesaurierend: (document.getElementById("ertragsverwendung").value === "thesaurierend"),
        bereits_verkaufte_anteile: verkaufteAnteile,
        ticker: aktuellerTRTicker,
        quelle: "tr"
    };

    // --- VALIDIERUNG VOR DEM SENDEN (FRONTEND-SCHUTZ) ---
    versteckeHinweis(); // Alte Meldungen löschen
    // 🛑 KRITISCHER FEHLER: Verkaufskurs fehlt oder ist <= 0
    if (!payload.verkaufskurs || payload.verkaufskurs <= 0) {
        zeigeHinweis("🛑 Berechnung gestoppt: Der Verkaufskurs muss größer als 0 sein!", "error");
        return; // Bricht ab, kein Request ans Backend
    }
    // 🛑 KRITISCHER FEHLER: Keine Käufe eingetragen
    if (!payload.kaeufe || payload.kaeufe.length === 0) {
        zeigeHinweis("🛑 Berechnung gestoppt: Bitte tragen Sie mindestens eine Kaufhistorie-Zeile ein!", "error");
        return; 
    }
    // 🛑 KRITISCHER FEHLER: Wunschnetto gewählt, aber Betrag ist 0
    if (payload.rechen_ziel === "wunschnetto" && payload.wert_wunschnetto <= 0) {
        zeigeHinweis("🛑 Berechnung gestoppt: Für das Rechenziel 'Wunschnetto' muss ein Betrag größer als 0 eingegeben werden!", "error");
        return;
    }
    // ⚠️ WARNUNG: Verlusttopf unrealistisch hoch (nur Hinweis, wir rechnen weiter)
    if (payload.verlusttopf > 50000) {
        zeigeHinweis("⚠️ Hinweis: Der eingegebene Verlusttopf ist sehr hoch. Die Berechnung läuft normal weiter.", "warning");
    }
    // --- VALIDIERUNG ENDE ---

    try {
        // 4. Daten an das Backend senden
        let response = await fetch("/api/calculate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
    
        let result = await response.json();
        // 5. Verarbeitung der Backend-Antwort
        if (result.success) {
            // Render die KPIs und Tabellen im Frontend
            zeigeErgebnisseImFrontend(result, payload.rechen_ziel);
            // 🎯 NEU: Prüfen, ob das Backend unkritische Warnungen mitgeliefert hat
            if (result.warnings && result.warnings.length > 0) {
                let warnText = "⚠️ " + result.warnings.join("\n⚠️ ");
                zeigeHinweis(warnText, "warning"); 
            } else {
                // Wenn alles perfekt lief und keine Frontend-Warnung aktiv war, Box schließen
                if (payload.verlusttopf <= 50000) {
                    versteckeHinweis();
                }
            }
        
            // Optionale alte Textbox aktualisieren (falls noch im HTML vorhanden)
            if (document.getElementById("rechen_ergebnis_tr")) {
                document.getElementById("rechen_ergebnis_tr").style.display = "block";
                document.getElementById("ergebnis_text_tr").innerHTML = `<pre>Berechnung erfolgreich!</pre>`;
            }
        
        } else {
            // 🎯 KORRIGIERT: Kritische Fehler aus dem Backend elegant in der roten Warnbox anzeigen
            console.error("Kompletter Backend-Fehler:", result);
            let fehlerText = result.error || result.detail || "Ein unerwarteter Fehler ist aufgetreten.";
            zeigeHinweis("🛑 " + fehlerText, "error");
        }
    
    } catch (error) {
        console.error("Netzwerkfehler beim Senden:", error);
        zeigeHinweis("💥 Netzwerkfehler: Der Server antwortet nicht oder sendet fehlerhafte Daten.", "error");
    }
}


// Suche diese Funktion im Code und füge den "3. Trade Republic Pfad" hinzu:
function aktualisiereThesaurierungsAnsicht() {
    let istThesaurierend = (document.getElementById("ertragsverwendung").value === "thesaurierend");
    // 1. Manueller Pfad steuern
    aktualisiereVorabpauschaleTabelle();

    // 2. ETF-Suchpfad steuern
    let vorabHakenSucheContainer = document.getElementById("haken_vorabpauschale_suche")?.parentNode;
    let vorabTabelleSuche = document.getElementById("bereich_vorabpauschale_suche");
    if (!istThesaurierend) {
        if (vorabHakenSucheContainer) vorabHakenSucheContainer.style.display = "none";
        if (vorabTabelleSuche) vorabTabelleSuche.style.display = "none";
        document.getElementById("haken_vorabpauschale_suche").checked = false;
    } else {
        if (vorabHakenSucheContainer) vorabHakenSucheContainer.style.display = "block";
    }

    // 3. NEU: Trade Republic Pfad steuern
    let vorabHakenTRContainer = document.getElementById("haken_vorabpauschale_tr")?.parentNode;
    let vorabTabelleTR = document.getElementById("bereich_vorabpauschale_tr");
    if (!istThesaurierend) {
        if (vorabHakenTRContainer) vorabHakenTRContainer.style.display = "none";
        if (vorabTabelleTR) vorabTabelleTR.style.display = "none";
        document.getElementById("haken_vorabpauschale_tr").checked = false;
    } else {
        if (vorabHakenTRContainer) vorabHakenTRContainer.style.display = "block";
    }
}

function toggleVorabpauschaleTR() {
    let istThesaurierend = (document.getElementById("ertragsverwendung").value === "thesaurierend");
    let haken = document.getElementById("haken_vorabpauschale_tr").checked;
    let vorabBereich = document.getElementById("bereich_vorabpauschale_tr");
    let tbody = document.getElementById("vorab_tabelle_body_tr");
        
    tbody.innerHTML = ""; // Vorherige Zeilen leeren
        
    // Wenn nicht thesaurierend oder Haken nicht gesetzt -> verstecken
    if (!haken || !istThesaurierend) {
        vorabBereich.style.display = "none";
        return;
    }

    // Ältestes Jahr aus den importierten TR-Käufen ermitteln
    let datumsFelder = document.querySelectorAll(".row-datum-tr");
    let MindestJahr = 2018;
    let aktuellesJahr = 2026; 
    let aeltestesJahr = aktuellesJahr;

    datumsFelder.forEach(feld => {
        if (feld.value) {
            let kaufJahr = new Date(feld.value).getFullYear();
            if (kaufJahr < aeltestesJahr) {
                aeltestesJahr = kaufJahr;
            }
        }
    });

    if (aeltestesJahr < MindestJahr) {
        aeltestesJahr = MindestJahr;
    }

    if (aeltestesJahr < aktuellesJahr) {
        vorabBereich.style.display = "block";
        for (let jahr = aeltestesJahr; jahr < aktuellesJahr; jahr++) {
            let row = tbody.insertRow();
            row.innerHTML = `
                <td><input type="number" class="vorab-jahr-tr" value="${jahr}" disabled ></td>
                <td><input type="number" class="vorab-wert-tr" value="0.00000000" step="0.00000001" min="0"></td>
            `;
        }
    } else {
        vorabBereich.style.display = "block";
        let row = tbody.insertRow();
        row.innerHTML = `<td colspan="2" style="color: #666; text-align: center;">Keine Käufe aus Vorjahren in der Tabelle gefunden.</td>`;
    }
}

// Variable, um die ID der aktuellen Berechnung für den PDF-Export zu speichern
let aktuelleBerechnungsId = null;

function zeigeErgebnisseImFrontend(result, rechenZiel) {
    if (!result.success) return;
        
    aktuellerPdfBase64 = result.pdf_data || null;
    aktuelleBerechnungsId = result.calculation_id || null;
        
    let kpi1 = document.getElementById("kpi_label_1");
    let kpi2 = document.getElementById("kpi_label_2");
    let kpi3 = document.getElementById("kpi_label_3");
        
    // 1. Labels UND Einheiten-Typen je nach Rechenziel festlegen
    let einheitKPI1 = "EUR";
    let einheitKPI2 = "EUR";
    let einheitKPI3 = "EUR";
    if (kpi1 && kpi2 && kpi3) {
        if (rechenZiel === "wunschnetto") {
            kpi1.innerText = "Benötigte Anteile";
            einheitKPI1 = "Anteile";
            kpi2.innerText = "Bruttoerlös";
            kpi3.innerText = "Nettoerlös";
        } else if (rechenZiel === "steuerfrei") {
            kpi1.innerText = "Max. steuerfrei verkaufbare Anteile";
            einheitKPI1 = "Anteile";
            kpi2.innerText = "Nettoerlös";
            kpi3.innerText = "Verbleibender Freibetrag";
        } else {
            kpi1.innerText = "Bruttoerlös";
            kpi2.innerText = "Nettoerlös";
            kpi3.innerText = "Steuerabzug";
        }
    }


    // Werte mit der jeweils passenden Einheit eintragen
    if (document.getElementById("kpi_wert_1")) {
        document.getElementById("kpi_wert_1").innerText = formatiereWert(result.kpis.wert1, einheitKPI1);
    }
    if (document.getElementById("kpi_wert_2")) {
        document.getElementById("kpi_wert_2").innerText = formatiereWert(result.kpis.wert2, einheitKPI2);
    }
    if (document.getElementById("kpi_wert_3")) {
        document.getElementById("kpi_wert_3").innerText = formatiereWert(result.kpis.wert3, einheitKPI3);
    }

    // 2. Tabelle dynamisch befüllen
    let tbody = document.getElementById("ergebnis_tabelle_body");
    if (tbody) {
        tbody.innerHTML = ""; 
    
        if (result.tabelle && Array.isArray(result.tabelle)) {
            result.tabelle.forEach(posten => {
                let tr = document.createElement("tr");
                tr.style.borderBottom = "1px solid #eee";
            
                // 🎯 Nutzt die vom Backend mitgelieferte Einheit, falls vorhanden (sonst standardmäßig EUR)
                let anzuzeigendeEinheit = posten.einheit || "EUR";
                let formatierterWert = formatiereWert(posten.wert, anzuzeigendeEinheit);
            
                tr.innerHTML = `
                    <td style="padding: 10px; color: #555;">${posten.name}</td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">${formatierterWert}</td>
                `;
                tbody.appendChild(tr);
            });
        }
    }
    let vorabTbody = document.getElementById("vorab_ergebnis_tabelle_body");
    let vorabContainer = document.getElementById("vorab_ergebnis_container");
    if (vorabTbody && vorabContainer) {
        vorabTbody.innerHTML = ""; // Altes Ergebnis löschen
    
        // Prüfen, ob das Backend überhaupt Vorabpauschalen zurückgegeben hat und die Liste nicht leer ist
        if (result.vorabpauschalen_ergebnis && result.vorabpauschalen_ergebnis.length > 0) {
            result.vorabpauschalen_ergebnis.forEach(posten => {
                let tr = document.createElement("tr");
                tr.style.borderBottom = "1px solid #eee";
            
                tr.innerHTML = `
                    <td style="padding: 10px; color: #555;">Vorabpauschale ${posten.jahr}</td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">
                        ${formatiereWert(posten.wert, "Anteile")}
                    </td>
                `;
                vorabTbody.appendChild(tr);
            });
            vorabContainer.style.display = "block"; // Tabelle anzeigen, wenn Daten da sind
        } else {
            // Falls keine Vorabpauschalen im Spiel waren (oder keine eingegeben wurden), 
            // verstecken wir den Container einfach, damit es sauber aussieht.
            vorabContainer.style.display = "none"; 
        }
    }

    // Container anzeigen & scrollen
    let ergebnisContainer = document.getElementById("ergebnis_container");
    if (ergebnisContainer) {
        ergebnisContainer.style.display = "block";
        ergebnisContainer.scrollIntoView({ behavior: 'smooth' });
    }
}

// Neue, flexible Formatierungs-Funktion
function formatiereWert(wert, einheit) {
    if (einheit === "Anteile") {
        // Formatiert Anteile mit bis zu 4 Nachkommastellen (wichtig bei Bruchstücken)
        return new Intl.NumberFormat('de-DE', { 
            minimumFractionDigits: 2, 
            maximumFractionDigits: 5 
        }).format(wert) ;
    }
    // Standard-Fallback: Euro-Formatierung
    return new Intl.NumberFormat('de-DE', { 
        style: 'currency', 
        currency: 'EUR' 
    }).format(wert);
}


function downloadeErgebnisPDF() {
    if (!aktuellerPdfBase64) {
        alert("Keine PDF-Daten verfügbar. Bitte starte die Berechnung erneut.");
        return;
    }

    try {
        // 1. Base64-String in rohe Binärdaten umwandeln
        let byteCharacters = atob(aktuellerPdfBase64);
        let byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        let byteArray = new Uint8Array(byteNumbers);
        // 2. Ein echtes Blob-Objekt für ein PDF erstellen
        let blob = new Blob([byteArray], { type: "application/pdf" });
        // 3. Eine temporäre Browser-URL für dieses Blob erzeugen
        let blobUrl = URL.createObjectURL(blob);
    
        // 4. Den unsichtbaren Download-Link erstellen
        let link = document.createElement("a");
        link.href = blobUrl;
        link.download = `Steuerreport_${aktuellerTRTicker || "ETF"}.pdf`;
        // WICHTIG: Das Element MUSS im DOM sein, damit einige Browser den Klick erlauben
        document.body.appendChild(link);
        link.click();
        // 5. Aufräumen (Link löschen und Speicher freigeben)
        document.body.removeChild(link);
        URL.revokeObjectURL(blobUrl);
    } catch (error) {
        console.error("❌ Fehler beim PDF-Download:", error);
        alert("Fehler beim Generieren der PDF-Datei im Browser: " + error.message);
    }
}


function zeigeHinweis(text, typ) {
    let alertBox = document.getElementById("validation_alert");
    if (!alertBox) return;

    // Wandelt Zeilenumbrüche (\n) aus dem Backend in lesbare HTML-Umbrüche um
    alertBox.innerHTML = text.replace(/\n/g, "<br>");
    
    // Vorherige Farb-Klassen entfernen, um Fehler zu vermeiden
    alertBox.classList.remove("message-warning", "message-error");

    // Die passende CSS-Klasse je nach Typ zuweisen
    if (typ === "warning") {
        alertBox.classList.add("message-warning");
    } else if (typ === "error") {
        alertBox.classList.add("message-error");
    }

    // Box anzeigen
    alertBox.style.display = "block";
}

function versteckeHinweis() {
    let alertBox = document.getElementById("validation_alert");
    if (!alertBox) return;

    // Box verstecken und zurücksetzen
    alertBox.style.display = "none";
    alertBox.innerHTML = "";
    alertBox.classList.remove("message-warning", "message-error");
}


toggleEingabeOptionen();



document.addEventListener("DOMContentLoaded", function () {
        
  const rechnerContainer = document.getElementById("rechner") || document.querySelector(".tool");
  const button = document.querySelector(".mobile-tool-button");
        
  if (!rechnerContainer || !button) return;
        
  // 1. Der Observer (steuert das Ein- und Ausblenden des Knopfs)
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          button.classList.remove("visible"); 
        } else {
          button.classList.add("visible");    
        }
      });
    },
    {
      threshold: 0.1 
    }
  );

  observer.observe(rechnerContainer);

  // 2. NEU: Die Klick-Funktion für den weichen Bildlauf zum Rechner
  button.addEventListener("click", function (e) {
    e.preventDefault(); // Verhindert unschöne Sprünge in der URL
    rechnerContainer.scrollIntoView({ 
      behavior: "smooth", // Aktiviert das weiche, flüssige Scrollen
      block: "start"      // Richtet den Rechner exakt an der Oberkante des Handys aus
    });
  });

});


function aktualisiereManuelleAnsicht() {
    const sucheInputFeld = document.getElementById('etf_suche_input');
    const symbolAnzeige = document.getElementById('etf_symbol_anzeige')?.innerText || "-";
    const etfBoxSichtbar = document.getElementById('ausgewählter_etf_box').style.display !== 'none';
    
    const csvUploadGruppe = document.getElementById('manuell_csv_upload_group');
    const vorabpauschaleHakenGroup = document.getElementById('vorabpauschale_haken_group');
    const bereichVorabpauschale = document.getElementById('bereich_vorabpauschale');
    const sucheWarnung = document.getElementById('etf_suche_warnung');

    // Ein ETF gilt NUR DANN als gültig ausgewählt, wenn die Box sichtbar ist UND das Symbol nicht "-" ist.
    const etfWurdeAusgewaehlt = (etfBoxSichtbar && symbolAnzeige !== "-");

    console.log("🔍 PRÜFUNG:");
    console.log("Input-Wert:", sucheInputFeld.value);
    console.log("Symbol in Box:", symbolAnzeige);
    console.log("Box sichtbar?:", etfBoxSichtbar);

    if (!etfWurdeAusgewaehlt) {
        console.log("Ergebnis: Ist ETF gültig ausgewählt?:", etfWurdeAusgewaehlt);
        // ==========================================================================
        // ❌ FALL A: KEIN ETF GEWÄHLT (Leer oder reiner Freitext)
        // ==========================================================================
        if (csvUploadGruppe) csvUploadGruppe.style.display = 'block';
        if (vorabpauschaleHakenGroup) vorabpauschaleHakenGroup.style.display = 'none';
        
        // Tabelle bei Freitext/Leere IMMER dauerhaft anzeigen
        if (bereichVorabpauschale) bereichVorabpauschale.style.display = 'block';

        // Warnung einblenden, wenn Freitext eingetippt wurde
        if (sucheWarnung) {
            sucheWarnung.style.display = (sucheInputFeld && sucheInputFeld.value.trim().length > 0) ? 'block' : 'none';
        }

        // Jahre generieren
        if (typeof aktualisiereVorabpauschaleTabelle === "function") {
            aktualisiereVorabpauschaleTabelle();
        }
    } else {
        // ==========================================================================
        //  FALL B: GÜLTIGER ETF AKTIV AUSGEWÄHLT
        // ==========================================================================
        if (vorabpauschaleHakenGroup) vorabpauschaleHakenGroup.style.display = 'block';
        if (sucheWarnung) sucheWarnung.style.display = 'none';
        
        // Zuerst die Jahre im Hintergrund berechnen lassen
        if (typeof aktualisiereVorabpauschaleTabelle === "function") {
            aktualisiereVorabpauschaleTabelle();
        }

        // Jetzt entscheidet EXKLUSIV der Status des Häkchens über die Sichtbarkeit!
        toggleVorabpauschale();
    }
}

function toggleVorabpauschale() {
    // 🎯 Bereinigt: Die alte 'kein_etf_auswahl'-Abfrage wurde entfernt, da sie Fehler verursacht hat
    const hakenAktiv = document.getElementById('haken_vorabpauschale')?.checked || false;
    const bereichVorabpauschale = document.getElementById('bereich_vorabpauschale');

    if (bereichVorabpauschale) {
        if (hakenAktiv) {
            bereichVorabpauschale.style.display = 'block';
            // Falls beim Aktivieren des Hakens im ETF-Modus auch die Jahre berechnet werden sollen:
            if (typeof aktualisiereVorabpauschaleTabelle === "function") {
                aktualisiereVorabpauschaleTabelle();
            }
        } else {
            bereichVorabpauschale.style.display = 'none';
        }
    }
}

function loescheZeileSparplan(button) {
    button.closest("tr").remove();
    if (typeof aktualisiereVorabpauschaleTabelleSparplan === "function") {
        aktualisiereVorabpauschaleTabelleSparplan();
    }

    aktualisiereTabellenAnsichtSparplan();
}


function aktualisiereVorabpauschaleTabelleSparplan() {
    let datumsFelder = document.querySelectorAll(".row-datum-sparplan");
    let MindestJahr = 2018; 
    let aktuellesJahr = new Date().getFullYear(); // 2026
    let aeltestesJahr = aktuellesJahr;

    // 1. Ältestes Kaufdatum ermitteln
    datumsFelder.forEach(feld => {
        // 🎯 KORREKTUR: Hier muss 'feld' statt 'datum' abgefragt werden!
        if (feld && feld.value) {
            let kaufJahr = new Date(feld.value).getFullYear();
            if (kaufJahr < aeltestesJahr) {
                aeltestesJahr = kaufJahr;
            }
        }
    });

    if (aeltestesJahr < MindestJahr) {
        aeltestesJahr = MindestJahr;
    }

    let vorabBereich = document.getElementById("bereich_vorabpauschale_sparplan");
    let tbody = document.getElementById("vorab_tabelle_body_sparplan");
    if (!tbody) return;
    
    tbody.innerHTML = ""; // Vorherige Zeilen leeren

    // 2. Zeilen für die Jahre generieren
    if (aeltestesJahr < aktuellesJahr) {
        for (let jahr = aeltestesJahr; jahr < aktuellesJahr; jahr++) {
            let row = tbody.insertRow();
            row.innerHTML = `
                <td><input type="number" class="vorab-jahr-sparplan" value="${jahr}" disabled ></td>
                <td><input type="number" class="vorab-wert-sparplan" value="0.00000000" step="0.00000001" min="0"></td>
            `;
        }

        // 3. Sichtbarkeit an den neuen Modus koppeln
        const symbolAnzeige = document.getElementById('etf_symbol_anzeige_sparplan')?.innerText || "-";
        const etfBoxSichtbar = document.getElementById('ausgewählter_etf_box_sparplan').style.display !== 'none';
        const etfWurdeAusgewaehlt = (etfBoxSichtbar && symbolAnzeige !== "-");
        
        const hakenManuellAktiv = document.getElementById('haken_vorabpauschale_sparplan')?.checked || false;

        // Wenn kein ETF da ist OR das Häkchen im ETF-Modus aktiv ist -> Zeigen!
        if (!etfWurdeAusgewaehlt || hakenManuellAktiv) {
            if (vorabBereich) vorabBereich.style.display = "block";
        } else {
            if (vorabBereich) vorabBereich.style.display = "none";
        }

    } else {
        if (vorabBereich) vorabBereich.style.display = "none";
    }
}


function aktualisiereSparplanAnsicht() {
    const sucheInputFeld = document.getElementById('etf_suche_input_sparplan');
    const symbolAnzeige = document.getElementById('etf_symbol_anzeige_sparplan')?.innerText || "-";
    const etfBoxSichtbar = document.getElementById('ausgewählter_etf_box_sparplan').style.display !== 'none';
    
    const vorabpauschaleHakenGroup = document.getElementById('sparplan_vorabpauschale_haken_group');
    const bereichVorabpauschale = document.getElementById('bereich_vorabpauschale_sparplan');
    const sucheWarnung = document.getElementById('etf_suche_warnung_sparplan');

    // Ein ETF gilt als gültig ausgewählt, wenn die Box aktiv ist und das Symbol nicht "-" lautet
    const etfWurdeAusgewaehlt = (etfBoxSichtbar && symbolAnzeige !== "-");

    if (!etfWurdeAusgewaehlt) {
        // ==========================================================================
        // ❌ FALL A: KEIN ETF GEWÄHLT (Leer oder Freitext)
        // ==========================================================================
        if (vorabpauschaleHakenGroup) vorabpauschaleHakenGroup.style.display = 'none';
        
        // Im Freitext-Modus die Tabelle IMMER dauerhaft anzeigen
        if (bereichVorabpauschale) bereichVorabpauschale.style.display = 'block';

        // Warnung steuern: Anzeigen, wenn wilder Text eingetippt wurde
        if (sucheWarnung) {
            sucheWarnung.style.display = (sucheInputFeld && sucheInputFeld.value.trim().length > 0) ? 'block' : 'none';
        }

        // Jahre in der Tabelle neu berechnen und füllen
        if (typeof aktualisiereVorabpauschaleTabelleSparplan === "function") {
            aktualisiereVorabpauschaleTabelleSparplan();
        }
    } else {
        // ==========================================================================
        //  FALL B: GÜLTIGER ETF IM SPARPLAN GEWÄHLT
        // ==========================================================================
        if (vorabpauschaleHakenGroup) vorabpauschaleHakenGroup.style.display = 'block';
        if (sucheWarnung) sucheWarnung.style.display = 'none';
        
        // Erst Jahre im Hintergrund berechnen lassen
        if (typeof aktualisiereVorabpauschaleTabelleSparplan === "function") {
            aktualisiereVorabpauschaleTabelleSparplan();
        }

        // Jetzt entscheidet exklusiv der Status des Häkchens über die Sichtbarkeit
        toggleVorabpauschaleSparplan();
    }
}

// Vorabpauschale manuell ein/ausblenden
function toggleVorabpauschaleSparplan() {
    const hakenAktiv = document.getElementById('haken_vorabpauschale_sparplan').checked;
    const bereichVorabpauschale = document.getElementById('bereich_vorabpauschale_sparplan');

    if (hakenAktiv) {
        bereichVorabpauschale.style.display = 'block';
    } else {
        bereichVorabpauschale.style.display = 'none';
    }
}

// Berechnungs-Ziele (Wunschnetto, Anteile etc.) ein/ausblenden
function toggleRechenZielFelderSparplan() {
    const ziel = document.getElementById("rechen_ziel_sparplan").value;
    const feldWunschnetto = document.getElementById("feld_wunschnetto_sparplan");
    const feldAnteile = document.getElementById("feld_anteile_sparplan");

    if (ziel === "wunschnetto") {
        feldWunschnetto.style.display = "block";
        feldAnteile.style.display = "none";
    } else if (ziel === "steuer_berechnen") {
        feldWunschnetto.style.display = "none";
        feldAnteile.style.display = "block";
    } else {
        // Für 'steuerfrei' werden beide Zusatzfelder nicht gebraucht
        feldWunschnetto.style.display = "none";
        feldAnteile.style.display = "none";
    }
}

// Globaler Zustand für den Einklapp-Status (Standard: eingeklappt nach CSV-Upload)
let isTableCollapsed = true; 


// Funktion für den Klick auf die Toggle-Buttons
function toggleTabelleKlappen() {
    isTableCollapsed = !isTableCollapsed;
    aktualisiereTabellenAnsicht();
}


// Globaler Zustand für den Einklapp-Status der Sparplan-Tabelle
let isSparplanTableCollapsed = true; 

// Click-Handler für die Buttons des Sparplans
function toggleTabelleKlappenSparplan() {
    isSparplanTableCollapsed = !isSparplanTableCollapsed;
    aktualisiereTabellenAnsichtSparplan();
}

// Globaler Zustand für den Einklapp-Status der Trade Republic Tabelle
let isTRTableCollapsed = true; 


function aktualisiereTabellenAnsicht() {
    let tbody = document.getElementById("tabelle_body");
    // Alle echten Zeilen holen (Platzhalter-Zeile ausschließen)
    let zeilen = Array.from(tbody.querySelectorAll("tr")).filter(tr => !tr.classList.contains("placeholder-row"));
    
    // Alte Platzhalter-Zeile entfernen
    let alterPlatzhalter = tbody.querySelector(".placeholder-row");
    if (alterPlatzhalter) alterPlatzhalter.remove();

    let btnOben = document.getElementById("btn_toggle_tabelle_oben");
    let btnUnten = document.getElementById("btn_toggle_tabelle_unten");
    let aktionsLeiste = document.getElementById("tabelle_aktionen_manuell");

    // 🎯 REGLUNG 1: Wenn weniger als 3 Einträge existieren: Beide Knöpfe weg, alles sichtbar
    if (zeilen.length < 3) {
        zeilen.forEach(z => z.classList.remove("row-hidden")); // Sichtbar machen
        if (btnOben) btnOben.style.display = "none";
        if (btnUnten) btnUnten.style.display = "none";
        if (aktionsLeiste) aktionsLeiste.style.display = "flex"; // Buttons immer sichtbar
        return;
    }

    if (isTableCollapsed) {
        // 🎯 REGLUNG 2: Im zusammengeklappten Zustand...
        if (btnOben) btnOben.style.display = "none";    // ...oberer Knopf VERSCHWINDET
        if (btnUnten) {
            btnUnten.style.display = "block";           // ...unterer Knopf bleibt sichtbar
            btnUnten.innerText = "↕️ Gesamte Tabelle anzeigen";
        }

        // Verstecke die Aktionsknöpfe (Hinzufügen, Download, Leeren)
        if (aktionsLeiste) aktionsLeiste.style.display = "none";

        // Erste und letzte Zeile zeigen, den Rest via CSS-Klasse verstecken
        zeilen.forEach((zeile, index) => {
            if (index === 0 || index === zeilen.length - 1) {
                zeile.classList.remove("row-hidden");
            } else {
                zeile.classList.add("row-hidden"); // Überschreibt das Mobil-Grid!
            }
        });

        // Platzhalter für ausgeblendete Zeilen einbauen
        let verdeckteAnzahl = zeilen.length - 2;
        let placeholderTr = document.createElement("tr");
        placeholderTr.className = "placeholder-row";
        // Streckt den Platzhalter im Mobil-Grid über beide Spalten
        placeholderTr.style.setProperty("grid-column", "span 2", "important");
        placeholderTr.innerHTML = `
            <td colspan="4" style="text-align: center; font-style: italic;">
                ➔ ${verdeckteAnzahl} weitere Einträge ausgeblendet...
            </td>
        `;
        tbody.insertBefore(placeholderTr, zeilen[zeilen.length - 1]);

    } else {
        // 🎯 REGLUNG 3: Im aufgeklappten Zustand sind BEIDE Knöpfe sichtbar
        if (btnOben) {
            btnOben.style.display = "block";
            btnOben.innerText = "↕️ Tabelle kompakter anzeigen";
        }
        if (btnUnten) {
            btnUnten.style.display = "block";
            btnUnten.innerText = "↕️ Tabelle kompakter anzeigen";
        }

        // Zeige die Aktionsknöpfe wieder
        if (aktionsLeiste) aktionsLeiste.style.display = "flex";

        // Alle Tabellenzeilen einblenden
        zeilen.forEach(zeile => zeile.classList.remove("row-hidden"));
    }
}


function aktualisiereTabellenAnsichtSparplan() {
    let tbody = document.getElementById("sparplan_tabelle_body");
    // Alle echten Zeilen holen (Platzhalter ausschließen)
    let zeilen = Array.from(tbody.querySelectorAll("tr")).filter(tr => !tr.classList.contains("placeholder-row"));
    
    // Alte Platzhalter-Zeile entfernen
    let alterPlatzhalter = tbody.querySelector(".placeholder-row");
    if (alterPlatzhalter) alterPlatzhalter.remove();

    let btnOben = document.getElementById("btn_toggle_tabelle_oben_sparplan");
    let btnUnten = document.getElementById("btn_toggle_tabelle_unten_sparplan");
    let aktionsLeiste = document.getElementById("tabelle_aktionen_sparplan");

    // Regel 1: Unter 3 Einträgen -> alles anzeigen, Knöpfe weg
    if (zeilen.length < 3) {
        zeilen.forEach(z => z.classList.remove("row-hidden"));
        if (btnOben) btnOben.style.display = "none";
        if (btnUnten) btnUnten.style.display = "none";
        if (aktionsLeiste) aktionsLeiste.style.display = "flex";
        return;
    }

    if (isSparplanTableCollapsed) {
        // Regel 2: Im zusammengeklappten Zustand oberer Knopf weg, unterer zeigt "anzeigen"
        if (btnOben) btnOben.style.display = "none";
        if (btnUnten) {
            btnUnten.style.display = "block";
            btnUnten.innerText = "↕️ Gesamte Tabelle anzeigen";
        }

        // Aktionsleiste verstecken
        if (aktionsLeiste) aktionsLeiste.style.display = "none";

        // Nur erste und letzte Zeile anzeigen
        zeilen.forEach((zeile, index) => {
            if (index === 0 || index === zeilen.length - 1) {
                zeile.classList.remove("row-hidden");
            } else {
                zeile.classList.add("row-hidden"); // Überschreibt das Mobil-Grid!
            }
        });

        // Platzhalter für ausgeblendete Zeilen einbauen
        let verdeckteAnzahl = zeilen.length - 2;
        let placeholderTr = document.createElement("tr");
        placeholderTr.className = "placeholder-row";
        // Streckt den Platzhalter im Mobil-Grid über beide Spalten
        placeholderTr.style.setProperty("grid-column", "span 2", "important");
        placeholderTr.innerHTML = `
            <td colspan="4" style="text-align: center; font-style: italic;">
                ➔ ${verdeckteAnzahl} weitere Einträge ausgeblendet...
            </td>
        `;
        tbody.insertBefore(placeholderTr, zeilen[zeilen.length - 1]);

    } else {
        // Regel 3: Im aufgeklappten Zustand beide Knöpfe da
        if (btnOben) {
            btnOben.style.display = "block";
            btnOben.innerText = "↕️ Tabelle kompakter anzeigen";
        }
        if (btnUnten) {
            btnUnten.style.display = "block";
            btnUnten.innerText = "↕️ Tabelle kompakter anzeigen";
        }

        if (aktionsLeiste) aktionsLeiste.style.display = "flex";

        // Alle echten Zeilen einblenden
        zeilen.forEach(zeile => zeile.classList.remove("row-hidden"));
    }
}


function aktualisiereTabellenAnsichtTR() {
    let tbody = document.getElementById("tr_tabelle_body");
    // Alle echten Zeilen holen (Platzhalter ausschließen)
    let zeilen = Array.from(tbody.querySelectorAll("tr")).filter(tr => !tr.classList.contains("placeholder-row"));
    
    // Alte Platzhalter-Zeile entfernen
    let alterPlatzhalter = tbody.querySelector(".placeholder-row");
    if (alterPlatzhalter) alterPlatzhalter.remove();

    let btnOben = document.getElementById("btn_toggle_tabelle_oben_tr");
    let btnUnten = document.getElementById("btn_toggle_tabelle_unten_tr");
    let aktionsLeiste = document.getElementById("tabelle_aktionen_tr");

    // Regel 1: Unter 3 Einträgen -> alles anzeigen, Knöpfe weg, Aktionsleiste sichtbar
    if (zeilen.length < 3) {
        zeilen.forEach(z => z.classList.remove("row-hidden"));
        if (btnOben) btnOben.style.display = "none";
        if (btnUnten) btnUnten.style.display = "none";
        if (aktionsLeiste) aktionsLeiste.style.display = "flex";
        return;
    }

    if (isTRTableCollapsed) {
        // Regel 2: Im zusammengeklappten Zustand oberer Knopf weg, unterer zeigt "anzeigen"
        if (btnOben) btnOben.style.display = "none";
        if (btnUnten) {
            btnUnten.style.display = "block";
            btnUnten.innerText = "↕️ Gesamte Tabelle anzeigen";
        }

        // Aktionsleiste verstecken
        if (aktionsLeiste) aktionsLeiste.style.display = "none";

        // Nur erste und letzte Zeile anzeigen
        zeilen.forEach((zeile, index) => {
            if (index === 0 || index === zeilen.length - 1) {
                zeile.classList.remove("row-hidden");
            } else {
                zeile.classList.add("row-hidden"); // Überschreibt das Mobil-Grid!
            }
        });

        // Platzhalter für ausgeblendete Zeilen einbauen
        let verdeckteAnzahl = zeilen.length - 2;
        let placeholderTr = document.createElement("tr");
        placeholderTr.className = "placeholder-row";
        // Streckt den Platzhalter im Mobil-Grid über beide Spalten
        placeholderTr.style.setProperty("grid-column", "span 2", "important");
        placeholderTr.innerHTML = `
            <td colspan="4" style="text-align: center; font-style: italic;">
                ➔ ${verdeckteAnzahl} weitere Einträge ausgeblendet...
            </td>
        `;
        tbody.insertBefore(placeholderTr, zeilen[zeilen.length - 1]);

    } else {
        // Regel 3: Im aufgeklappten Zustand beide Knöpfe da
        if (btnOben) {
            btnOben.style.display = "block";
            btnOben.innerText = "↕️ Tabelle kompakter anzeigen";
        }
        if (btnUnten) {
            btnUnten.style.display = "block";
            btnUnten.innerText = "↕️ Tabelle kompakter anzeigen";
        }

        if (aktionsLeiste) aktionsLeiste.style.display = "flex";

        // Alle echten Zeilen einblenden
        zeilen.forEach(zeile => zeile.classList.remove("row-hidden"));
    }
}

// Click-Handler für die Buttons des TR-Bereichs
function toggleTabelleKlappenTR() {
    isTRTableCollapsed = !isTRTableCollapsed;
    aktualisiereTabellenAnsichtTR();
}

function fuegeZeileHinzuSparplan(datum = "", anzahl = "", preis = "") {
    let tbody = document.getElementById("sparplan_tabelle_body");
    let tr = document.createElement("tr");

    const heute = new Date().toISOString().split('T')[0];

    tr.innerHTML = `
        <td>
            <input type="date" class="row-datum-sparplan" max="${heute}" value="${datum}" onchange="
                if(this.value > this.max) { 
                    this.value = this.max; 
                }
                if (typeof aktualisiereVorabpauschaleTabelleSparplan === 'function') {
                    aktualisiereVorabpauschaleTabelleSparplan();
                }
                pruefeUnvollstaendigeZeilen();
            " oninput="pruefeUnvollstaendigeZeilen()">
        </td>
        <td>
            <input type="number" class="row-anzahl-sparplan" step="0.00001" min="0.00001" placeholder="0.0" value="${anzahl}" onchange="
                if(this.value !== '') {
                    if(parseFloat(this.value) < parseFloat(this.min)) this.value = this.min;
                }
                pruefeUnvollstaendigeZeilen();
            " oninput="pruefeUnvollstaendigeZeilen()">
        </td>
        <td>
            <input type="number" class="row-preis-sparplan" step="0.01" min="0.01" placeholder="0.00" value="${preis}" onchange="
                if(this.value !== '') {
                    if(parseFloat(this.value) < parseFloat(this.min)) this.value = this.min;
                }
                pruefeUnvollstaendigeZeilen();
            " oninput="pruefeUnvollstaendigeZeilen()">
        </td>
        <td>
            <button type="button" class="btn-delete" onclick="loescheZeileSparplan(this)">🗑️</button>
        </td>
    `;
    
    tbody.appendChild(tr);

    if (typeof aktualisiereVorabpauschaleTabelleSparplan === "function") {
        aktualisiereVorabpauschaleTabelleSparplan();
    }

    if (!datum) { 
        isSparplanTableCollapsed = false; 
    }
    aktualisiereTabellenAnsichtSparplan();
    pruefeUnvollstaendigeZeilen(); // Direkt beim Erstellen prüfen
}


function fuegeZeileHinzu(datum = "", anzahl = "", preis = "") {
    let tbody = document.getElementById("tabelle_body");
    let tr = document.createElement("tr");

    const heute = new Date().toISOString().split('T')[0];

    tr.innerHTML = `
        <td>
            <input type="date" class="row-datum" max="${heute}" value="${datum}" onchange="
                if(this.value > this.max) { 
                    this.value = this.max; 
                }
                if (typeof aktualisiereVorabpauschaleTabelle === 'function') {
                    aktualisiereVorabpauschaleTabelle();
                }
                pruefeUnvollstaendigeZeilen();
            " oninput="pruefeUnvollstaendigeZeilen()">
        </td>
        <td>
            <input type="number" class="row-anzahl" step="0.00001" min="0.00001" placeholder="0.0" value="${anzahl}" onchange="
                if(this.value !== '') {
                    if(parseFloat(this.value) < parseFloat(this.min)) this.value = this.min;
                }
                pruefeUnvollstaendigeZeilen();
            " oninput="pruefeUnvollstaendigeZeilen()">
        </td>
        <td>
            <input type="number" class="row-preis" step="0.01" min="0.01" placeholder="0.00" value="${preis}" onchange="
                if(this.value !== '') {
                    if(parseFloat(this.value) < parseFloat(this.min)) this.value = this.min;
                }
                pruefeUnvollstaendigeZeilen();
            " oninput="pruefeUnvollstaendigeZeilen()">
        </td>
        <td>
            <button type="button" class="btn-delete" onclick="loescheZeile(this)">🗑️</button>
        </td>
    `;
    
    tbody.appendChild(tr);

    if (typeof aktualisiereVorabpauschaleTabelle === "function") {
        aktualisiereVorabpauschaleTabelle();
    }

    isTableCollapsed = false; 
    aktualisiereTabellenAnsicht();
    pruefeUnvollstaendigeZeilen(); // Direkt beim Erstellen prüfen
}

// 🎯 NEU: Zentrale Prüffunktion für unvollständige Zeilen
function pruefeUnvollstaendigeZeilen() {
    // 1. Manuelle Tabelle prüfen
    let manuellZeilen = document.querySelectorAll("#tabelle_body tr:not(.placeholder-row)");
    let hatManuellFehler = false;
    manuellZeilen.forEach(zeile => {
        let d = zeile.querySelector(".row-datum")?.value;
        let a = zeile.querySelector(".row-anzahl")?.value;
        let p = zeile.querySelector(".row-preis")?.value;
        // Wenn mindestens ein Feld ausgefüllt ist, aber nicht alle drei:
        if ((d || a || p) && (!d || !a || !p)) {
            hatManuellFehler = true;
        }
    });
    document.getElementById("warnung_unvollstaendig_manuell").style.display = hatManuellFehler ? "block" : "none";

    // 2. Sparplan Tabelle prüfen
    let sparplanZeilen = document.querySelectorAll("#sparplan_tabelle_body tr:not(.placeholder-row)");
    let hatSparplanFehler = false;
    sparplanZeilen.forEach(zeile => {
        let d = zeile.querySelector(".row-datum-sparplan")?.value;
        let a = zeile.querySelector(".row-anzahl-sparplan")?.value;
        let p = zeile.querySelector(".row-preis-sparplan")?.value;
        if ((d || a || p) && (!d || !a || !p)) {
            hatSparplanFehler = true;
        }
    });
    document.getElementById("warnung_unvollstaendig_sparplan").style.display = hatSparplanFehler ? "block" : "none";
}
