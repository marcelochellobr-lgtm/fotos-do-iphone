"""Gera icone.ico: iPhone com uma foto na tela e o selo verde de 'conferido'.
Desenhado em 1024 px e reduzido, para as bordas saírem lisas em todos os tamanhos."""
import os
from PIL import Image, ImageDraw

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# fundo: quadrado arredondado em degradê azul
fundo = Image.new("RGBA", (S, S))
fd = ImageDraw.Draw(fundo)
for y in range(S):
    t = y / S
    fd.line([(0, y), (S, y)], fill=(int(40 + 20 * t), int(120 - 50 * t), int(235 - 60 * t), 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=220, fill=255)
img.paste(fundo, (0, 0), mask)

# corpo do iPhone
x0, y0, x1, y1 = 300, 120, 724, 904
d.rounded_rectangle([x0, y0, x1, y1], radius=80, fill=(24, 24, 28, 255))
# tela com a foto (céu, sol, montanhas)
tx0, ty0, tx1, ty1 = x0 + 26, y0 + 26, x1 - 26, y1 - 26
tela = Image.new("RGBA", (tx1 - tx0, ty1 - ty0))
td = ImageDraw.Draw(tela)
w, h = tela.size
for y in range(h):
    t = y / h
    td.line([(0, y), (w, y)], fill=(int(120 + 100 * t), int(190 + 30 * t), 255, 255))
td.ellipse([w * 0.58, h * 0.16, w * 0.86, h * 0.16 + w * 0.28], fill=(255, 205, 70, 255))
td.polygon([(0, h * 0.78), (w * 0.38, h * 0.42), (w * 0.72, h * 0.80), (0, h)], fill=(46, 140, 90, 255))
td.polygon([(w * 0.30, h), (w * 0.70, h * 0.55), (w, h * 0.82), (w, h)], fill=(30, 105, 70, 255))
td.rectangle([0, h * 0.86, w, h], fill=(30, 105, 70, 255))
tmask = Image.new("L", tela.size, 0)
ImageDraw.Draw(tmask).rounded_rectangle([0, 0, w - 1, h - 1], radius=58, fill=255)
img.paste(tela, (tx0, ty0), tmask)
# ilha dinâmica
d.rounded_rectangle([462, y0 + 52, 562, y0 + 92], radius=20, fill=(24, 24, 28, 255))

# selo verde com ✓ (canto inferior direito)
cx, cy, r = 742, 770, 170
d.ellipse([cx - r - 22, cy - r - 22, cx + r + 22, cy + r + 22], fill=(255, 255, 255, 255))
d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(40, 168, 107, 255))
d.line([(cx - 82, cy + 4), (cx - 22, cy + 66), (cx + 90, cy - 62)], fill=(255, 255, 255, 255), width=46, joint="curve")
for px, py in [(cx - 82, cy + 4), (cx + 90, cy - 62)]:
    d.ellipse([px - 23, py - 23, px + 23, py + 23], fill=(255, 255, 255, 255))

aqui = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
img.resize((256, 256), Image.LANCZOS).save(
    os.path.join(aqui, "icone.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("ok")
