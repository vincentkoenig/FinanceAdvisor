"""
make_icons.py - Erzeugt die PNG-Icons der App aus demselben Motiv wie public/icon.svg
(FT-Monogramm in Mint auf Waldgrün). Das Motiv besteht nur aus geraden Linien, darum
lässt es sich ohne SVG-Renderer als Vieleck zeichnen.

Aufruf (braucht Pillow, nur für Entwickler): python frontend/scripts/make_icons.py
Die erzeugten Dateien liegen in frontend/public und werden mit eingecheckt.
"""

from pathlib import Path

from PIL import Image, ImageDraw

PUBLIC = Path(__file__).resolve().parent.parent / 'public'
BACKGROUND = '#0f3d2b'
INK = '#86e3b4'

# Gleiche Pfade wie in icon.svg (Koordinaten im 512er-Raster, Motiv mittig)
F = [(120, 143), (238, 143), (238, 187), (170, 187), (170, 237), (229, 237), (229, 279), (170, 279), (170, 369), (120, 369)]
T = [(259, 143), (393, 143), (393, 187), (351, 187), (351, 369), (301, 369), (301, 187), (259, 187)]

# Name, Kantenlänge. Das Motiv liegt in der sicheren Zone runder Masken, darum taugt
# dasselbe Bild auch als "maskable"-Icon.
ICONS = [
    ('icon-192.png', 192),
    ('icon-512.png', 512),
    ('icon-maskable-512.png', 512),
    ('apple-touch-icon.png', 180),
]

SUPERSAMPLE = 4


def render(size):
    big = size * SUPERSAMPLE
    scale = big / 512
    image = Image.new('RGB', (big, big), BACKGROUND)
    draw = ImageDraw.Draw(image)
    for shape in (F, T):
        draw.polygon([(x * scale, y * scale) for x, y in shape], fill=INK)
    # Groß zeichnen und verkleinern ergibt glatte Kanten
    return image.resize((size, size), Image.LANCZOS)


if __name__ == '__main__':
    for name, size in ICONS:
        render(size).save(PUBLIC / name, optimize=True)
        print(f'{name} ({size}px)')
