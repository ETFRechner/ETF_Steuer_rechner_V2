// -------------------------------------
// HTMX globale Events
// -------------------------------------

document.body.addEventListener("htmx:beforeRequest", function (event) {

    const target = event.detail.target

    if (target) {
        target.style.opacity = "0.5"
    }

})


document.body.addEventListener("htmx:afterRequest", function (event) {

    const target = event.detail.target

    if (target) {
        target.style.opacity = "1"
    }

})


// -------------------------------------
// Fehlerbehandlung
// -------------------------------------

document.body.addEventListener("htmx:responseError", function () {

    alert("Es ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut.")

})


// -------------------------------------
// ETF Suche (optional vorbereiteter Hook)
// -------------------------------------

function selectETF(symbol, name) {

    const input = document.getElementById("etf-search")
    const hidden = document.getElementById("etf-ticker")

    if (input) {
        input.value = name + " (" + symbol + ")"
    }

    if (hidden) {
        hidden.value = symbol
    }

    const dropdown = document.getElementById("search-results")

    if (dropdown) {
        dropdown.innerHTML = ""
    }

}


// -------------------------------------
// CSV Upload Anzeige
// -------------------------------------

function showUploadedFile(input) {

    if (!input.files.length) return

    const file = input.files[0]

    const label = document.getElementById("csv-file-name")

    if (label) {
        label.innerText = "Datei geladen: " + file.name
    }

}


// -------------------------------------
// Sparplan Eintrag hinzufügen (Frontend)
// -------------------------------------

function addSparplanRow() {

    const table = document.getElementById("sparplan-table")

    if (!table) return

    const row = document.createElement("tr")

    row.innerHTML = `
        <td><input type="date" name="startdatum"></td>
        <td><input type="date" name="enddatum"></td>
        <td><input type="number" step="0.01" name="rate"></td>
        <td><input type="number" min="1" max="28" name="tag"></td>
        <td>
            <button type="button" onclick="removeRow(this)">
                löschen
            </button>
        </td>
    `

    table.appendChild(row)

}


// -------------------------------------
// Zeile löschen
// -------------------------------------

function removeRow(button) {

    const row = button.closest("tr")

    if (row) {
        row.remove()
    }

}