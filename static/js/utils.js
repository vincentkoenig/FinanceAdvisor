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