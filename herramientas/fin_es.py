"""Marcas de fin de capitulo/juego (BGD.PAC id 9205 = 終, id 9209 = 完): se sustituyen por 'Fin' con los glifos latinos (escala 2).
Entrada: TIM 8 bpp 320x240 sin comprimir. fondo/blanco = indices de paleta. Uso: python herramientas/fin_es.py in.tim out.png"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glifos_latinos as GL
W, H = 320, 240
import idioma as ID
def poner(d, texto='Fin' if ID.LANG == 'es' else 'End', escala=2, fondo=None, blanco=None, caja=None):
    d = bytearray(d); p = 8; n = struct.unpack_from('<I', d, p)[0]; pal = struct.unpack_from('<256H', d, p + 12); p += n
    n2, x, y, w, h = struct.unpack_from('<IHHHH', d, p); assert (w * 2, h) == (W, H)
    b0 = p + 12
    if fondo is None: fondo = d[b0]                    # esquina superior izquierda = fondo
    if blanco is None: blanco = max(range(256), key=lambda i: (pal[i] & 31) + ((pal[i] >> 5) & 31) + ((pal[i] >> 10) & 31))
    if caja is None:                                     # caja del rotulo original: pixeles distintos del fondo
        xs = [i % W for i in range(W * H) if d[b0 + i] != fondo]; ys = [i // W for i in range(W * H) if d[b0 + i] != fondo]
        caja = (min(xs), min(ys), max(xs), max(ys))
    x0, y0, x1, y1 = caja
    for yy in range(y0, y1 + 1):
        for xx in range(x0, x1 + 1): d[b0 + yy * W + xx] = fondo
    g = GL.todos(); tw = sum(g[c][0] + 1 for c in texto) - 1; th = max(g[c][1] for c in texto)
    cx = x1 - (tw * escala) if False else (x0 + x1) // 2 - tw * escala // 2; cy = (y0 + y1) // 2 - th * escala // 2
    x = cx
    for c in texto:
        gw, gh, gp = g[c]
        for yy in range(gh):
            for xx in range(gw):
                if gp[yy * gw + xx] > 1:
                    for sy in range(escala):
                        for sx in range(escala):
                            px, py = x + xx * escala + sx, cy + yy * escala + sy
                            if 0 <= px < W and 0 <= py < H: d[b0 + py * W + px] = blanco
        x += (gw + 1) * escala
    return bytes(d), caja
if __name__ == '__main__':
    sys.path.insert(0, os.path.expanduser('~/w')); import tim
    o, caja = poner(open(sys.argv[1], 'rb').read()); print(caja); tim.png(o, sys.argv[2])
