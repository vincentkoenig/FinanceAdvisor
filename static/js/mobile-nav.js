/**
 * mobile-nav.js - Steuert das aufklappende "Mehr"-Menü der mobilen
 * Bottom Navigation (Watchlist, Einstellungen, Theme-Toggle, Logout).
 */

function toggleMoreMenu() {
    const menu = document.getElementById('more-menu')
    if (menu.style.display === 'none') {
        menu.style.display = 'block'
    } else {
        menu.style.display = 'none'
    }
}