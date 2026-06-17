// Theme beim Laden anwenden
const savedTheme = localStorage.getItem('theme') || 'dark'
document.documentElement.setAttribute('data-theme', savedTheme)

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme')
    const newTheme = current === 'dark' ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', newTheme)
    localStorage.setItem('theme', newTheme)
}