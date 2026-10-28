// Maskiert Text, bevor er per innerHTML in die Seite eingefügt wird.
// Ohne das würde z.B. ein Kategoriename wie <img src=x onerror=...>
// als echtes HTML ausgeführt (XSS). Für alle Werte nutzen, die vom
// Nutzer, vom Server oder vom LLM stammen.
function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
}

// Bereitet einen Wert als Argument für einen Inline-Handler wie
// onclick="showAssetDetail(1, ...)" vor. JSON.stringify macht daraus
// einen gültigen JavaScript-String (auch bei Apostrophen wie in
// "McDonald's"), escapeHtml schützt das umgebende HTML-Attribut.
function jsArg(value) {
    return escapeHtml(JSON.stringify(value))
}

// Wandelt Markdown aus LLM-Antworten in HTML um und entfernt dabei
// alles Gefährliche (Skripte, Event-Handler) über DOMPurify.
function renderMarkdown(text) {
    return DOMPurify.sanitize(marked.parse(text ?? ''))
}

// Generiert für eine gegebene Anzahl Elemente gleichmäßig verteilte,
// klar unterscheidbare Farben über das HSL-Farbrad - funktioniert
// für beliebig viele Elemente, ohne dass sich Farben wiederholen.
// Wird für Donut Charts genutzt (Portfolio-Allokation, Budget-Ausgaben).
function generateColors(count) {
    const colors = []
    for (let i = 0; i < count; i++) {
        const hue = Math.round((360 / count) * i)
        colors.push(`hsl(${hue}, 65%, 55%)`)
    }
    return colors
}