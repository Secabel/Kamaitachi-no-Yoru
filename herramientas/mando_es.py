"""Imagen 'Mapa del mando' (BGD.PAC entrada 933, id 9005): sustituye los rotulos japoneses por espanol con los glifos latinos del juego.
Entrada: extraido/BGD_933_orig.tim (TIM 8 bpp 320x240 descomprimida). Salida: bytes del TIM nuevo (sin comprimir) + vista previa PNG.
Uso: python herramientas/mando_es.py [salida.png]"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glifos_latinos as GL, idioma as ID
AQUI = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(AQUI, '..', 'extraido', 'BGD_933_orig.tim')
W, H = 320, 240
FONDO, BLANCO, BORDE = 104, 255, 1
# (recuadro original x0,y0,x1,y1) , texto, icono (None/True: recorta el icono del original y lo pone tras el texto), anclaje ('l' fija el borde izquierdo, 'r' el derecho, 'c' el centro)
LABELS = [
    ((56, 15, 118, 32), 'Como', True, 'l'),             # 〇と同じ
    ((186, 15, 263, 32), 'Ocultar', None, 'l'),   # 文字を消す
    ((16, 35, 78, 52), 'Como', True, 'l'),              # ✕と同じ
    ((226, 35, 303, 52), 'Oscurecer', None, 'r'),       # 画面を暗く
    ((222, 86, 299, 103), 'Mapa', None, 'r'),           # 移動マップ
    ((125, 102, 215, 118), 'Elegir', None, 'c'),        # 選択肢の移動
    ((233, 141, 305, 158), 'Aceptar', None, 'l'),       # 読む・決定
    ((14, 151, 103, 168), 'Mover cursor', None, 'l'),   # カーソル移動
    ((196, 161, 272, 178), 'Cancelar', None, 'r'),      # キャンセル
    ((86, 181, 148, 198), 'Como', True, 'r'),           # □と同じ
    ((156, 181, 218, 198), 'Atrás', None, 'c'),        # 読み戻し
]
if ID.LANG == 'en':
    _EN = ['Same as', 'Hide text', 'Same as', 'Dim screen', 'Map', 'Choose', 'Confirm', 'Move cursor', 'Cancel', 'Same as', 'Back']
    LABELS = [(r, t, ic, anc) for (r, _o, ic, anc), t in zip(LABELS, _EN)]
MARGEN = 3
def leer_tim(d):
    p = 8; n = struct.unpack_from('<I', d, p)[0]; pal = d[p:p + n]; p += n
    n2 = struct.unpack_from('<I', d, p)[0]; assert struct.unpack_from('<4H', d, p + 4) == (0, 0, 160, 240)
    return d[:p + 12], bytearray(d[p + 12:p + n2])
ESP = 6                                  # avance del espacio entre palabras (el glifo ' ' mide 11 px)
def _av(c, g): return ESP if c == ' ' else g[c][0] + 1
def ancho_texto(t, g): return sum(_av(c, g) for c in t) - 1
def dibujar_texto(px, t, g, x, y):
    for c in t:
        w, h, gp = g[c]
        for yy in range(h):
            for xx in range(w):
                v = gp[yy * w + xx]
                if v and 0 <= x + xx < W and 0 <= y + yy < H: px[(y + yy) * W + x + xx] = BORDE if v == 1 else BLANCO
        x += _av(c, g)
def construir(orig=None):
    d = open(ORIG, 'rb').read() if orig is None else orig
    cab, px = leer_tim(d); ref = bytearray(px); g = GL.todos(); fallos = []
    for (x0, y0, x1, y1), t, ic, anc in LABELS:
        tw = ancho_texto(t, g); iw = 0
        if ic:
            ico = [[ref[y * W + x] for x in range(x0 + 2, x0 + 19)] for y in range(y0, y1 + 1)]; iw = 3 + 17   # 17 col: la 18.a traia un resto negro del 1.er caracter japones (linea vertical junto al icono)
        need = tw + iw + 2 * MARGEN
        ancho = x1 - x0 + 1
        nx0, nx1 = x0, x1
        if need > ancho:
            extra = need - ancho
            if anc == 'l': nx1 = x1 + extra
            elif anc == 'r': nx0 = x0 - extra
            else: nx0 = x0 - extra // 2; nx1 = x1 + (extra - extra // 2)
        for y in range(y0, y1 + 1):
            for x in range(nx0, nx1 + 1): px[y * W + x] = FONDO
        ty = y0 + 1; tx = nx0 + (nx1 - nx0 + 1 - tw - iw) // 2
        dibujar_texto(px, t, g, tx, ty)
        if ic:
            ix = tx + tw + 3
            for yy, fila in enumerate(ico):
                for xx, v in enumerate(fila): px[(y0 + yy) * W + ix + xx] = v
        if nx1 - nx0 + 1 < tw + iw: fallos.append(t)
    return cab + bytes(px), fallos
def a_png(tim, ruta):
    from PIL import Image
    p = 8; n = struct.unpack_from('<I', tim, p)[0]; pal = [struct.unpack_from('<H', tim, p + 12 + 2 * i)[0] for i in range(256)]
    px = tim[p + n + 12:p + n + 12 + W * H]
    c = lambda v: (((v & 31) * 255) // 31, (((v >> 5) & 31) * 255) // 31, (((v >> 10) & 31) * 255) // 31)
    im = Image.new('RGB', (W, H)); im.putdata([c(pal[b]) for b in px]); im.resize((W * 3, H * 3), Image.NEAREST).save(ruta)
if __name__ == '__main__':
    tim, fallos = construir(); print('TIM', len(tim), 'B', 'fallos', fallos)
    if len(sys.argv) > 1: a_png(tim, sys.argv[1])
