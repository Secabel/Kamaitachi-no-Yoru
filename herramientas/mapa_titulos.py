"""Banco de titulos de escena / ramas / finales (pantalla de grafico y cabecera): bloque LZS del ejecutable en 0x800680b8.
Bloque descomprimido: [3][(off,tam)x3] + seccion A (graficos) + B (graficos) + C (263 titulos: tabla u32 BE de desplazamientos + cadenas 0-terminadas).
Aqui se sustituye C por traduccion/mapa_textos.tsv (cadenas de 1 byte/letra con bandera 0x01 para el impresor de menus) y se recomprime.
aplicar(exe_bytearray) -> lineas de informe; python3 mapa_titulos.py  -> informe de anchos."""
import os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lzs, layout as LY, sce_pac as SP, menus_exe as ME, menu1b
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
BASE = 0x80010000 - 0x800
LZS_DIR = 0x800680bb; LZS_LEN = 0x232f          # flujo tras 'LZS' (3 bytes) y su longitud (inmediata de 0x80019d04)
HOOK_LEN = 0x80019d04
N = 263; ANCHO_MAX = 300
LIBRES = []          # huecos de RAM del exe que quedan libres tras reempaquetar (inicio, fin)
TAGS = {'-': '', 'B': '{c2}Rama{c0}: ', 'F': '{ss}{c7}Final{c0}: ', 'K': '{ss}{c7}Fin{c0}: ', 'C': 'Culpable: '}
def cargar():
    d = {}
    for ln in open(os.path.join(RAIZ, 'traduccion', 'mapa_textos.tsv'), encoding='utf-8').read().splitlines():
        if not ln.strip() or ln.startswith('#'): continue
        i, t, x = ln.split('\t'); d[int(i)] = TAGS[t] + x
    assert sorted(d) == list(range(N)), 'faltan indices'
    return d
def ancho(txt):
    w = 0
    for tk in re.findall(r'\{[^}]*\}|.', txt):
        if tk.startswith('{'):
            c = tk[1:-1]
            if re.fullmatch(r'n\d', c): w += ME.NOMBRE_PX
            elif c == 'ss': w += 6
            elif c == 's8': w += 8
        elif tk in SP.MAPA: w += LY.ancho(tk)
        else: w += 16
    return w
def seccion_c(tr, mp):
    tab = bytearray(4 * N); cuerpo = bytearray()
    for i in range(N):
        struct.pack_into('>I', tab, 4 * i, 4 * N + len(cuerpo)); cuerpo += ME.codificar1(tr[i], mp) + b'\0'
    return bytes(tab + cuerpo)
def aplicar(exe):
    mp = menu1b.construir([(c, v) for c, v in SP.MAPA.items() if not (c.isascii() and c.isalnum())])[3]
    o = lambda a: a - 0x80010000 + 0x800
    d = lzs.descomprimir(bytes(exe[o(LZS_DIR):o(LZS_DIR) + LZS_LEN]))
    cnt, = struct.unpack_from('>I', d, 0); assert cnt == 3
    (oa, sa), (ob, sb), (oc, sc) = [struct.unpack_from('>II', d, 4 + 8 * k) for k in range(3)]
    assert (oa, sa, ob, sb, oc, sc) == (28, 1430, 1462, 4298, 5764, 8460), 'banco distinto'
    C = seccion_c(cargar(), mp)
    nuevo = bytearray(d[:oc]); nuevo += C; nuevo += bytes((-len(nuevo)) % 4)
    struct.pack_into('>II', nuevo, 4 + 16, oc, len(C))
    comp = lzs.comprimir(bytes(nuevo)); assert lzs.descomprimir(comp) == bytes(nuevo)
    assert len(comp) <= LZS_LEN, 'no cabe el banco comprimido: %d > %d' % (len(comp), LZS_LEN)
    exe[o(LZS_DIR):o(LZS_DIR) + LZS_LEN] = comp + bytes(LZS_LEN - len(comp)); LIBRES.append((LZS_DIR + len(comp), LZS_DIR + LZS_LEN))
    ins = struct.unpack_from('<I', exe, o(HOOK_LEN))[0]; assert ins == 0x24060000 | LZS_LEN
    struct.pack_into('<I', exe, o(HOOK_LEN), 0x24060000 | len(comp))
    return ['titulos: C %d B (antes %d), bloque %d B, comprimido %d B de %d' % (len(C), sc, len(nuevo), len(comp), LZS_LEN)]
FIN_BASE = 0x80067914; FIN_LEN = 0x76a; FIN_X_NOMBRE = (0x80015350, 0x80015364); X_NOMBRE = 0x2c; FIN_ANCHO_MAX = 274
def cargar_finales():
    d = {}
    for ln in open(os.path.join(RAIZ, 'traduccion', 'finales_textos.tsv'), encoding='utf-8').read().splitlines():
        if not ln.strip() or ln.startswith('#'): continue
        i, t = ln.split('\t'); d[int(i)] = t
    assert sorted(d) == list(range(46)); return d
def aplicar_finales(exe):
    """lista de finales: bloque [46 x (desp. prefijo, desp. nombre)] u32 BE + cadenas, cargado por 0x800151a0 con longitud 0x76a; nombres a x=X_NOMBRE"""
    o = lambda a: a - 0x80010000 + 0x800
    mp = menu1b.construir([(c, v) for c, v in SP.MAPA.items() if not (c.isascii() and c.isalnum())])[3]
    tr = cargar_finales(); tab = bytearray(8 * 46); cuerpo = bytearray(); cache = {}
    def poner(b):
        if b not in cache: cache[b] = 8 * 46 + len(cuerpo); cuerpo.extend(b + b'\0')
        return cache[b]
    for i in range(46):
        struct.pack_into('>II', tab, 8 * i, poner(ME.codificar1('%d.' % (i + 1), mp)), poner(ME.codificar1(tr[i], mp)))
    blk = bytes(tab + cuerpo); assert len(blk) <= FIN_LEN, 'lista de finales: %d > %d' % (len(blk), FIN_LEN)
    exe[o(FIN_BASE):o(FIN_BASE) + FIN_LEN] = blk + bytes(FIN_LEN - len(blk)); LIBRES.append((FIN_BASE + len(blk), FIN_BASE + FIN_LEN))
    for a in FIN_X_NOMBRE:
        w = struct.unpack_from('<I', exe, o(a))[0]; assert w == 0x24040000 | 0x4d, hex(a)
        struct.pack_into('<I', exe, o(a), 0x24040000 | X_NOMBRE)
    return ['finales: bloque %d B de %d' % (len(blk), FIN_LEN)]
if __name__ == '__main__':
    tr = cargar(); mal = 0
    for i, t in tr.items():
        w = ancho(t)
        if w > ANCHO_MAX: mal += 1; print(i, w, t)
    print('anchos > %d: %d de %d' % (ANCHO_MAX, mal, N))
    for i, t in cargar_finales().items():
        if ancho(t) > FIN_ANCHO_MAX: print('final', i, ancho(t), t)
