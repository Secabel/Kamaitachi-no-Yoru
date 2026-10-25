"""Pantalla de entrada de nombres (protagonista / pareja / culpable) y normalizador de respuestas del culpable.
- Cabeceras 'Nombre del ...' (0x80011fb4/fc4/fd0) y etiquetas de boton (0x8007932c/34) en espanol, con x recalculado.
- Normalizador 0x800432ec: la respuesta tecleada (codigos de ancho completo de las letras latinas) se compara con una lista de alias POR PERSONAJE;
  los alias japoneses (kana) se sustituyen por alias latinos en minusculas y la comparacion (0x80044d88) pasa a ignorar mayusculas.
  Si coincide, el nombre canonico (texto del juego con codigos de historia) sustituye a la respuesta.
- Menus de grupo (quien es el culpable?) en espanol.
aplicar(exe, libres) -> informe.   libres: lista de (inicio, fin) de RAM libres extra (cola del banco LZS / lista de finales)."""
import os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
import layout as LY, sce_pac as SP, idioma as ID
BASE = 0x80010000 - 0x800
def o(a): return a - BASE
R1 = (0x80011fb4, 0x8001249c)             # vocabulario japones (se reutiliza entero)
# (alias en minusculas ASCII, nombre canonico) por caso 0..11 (indice de la tabla de saltos 0x800129ac)
CASOS = [
    (['mikimoto', 'yosuke', 'mikimotoyosuke', 'fotografo', 'barbudo'], 'Mikimoto'),
    (['tanaka', 'ichiro', 'tanakaichiro'], 'Tanaka'),
    (['kobayashi', 'jiro', 'kobayashijiro', 'dueno', 'jefe', 'tio'], 'Kobayashi'),
    (['kyoko', 'kobayashikyoko', 'duena', 'tia', 'senora'], 'Kyoko'),
    (['kayama', 'seiichi', 'kayamaseiichi', 'presidente', 'osaka', 'marido'], 'Kayama'),
    (['haruko', 'kayamaharuko', 'esposa', 'bella'], 'Haruko'),
    (['toshio', 'kubota', 'kubotatoshio', 'alto', 'chonmage'], 'Toshio'),
    (['midori', 'shinozaki', 'shinozakimidori', 'coleta'], 'Midori'),
    (['aki', 'kawamura', 'kawamuraaki', 'akichan'], 'Aki'),
    (['kanako', 'watase', 'watasekanako', 'kanakochan'], 'Kanako'),
    (['keiko', 'kitano', 'kitanokeiko', 'keikochan'], 'Keiko'),
    (['ol', 'chicas', 'oficinistas', 'lastres', 'tres'], None),      # el canonico del grupo es la cadena de menu 0x80012418
]
GRUPOS = {0x80012418: 'Las tres chicas', 0x80012424: 'Kayama (marido)', 0x80012430: 'Midori u otros', 0x80012440: 'Otro personaje', 0x80012454: 'Ningún personaje',
          0x80012464: 'Cualquier otro personaje', 0x80012478: 'Una de las tres chicas', 0x8001248c: 'Alguien ya muerto',
          0x800793cc: 'Mikimoto', 0x800793d4: 'Tanaka', 0x800793dc: 'Toshio', 0x800793e4: 'Haruko'}
CAB = {0x80011fb4: 'Nombre del protagonista', 0x80011fc4: 'Nombre de la pareja', 0x80011fd0: 'Nombre del culpable'}
ET = {0x8007932c: ('Borra', 0x8487), 0x80079334: ('Fin', 0x8486)}       # texto + codigo de icono (x, triangulo)
if ID.LANG == 'en':
    CASOS = [
        (['mikimoto', 'yosuke', 'mikimotoyosuke', 'photographer', 'bearded'], 'Mikimoto'),
        (['tanaka', 'ichiro', 'tanakaichiro'], 'Tanaka'),
        (['kobayashi', 'jiro', 'kobayashijiro', 'owner', 'boss', 'uncle'], 'Kobayashi'),
        (['kyoko', 'kobayashikyoko', 'landlady', 'aunt', 'ownerswife'], 'Kyoko'),
        (['kayama', 'seiichi', 'kayamaseiichi', 'president', 'osaka', 'husband'], 'Kayama'),
        (['haruko', 'kayamaharuko', 'wife', 'beauty'], 'Haruko'),
        (['toshio', 'kubota', 'kubotatoshio', 'tall', 'parttimer'], 'Toshio'),
        (['midori', 'shinozaki', 'shinozakimidori', 'ponytail'], 'Midori'),
        (['aki', 'kawamura', 'kawamuraaki', 'akichan'], 'Aki'),
        (['kanako', 'watase', 'watasekanako', 'kanakochan'], 'Kanako'),
        (['keiko', 'kitano', 'kitanokeiko', 'keikochan'], 'Keiko'),
        (['ol', 'girls', 'officeladies', 'threegirls', 'three'], None),
    ]
    GRUPOS = {0x80012418: 'The three girls', 0x80012424: 'Kayama (husband)', 0x80012430: 'Midori or others', 0x80012440: 'Another character', 0x80012454: 'Not a character',
              0x80012464: 'Any other character', 0x80012478: 'One of the three girls', 0x8001248c: 'Someone already dead',
              0x800793cc: 'Mikimoto', 0x800793d4: 'Tanaka', 0x800793dc: 'Toshio', 0x800793e4: 'Haruko'}
    CAB = {0x80011fb4: "Protagonist's name", 0x80011fc4: "Partner's name", 0x80011fd0: "Culprit's name"}
    ET = {0x8007932c: ('Erase', 0x8487), 0x80079334: ('Done', 0x8486)}
def cod(s):
    out = bytearray()
    for ch in s: c = SP.MAPA[ch]; out += bytes([c >> 8, c & 255])
    return bytes(out)
def ancho(s): return sum(LY.ancho(ch) for ch in s)
def _sitios(exe, rangos):
    """{valor: [(off_lui, off_addiu)]} de pares lui/addiu (hi 0x8001 o 0x8008) hacia los rangos"""
    sit = {}
    for p in range(0x800, 0x800 + (0x8006AB90 - 0x80010000), 4):
        w = struct.unpack_from('<I', exe, p)[0]
        if w >> 26 != 0x0f: continue
        rt = (w >> 16) & 31; hi = w & 0xffff
        if hi not in (0x8001, 0x8008): continue
        for k in range(1, 8):
            q = p + 4 * k; w2 = struct.unpack_from('<I', exe, q)[0]
            if w2 >> 26 == 9 and ((w2 >> 21) & 31) == rt:
                lo = w2 & 0xffff; lo = lo - 0x10000 if lo >= 0x8000 else lo; v = (hi << 16) + lo
                if any(a <= v < b for a, b in rangos): sit.setdefault(v, []).append((p, q))
                break
    return sit
def _repuntar(exe, sit, v, nd):
    for p, q in sit[v]:
        wl = struct.unpack_from('<I', exe, p)[0]; wa = struct.unpack_from('<I', exe, q)[0]
        struct.pack_into('<I', exe, p, (wl & 0xffff0000) | (((nd + 0x8000) >> 16) & 0xffff)); struct.pack_into('<I', exe, q, (wa & 0xffff0000) | (nd & 0xffff))
def fw(s):
    out = bytearray()
    for ch in s:
        c = 0x8281 + ord(ch) - 97 if ch.islower() else SP.MAPA[ch]
        out += bytes([c >> 8, c & 255])
    return bytes(out)
# comparacion sin distinguir mayusculas/minusculas de ancho completo (0x82 0x60..0x79 -> 0x82 0x81..0x9a), sustituye a 0x80044d88(a0=palabra, a1=entrada) -> 1 si iguales
import menu1b
menu1b.R.setdefault('t5', 13)
CMP_ORIG = 0x80044d88
def prog_cmp():
    I, br, jj, NOP = menu1b.I, menu1b.br, menu1b.jj, menu1b.NOP
    return [
        'CMP:', I(0x09, 'zero', 't0', 0), I(0x09, 'zero', 't1', 0),
        'LOOP:', I(0x24, 'a0', 'v0', 0), I(0x09, 'a0', 'a0', 1), I(0x24, 'a1', 'v1', 0), I(0x09, 'a1', 'a1', 1),
        I(0x09, 'v0', 't4', 0), I(0x09, 'v1', 't5', 0),
        I(0x09, 't0', 't2', -0x82), br(5, 't2', 'zero', 'F1'), NOP,
        I(0x09, 'v0', 't3', -0x60), I(0x0b, 't3', 't3', 0x1a), br(4, 't3', 'zero', 'F1'), NOP, I(0x09, 'v0', 'v0', 0x21),
        'F1:', I(0x09, 't1', 't2', -0x82), br(5, 't2', 'zero', 'F2'), NOP,
        I(0x09, 'v1', 't3', -0x60), I(0x0b, 't3', 't3', 0x1a), br(4, 't3', 'zero', 'F2'), NOP, I(0x09, 'v1', 'v1', 0x21),
        'F2:', br(4, 'v0', 'zero', 'END0'), NOP, br(4, 'v1', 'zero', 'RET0'), NOP, br(5, 'v0', 'v1', 'RET0'), NOP,
        I(0x09, 't4', 't0', 0), I(0x09, 't5', 't1', 0), jj(2, 'LOOP'), NOP,
        'END0:', br(5, 'v1', 'zero', 'RET0'), NOP, I(0x09, 'zero', 'v0', 1), menu1b.Rr('ra', 'zero', 'zero', 0, 8), NOP,
        'RET0:', I(0x09, 'zero', 'v0', 0), menu1b.Rr('ra', 'zero', 'zero', 0, 8), NOP]
class Libre:
    def __init__(s, rangos): s.r = [[a, b] for a, b in rangos]
    def pedir(s, n, alin=4):
        for r in s.r:
            a = (r[0] + alin - 1) // alin * alin
            if a + n <= r[1]: r[0] = a + n; return a
        raise AssertionError('sin sitio para %d B' % n)
    def resto(s): return sum(b - a for a, b in s.r)
def aplicar(exe, libres):
    rep = []; hueco = Libre([R1] + list(libres))
    sit = _sitios(exe, [R1, (0x80079300, 0x800793f0)])
    # 0) tabla de casos del normalizador
    tab = list(struct.unpack_from('<12I', exe, o(0x800129ac)))
    ini = sorted(tab); fin_casos = 0x80043b60
    def caso_de(a):
        for k, t in enumerate(tab):
            nx = [x for x in ini if x > t]; end = nx[0] if nx else fin_casos
            if t <= a < end: return k
    porcaso = {k: [] for k in range(12)}
    for v, lst in sit.items():
        for p, q in lst:
            a = 0x80010000 + p - 0x800
            if 0x80043344 <= a < fin_casos: porcaso[caso_de(a)].append((p, q, v))
    for k in porcaso: porcaso[k].sort()
    # 1) limpiar el vocabulario japones y reasignar
    exe[o(R1[0]):o(R1[1])] = bytes(R1[1] - R1[0])
    nuevos = {}            # cadena (bytes) -> direccion
    def poner(b):
        if b not in nuevos: a = hueco.pedir(len(b) + 2, 2); exe[o(a):o(a) + len(b)] = b; nuevos[b] = a
        return nuevos[b]
    dummy = poner(b'\xff\xff')
    grupo = {v: poner(cod(t)) for v, t in GRUPOS.items()}
    for k, (alias, canon) in enumerate(CASOS):
        sitios = porcaso[k]; assert len(sitios) - 1 >= len(alias), (k, len(sitios), len(alias))
        for j, (p, q, v) in enumerate(sitios):
            if j == len(sitios) - 1: nd = grupo[0x80012418] if canon is None else poner(cod(canon))
            else: nd = poner(fw(alias[j])) if j < len(alias) else dummy
            _repuntar_uno(exe, p, q, nd)
    # 2) menus de grupo (punteros apilados en 0x80043f5c..0x80044040) y cabeceras / etiquetas
    for v, nd in grupo.items():
        for p, q in sit.get(v, []):
            a = 0x80010000 + p - 0x800
            if a >= 0x80043f00 or v in (0x800793cc, 0x800793d4, 0x800793dc, 0x800793e4): _repuntar_uno(exe, p, q, nd)
    cab = {}
    for v, t in CAB.items():
        nd = poner(cod(t)); cab[v] = ancho(t)
        for p, q in sit[v]: _repuntar_uno(exe, p, q, nd)
    ws = sorted(cab.values())
    x0 = int(round(160 - (cab[0x80011fb4]) / 2)); x12 = int(round(160 - (cab[0x80011fc4] + cab[0x80011fd0]) / 4))
    for a, x in ((0x800429a8, x0), (0x8004299c, x12)):
        w = struct.unpack_from('<I', exe, o(a))[0]; assert w == 0x24040070, hex(a); struct.pack_into('<I', exe, o(a), 0x24040000 | max(4, x))
    for v, (t, icono) in ET.items():
        nd = poner(cod(t) + bytes([icono >> 8, icono & 255]))
        for p, q in sit[v]: _repuntar_uno(exe, p, q, nd)
    for a, x in ((0x800429dc, 20), (0x800429f4, 246)):
        w = struct.unpack_from('<I', exe, o(a))[0]; assert w >> 16 == 0x2404, hex(a); struct.pack_into('<I', exe, o(a), 0x24040000 | x)
    # 2b) cabeceras y etiquetas con avance VARIABLE (el original usaba avance fijo de 16 px por caracter: 'addiu a3,zero,0x10')
    for a in (0x800429D8, 0x800429F0, 0x80042A08):
        w = struct.unpack_from('<I', exe, o(a))[0]; assert w == 0x24070010, hex(a); struct.pack_into('<I', exe, o(a), 0x24070000)
    # 3) comparacion sin distinguir mayusculas
    prog, lab = menu1b.asm(prog_cmp(), 0)
    n = 4 * len(prog); base_c = hueco.pedir(n, 4)
    prog, lab = menu1b.asm(prog_cmp(), base_c)
    for k, wd in enumerate(prog): struct.pack_into('<I', exe, o(base_c) + 4 * k, wd)
    assert struct.unpack_from('<II', exe, o(CMP_ORIG)) == (0x90820000, 0x24840001), 'comparador distinto'
    struct.pack_into('<II', exe, o(CMP_ORIG), (2 << 26) | ((lab['CMP'] >> 2) & 0x3ffffff), 0)
    rep.append('nombres: %d cadenas nuevas; sobran %d B; cabeceras x=%d/%d' % (len(nuevos), hueco.resto(), x0, x12))
    return rep
def _repuntar_uno(exe, p, q, nd):
    wl = struct.unpack_from('<I', exe, p)[0]; wa = struct.unpack_from('<I', exe, q)[0]
    struct.pack_into('<I', exe, p, (wl & 0xffff0000) | (((nd + 0x8000) >> 16) & 0xffff)); struct.pack_into('<I', exe, q, (wa & 0xffff0000) | (nd & 0xffff))
