"""Traduccion de los textos del ejecutable (menus, perfiles, ayuda, tarjeta de memoria, fin de juego). Uso: python3 menus_exe.py [informe]
Las cadenas JP viven en 0x80010000..0x800118e4 y las referencian pares lui/addiu del codigo. Aqui se reempaquetan (traduccion/exe_textos.tsv:
addr<TAB>texto, '|' = salto 'rr', {codigos} literales) en los mismos huecos, se reparchean los addiu y se recentran las cadenas que el original centraba
(llamadas jal 0x80038658(x, y, texto, 0)). aplicar(exe_bytearray) -> informe."""
import os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
import layout as LY, sce_pac as SP, glifos_latinos as GL, menu1b
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
BASE = 0x80010000 - 0x800
POOLS = [(0x80010000, 0x80011378), (0x8001153C, 0x800118E4)]      # huecos reempaquetables (cadenas JP/depuracion)
EXTRA = (0x80077560, 0x80077560 + 3400)    # 3.4 KB a cero en 10 savestates y sin referencias en el codigo (desbordamiento)
SITIOS_IN = (0x80010000, 0x800118E4)
PRINT = 0x80038658
NOMBRE_PX = 64; ICONO_PX = 16
BOTONES = {0x800110C8, 0x800110D4, 0x800110E4, 0x80010DF4, 0x80010E08}     # textos centrados sobre un boton (titulo, tarjeta 1/2)
AJUSTE_X = {0x800118CC: -5}    # correcciones finas (px) tras el recentrado: 'Guardado.' ~5 px y 'Comprobando' ~10 px a la izquierda (pedido del usuario)
CENTROS = {0x800110C8: 62, 0x800110D4: 157, 0x800110E4: 250}    # centro (px) de las placas del titulo (medido en emulador)
SPC, SPH = 0x8488, 0x8489      # ANTES 0x848B/0x8483: 0x8483 es el ICONO DE FIN DE PAGINA y 0x848B otro glifo que dibuja el juego (0x800380ec); ahora codigos sin uso (ni texto ni codigo del juego).
# el impresor de menus avanza el espacio 0x8140 solo ~3 px (medido): se usan 2 huecos de glifo en blanco (11 y 5 px; avance 12 y 6)
def aw(ch): return 6 if ch == '~' else LY.ancho(ch)
def o(a): return a - BASE
def jp_ancho(b):
    """ancho en px de una cadena JP (bytes): glifos SJIS de 2 bytes; los ASCII son codigos. Devuelve el maximo de las lineas ('rr')."""
    mx = 0; cur = 0; i = 0
    while i < len(b):
        c = b[i]
        if 0x81 <= c <= 0x9f or 0xe0 <= c <= 0xfc:
            code = (c << 8) | b[i+1]; i += 2
            ix = GL.indice(code); cur += (GL._gl[ix][0] + 1) if ix is not None and ix >= 0 else 14
        elif c == 0x72 and i + 1 < len(b) and b[i+1] == 0x72: mx = max(mx, cur); cur = 0; i += 2
        else: i += 1
    return max(mx, cur)
def cargar_tsv(ruta=None):
    ruta = ruta or os.path.join(RAIZ, 'traduccion', 'exe_textos.tsv'); d = {}
    for ln in open(ruta, encoding='utf-8').read().splitlines():
        if not ln.strip() or ln.startswith('#'): continue
        k, v = ln.split('\t', 1); d[int(k, 16)] = v
    return d
def codificar(txt):
    """-> (bytes, [anchos de linea px])"""
    out = bytearray(); anchos = []; cur = 0; k = 0
    while k < len(txt):
        ch = txt[k]
        if ch == '{':
            j = txt.index('}', k); c = txt[k+1:j]; k = j + 1
            out += c.encode('ascii')
            if re.fullmatch(r'n\d', c): cur += NOMBRE_PX
            continue
        k += 1
        if ch == '|': out += b'rr'; anchos.append(cur); cur = 0; continue
        if ch in (' ', '~'): c = SPC if ch == ' ' else SPH; out += bytes([c >> 8, c & 255]); cur += aw(ch); continue
        if ch in SP.MAPA: c = SP.MAPA[ch]; out += bytes([c >> 8, c & 255]); cur += LY.ancho(ch); continue
        b = ch.encode('cp932'); out += b; cur += ICONO_PX          # iconos de boton (х ф А у...) tal cual
    anchos.append(cur); return bytes(out), anchos
def codificar1(txt, mp):
    """igual que codificar pero 1 byte por letra (formato de menu1b); los codigos de control/iconos con escape 0x02"""
    out = bytearray([1]); k = 0
    while k < len(txt):
        ch = txt[k]
        if ch == '{':
            j = txt.index('}', k); c = txt[k+1:j]; k = j + 1
            assert len(c) % 2 == 0, c
            for p in range(0, len(c), 2): out += b'\x02' + c[p:p+2].encode('ascii')
            continue
        k += 1
        if ch == '|': out += b'\x02rr'; continue
        if ch in SP.MAPA or ch == '~': out.append(ord(ch) if (ch.isascii() and ch.isalnum()) else mp[ch]); continue
        out += b'\x02' + ch.encode('cp932')
    return bytes(out)
def _tokw(t):
    if t.startswith('{'): return NOMBRE_PX if re.fullmatch(r'\{n\d\}', t) else 0
    return sum(aw(c) if (c in SP.SINGLE or c in SP.MAPA or c == '~') else ICONO_PX for c in t)
def envolver(txt, maxw):
    """texto corrido -> texto con '|' al partir lineas por palabras (ancho en px)."""
    lineas = []; cur = ''; w = 0
    for tk in re.findall(r'\{[^}]*\}|\s+|[^\s{]+', txt):
        if tk.isspace():
            if cur: cur += ' '; w += LY.ancho(' ')
            continue
        tw = _tokw(tk)
        if cur and w + tw > maxw: lineas.append(cur.rstrip()); cur = ''; w = 0
        cur += tk; w += tw
    if cur.strip(): lineas.append(cur.rstrip())
    return '|'.join(lineas)
def centrar_lineas(txt):
    """mensajes centrados de varias lineas: el impresor reinicia x en cada 'rr', asi que se centra cada linea con relleno ('espacio'=12 px, '~'=6 px)"""
    ls = txt.split('|'); ws = [codificar(l)[1][0] for l in ls]; W = max(ws); out = []
    for l, w in zip(ls, ws):
        pad = int(round((W - w) / 2 / 6.0)) * 6
        out.append(' ' * (pad // 12) + '~' * ((pad % 12) // 6) + l)
    return '|'.join(out)
MSGBOX = {0x80010ec0, 0x80010f40, 0x80011580, 0x800115cc, 0x80011620}     # los imprime 0x80025c74 en x=14 (cada 'rr' vuelve a x=14)
def centrar_caja(txt):
    txt = re.sub(r'^(\{s[s8]+\})+', '', txt.replace('|{s', '|{s')); ls = [re.sub(r'^(\{s[s8]+\})+', '', l) for l in txt.split('|')]; out = []
    for l in ls:
        pad = max(0, int(round((146 - codificar(l)[1][0] / 2) / 6.0)) * 6)
        out.append(' ' * (pad // 12) + '~' * ((pad % 12) // 6) + l)
    return '|'.join(out)
def preparar_texto(a, txt):
    """perfiles (188 px) y ayuda (276 px): se reparte solo en lineas; el resto se deja como esta escrito"""
    if 0x80010000 <= a < 0x800108A4:
        cab, cuerpo = txt.split('||', 1)
        return cab + '||' + envolver(cuerpo.replace('|', ' '), 188)
    if 0x800108F4 <= a < 0x80010D2C: return envolver(txt.replace('|', ' '), 276)
    if a in MSGBOX: return centrar_caja(txt)
    if a >= 0x80010D2C and '|' in txt and '||' not in txt: return centrar_lineas(txt)
    return txt
def cadenas_jp(exe, lo=0x80010000, hi=0x80011D1C):
    r = {}; i = o(lo)
    while i < o(hi):
        j = i
        while exe[j] != 0: j += 1
        if j > i: r[i + BASE] = bytes(exe[i:j])
        i = j + 1
    return r
def escanear_sitios(exe):
    """addiu rt,rt,lo que completan un lui rt,hi hacia cadenas de la zona -> {cadena: [(off_addiu)]}"""
    sitios = {}; n = len(exe)
    for p in range(0x800, 0x800 + (0x8006AB90 - 0x80010000), 4):
        w = struct.unpack_from('<I', exe, p)[0]
        if w >> 26 != 0x0f: continue
        rt = (w >> 16) & 31; hi = w & 0xffff
        if hi != 0x8001: continue
        for k in range(1, 8):
            q = p + 4 * k
            w2 = struct.unpack_from('<I', exe, q)[0]
            if w2 >> 26 == 9 and ((w2 >> 21) & 31) == rt and ((w2 >> 16) & 31) in (rt, 4, 5, 6, 7, 16, 17):
                lo = w2 & 0xffff
                if lo < 0x8000 and SITIOS_IN[0] <= 0x80010000 + lo < SITIOS_IN[1]: sitios.setdefault(0x80010000 + lo, []).append((p, q))
                break
            if (w2 >> 16) & 31 == rt and w2 >> 26 not in (4, 5, 0x2b, 0x23, 0x21, 0x29): pass
    return sitios
def llamadas(exe):
    """jal PRINT: -> [(off_jal, off_addiu_a0 o None, x, y, direccion_cadena)]"""
    md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS32 + capstone.CS_MODE_LITTLE_ENDIAN); md.skipdata = True
    lo = 0x80012500; code = [(i.address, i.mnemonic, i.op_str) for i in md.disasm(bytes(exe[o(lo):0x800 + (0x8006AB90 - 0x80010000)]), lo)]
    res = []
    for k, (ad, m, ops) in enumerate(code):
        if m != 'jal' or ops.strip() != hex(PRINT): continue
        a0 = a1 = a2 = None; ia0 = None; hi = None
        for ad2, m2, o2 in code[max(0, k - 14):k + 2]:
            if m2 == 'addiu' and o2.startswith('$a0, $zero'): a0 = int(o2.split(',')[-1], 16); ia0 = ad2
            if m2 == 'addiu' and o2.startswith('$a1, $zero'): a1 = int(o2.split(',')[-1], 16)
            if m2 == 'lui' and o2.startswith('$a2'): hi = int(o2.split(',')[-1], 16)
            if m2 == 'addiu' and o2.startswith('$a2, $a2') and hi is not None: a2 = (hi << 16) + int(o2.split(',')[-1], 16)
        if a2 is not None and SITIOS_IN[0] <= a2 < SITIOS_IN[1]: res.append((ad, ia0, a0, a1, a2))
    return res
MAXW = lambda a: 188 if 0x80010000 <= a < 0x800108A4 else (276 if 0x800108F4 <= a < 0x80010D2C else 296)
SINT = {0xF0000001: 'Toru', 0xF0000002: 'Mari', 0xF0000003: 'Volver~х'}           # sustituyen a las cadenas 'n1'/'n2' (0x80079144/48) de la lista de personajes
SINT_SITIOS = {0x80079144: 0xF0000001, 0x80079148: 0xF0000002}
EN_SITIO = {0x80079218: 'x', 0x80079228: 'Libre', 0x80079168: 'Mover', 0x80079174: 'Grabar', 0x80079180: 'Sí', 0x800791a8: 'Sí', 0x80079188: 'No', 0x800791b0: 'No', 0x80079190: 'Seguir', 0x800118e4: ' y '}          # region 2 (libro): 1 byte, deben caber en el hueco JP (len+1)
def cadena_en(exe, a):
    i = o(a); j = i
    while exe[j] != 0: j += 1
    return exe[i:j]
def sitios_hi8(exe, objetivos):
    """lui rt,0x8008 + addiu rt,rt,-k hacia direcciones de 'objetivos' -> {dir: [(off_lui, off_addiu)]}"""
    r = {}
    for p in range(0x800, 0x800 + 0x6A000 - 0x800, 4):
        w = struct.unpack_from('<I', exe, p)[0]
        if w >> 26 != 0x0f or (w & 0xffff) != 0x8008: continue
        rt = (w >> 16) & 31
        for k in range(1, 7):
            q = p + 4 * k
            w2 = struct.unpack_from('<I', exe, q)[0]
            if w2 >> 26 == 9 and ((w2 >> 21) & 31) == rt:
                imm = w2 & 0xffff; imm -= 0x10000 if imm >= 0x8000 else 0
                if 0x80080000 + imm in objetivos: r.setdefault(0x80080000 + imm, []).append((p, q))
                break
    return r
def aplicar(exe, informe=False):
    tr = cargar_tsv(); jp = cadenas_jp(exe); sitios = escanear_sitios(exe); calls = llamadas(exe); rep = []
    irreg = [(c, (SPC if c == ' ' else v)) for c, v in SP.MAPA.items() if not (c.isascii() and c.isalnum())] + [('~', SPH)]
    mp = menu1b.aplicar(exe, irreg)
    for a, t in EN_SITIO.items():
        b = codificar1(t, mp); n0 = len(cadena_en(exe, a)); j = o(a) + n0
        while exe[j] == 0 and j < o(a) + n0 + 12: j += 1
        hueco = j - o(a) - (1 if j - o(a) > n0 + 1 and False else 0)     # bytes disponibles hasta el siguiente dato
        assert len(b) + 1 <= hueco, hex(a)
        exe[o(a):o(a) + hueco] = b + bytes(hueco - len(b))
    ncall = {}
    for c in calls: ncall[c[4]] = ncall.get(c[4], 0) + 1
    flag = {a for a in tr if a in ncall and len(sitios.get(a, [])) <= ncall[a]}      # solo las que van directas al impresor
    # 1) nuevos bytes y reubicacion por huecos
    nuevo = {}; anch = {}
    for a, b in jp.items():
        if a in tr:
            nuevo[a], anch[a] = codificar(preparar_texto(a, tr[a]))
            if a in flag: nuevo[a] = codificar1(preparar_texto(a, tr[a]), mp); assert len(nuevo[a]) < 370, hex(a)
        else: nuevo[a] = b
    for k, t in SINT.items(): nuevo[k] = codificar1(t, mp); anch[k] = [0]
    for a in tr: assert a in jp, 'direccion sin cadena JP: %x' % a
    destino = {}; libre = [[lo, hi] for lo, hi in POOLS] + [[EXTRA[0], EXTRA[1]]]
    assert all(b == 0 for b in exe[o(EXTRA[0]):o(EXTRA[1])]), 'region EXTRA ocupada'
    movibles = sorted([a for a in jp if any(lo <= a < hi for lo, hi in POOLS)] + list(SINT), key=lambda x: (0 if x in (0x800110c8, 0x800110d4, 0x800110e4) else 1, -(len(nuevo[x]) + 1)))
    for a in movibles:
        n = len(nuevo[a]) + 1
        for r in libre:
            if r[1] - r[0] >= n: destino[a] = r[0]; r[0] += n; break
        else: raise AssertionError('sin sitio para %x (%d B)' % (a, n))
    for (lo, hi), r in zip(POOLS + [EXTRA], libre): rep.append('region %x: %d de %d B' % (lo, (r[0] - lo), hi - lo))
    # debug/huecos intermedios (cadenas fuera de POOLS dentro de la zona) se dejan donde estan
    for a in jp:
        if a not in destino: destino[a] = a
    # 2) escribir (limpiando huecos)
    movibles_set = set(movibles)
    for lo, hi in POOLS: exe[o(lo):o(hi)] = bytes(hi - lo)
    for a, d in destino.items():
        if a in movibles_set: exe[o(d):o(d) + len(nuevo[a])] = nuevo[a]
        elif a in tr:      # fuera de los huecos: sustitucion en el sitio (debe caber)
            assert len(nuevo[a]) <= len(jp[a]), 'no cabe en su sitio %x' % a
            exe[o(a):o(a) + len(jp[a])] = nuevo[a] + bytes(len(jp[a]) - len(nuevo[a]))
    # 2b) sinteticas: apuntar las referencias a 'n1'/'n2' a las nuevas cadenas
    for dir_, k in SINT_SITIOS.items():
        for qh, q in sitios_hi8(exe, SINT_SITIOS).get(dir_, []):
            nd = destino[k]; wl = struct.unpack_from('<I', exe, qh)[0]; wa = struct.unpack_from('<I', exe, q)[0]
            struct.pack_into('<I', exe, qh, (wl & 0xffff0000) | (((nd + 0x8000) >> 16) & 0xffff)); struct.pack_into('<I', exe, q, (wa & 0xffff0000) | (nd & 0xffff))
            rep.append('lista personajes %x -> %x (%s)' % (dir_, nd, SINT[k]))
    # 3) reparchear addiu
    n = 0
    for a, lst in sitios.items():
        if a not in jp: continue
        for qh, q in lst:
            nd = destino[a]; wl = struct.unpack_from('<I', exe, qh)[0]; wa = struct.unpack_from('<I', exe, q)[0]
            nl = (wl & 0xffff0000) | (((nd + 0x8000) >> 16) & 0xffff); na = (wa & 0xffff0000) | (nd & 0xffff)
            if nl != wl: struct.pack_into('<I', exe, qh, nl)
            if na != wa: struct.pack_into('<I', exe, q, na)
            n += 1
    rep.append('addiu reparcheados: %d; cadenas de 1 byte: %d' % (n, len(flag)))
    # 3b) menu de pausa: con el espacio real (12 px) 'Volver ×' (86 px) no cabia en el cuadro de la derecha (x 232..312, texto en 250) y se salia de la pantalla.
    #     El cuadro se ensancha hacia la izquierda (x 212..312), el cursor y el texto se desplazan, y la ultima opcion usa 'Volver~×' (espacio de 6 px).
    PAUSA = [(a, 0xe8, 0xd4) for a in (0x80018df0, 0x80018fa0, 0x80019058, 0x80019148)] + [(a, 0x50, 0x64) for a in (0x80018df8, 0x80018fa8, 0x80019060, 0x80019150)] \
          + [(a, 0xea, 0xd6) for a in (0x800191c4, 0x800191e4)] + [(a, 0xfa, 0xe8) for a in (0x80019214, 0x80019244, 0x80019288, 0x800192b8, 0x800192dc)]
    for a, v0, v1 in PAUSA:
        w = struct.unpack_from('<I', exe, o(a))[0]; assert (w >> 16) in (0x2404, 0x2406) and (w & 0xffff) == v0, hex(a)
        struct.pack_into('<I', exe, o(a), (w & 0xffff0000) | v1)
    wl, wa = struct.unpack_from('<II', exe, o(0x800192e4)); assert (wl, wa) == (0x3c068001, 0x24c608d8) or (wl >> 16) == 0x3c06 and (wa >> 16) == 0x24c6, (hex(wl), hex(wa))
    nd = destino[0xF0000003]; struct.pack_into('<II', exe, o(0x800192e4), (wl & 0xffff0000) | (((nd + 0x8000) >> 16) & 0xffff), (wa & 0xffff0000) | (nd & 0xffff))
    rep.append('menu de pausa: cuadro x=212 w=100, texto x=232, Volver -> %x' % nd)
    # 3c) menu 'Comprobar de nuevo / Seguir sin guardar' (0x8002a400..0x8002a740): con el espacio real el texto (199 px desde x=95) se salia del cuadro (x 60..260).
    #     Cuadro x 36..284, cursor x=46 (era 70), texto x=75 (era 95).
    n3 = 0
    for a in range(0x8002a400, 0x8002a740, 4):
        w = struct.unpack_from('<I', exe, o(a))[0]
        cam = None
        if (w >> 16) == 0x2404 and (w & 0xffff) == 0x3c: cam = 0x24                 # addiu a0,zero,60  (x del cuadro)
        elif (w >> 16) == 0x2406 and (w & 0xffff) == 0xc8: cam = 0xf8               # addiu a2,zero,200 (ancho)
        elif (w >> 16) == 0x2404 and (w & 0xffff) == 0x46 and a in (0x8002a474, 0x8002a684): cam = 0x2e   # cursor
        elif (w >> 16) == 0x2404 and (w & 0xffff) == 0x5f and a in (0x8002a4a8, 0x8002a6c0, 0x8002a6f0): cam = 0x4b   # texto
        if cam is not None: struct.pack_into('<I', exe, o(a), (w & 0xffff0000) | cam); n3 += 1
    assert n3 >= 12, n3
    rep.append('menu Comprobar de nuevo: %d instrucciones (cuadro ensanchado)' % n3)
    # 3d) 'No quites ni pongas' usa 'move a1,a0' (y = x = 100); el recentrado cambiaba x y arrastraba y -> se solapaba con la linea de abajo
    for a in (0x80018114, 0x800163a4):
        assert struct.unpack_from('<I', exe, o(a))[0] == 0x00802821, hex(a)
        struct.pack_into('<I', exe, o(a), 0x24050064)                                  # addiu a1,zero,100
    # 3e) 'Cargando / Borrando / Copiando' + 'No quites ni pongas|la tarjeta de memoria.': 3 lineas con paso de 17 px; la ultima quedaba pegada al borde inferior del cuadro
    #     (y 70/90 -> 62/79 para repartir los margenes)
    for a, v0, v1 in [(0x800169e0, 0x46, 0x3e), (0x800169f8, 0x5a, 0x4f), (0x80016ae4, 0x46, 0x3e), (0x80016afc, 0x5a, 0x4f), (0x80016f64, 0x46, 0x3e), (0x80016f7c, 0x5a, 0x4f)]:
        w = struct.unpack_from('<I', exe, o(a))[0]; assert (w >> 16) == 0x2405 and (w & 0xffff) == v0, hex(a)
        struct.pack_into('<I', exe, o(a), (w & 0xffff0000) | v1)
    # 3g) nombres por defecto (pantalla 'Bienvenidos a Spur' antes de teclearlos): el original los toma de una tabla (0x8006b74c -> 透, 0x8006b750 -> 真理, en kanji).
    #     Se apuntan a 'Toru' / 'Mari' en letras anchas del mapa (mismos codigos que los nombres tecleados), al final del 2.o hueco de cadenas (EXTRA se descarto: salian en blanco).
    for k, (ptr, nom) in enumerate(((0x8006b74c, 'Toru'), (0x8006b750, 'Mari'))):
        dst = POOLS[1][1] - 32 + 16 * k                                           # cola del 2.o hueco (sin usar: las cadenas ocupan 781 de 936 B)
        assert all(b == 0 for b in exe[o(dst):o(dst) + 16]), hex(dst)
        b = b''.join(bytes([SP.MAPA[c] >> 8, SP.MAPA[c] & 255]) for c in nom)
        exe[o(dst):o(dst) + len(b)] = b
        assert struct.unpack_from('<I', exe, o(ptr))[0] in (0x800792d4, 0x800792cc), hex(ptr)
        struct.pack_into('<I', exe, o(ptr), dst)
    rep.append('nombres por defecto: Toru/Mari')
    # 3i) cueva de los caracteres de 1 byte (parche_exe): estaba en 0x8006ab90 = buffer de cabecera de la tarjeta, que el guardado sobrescribe -> cuelgue al imprimir texto tras guardar
    import parche_exe as _PE
    assert libre[1][0] <= _PE.CAVA, 'las cadenas invaden la cueva'
    _PE.poner_cueva(exe); rep.append('cueva 1 byte en %x' % _PE.CAVA)
    # 3h) menu del libro (Leer / Borrar / Copiar / Volver): 'Borrar el libro' (139 px) y 'Copiar el libro' (140 px) se salian del cuadro (x 80..240, textos en 105) y la
    #     barra de seleccion (x 100, ancho 120) era mas corta que el texto. Cuadro x 62..238, barra x 70..230, texto x 76.
    LIBRO = [(a, 0x2404, 0x64, 0x46) for a in (0x8001737c, 0x800173a8, 0x800173d0, 0x800173f8)] \
          + [(a, 0x2406, 0x78, 0xa0) for a in (0x80017384, 0x800173b0, 0x800173d8)] \
          + [(a, 0x2404, 0x69, 0x4c) for a in (0x80017428, 0x80017458, 0x8001748c, 0x800174bc)] \
          + [(0x800174dc, 0x2404, 0x50, 0x3e), (0x800174e4, 0x2406, 0xa0, 0xb0)]
    for a, op, v0, v1 in LIBRO:
        w = struct.unpack_from('<I', exe, o(a))[0]; assert (w >> 16) == op and (w & 0xffff) == v0, hex(a)
        struct.pack_into('<I', exe, o(a), (w & 0xffff0000) | v1)
    for a, nuevo_w in ((0x800173d4, 0x24050064), (0x800173fc, 0x240600a0)):          # 'move a1,a0' (y=100) y 'move a2,a1' (ancho=y=120)
        assert struct.unpack_from('<I', exe, o(a))[0] in (0x00802821, 0x00a03021), hex(a)
        struct.pack_into('<I', exe, o(a), nuevo_w)
    rep.append('menu del libro: cuadro x=62 w=176, barra x=70 w=160, texto x=76')
    # 4) recentrado de las cadenas centradas por el original
    c = 0
    for ad, ia0, x, y, a in llamadas(exe) if False else calls:
        if a not in tr or ia0 is None or x is None: continue
        wjp = jp_ancho(jp[a]); wes = max(anch[a])
        cx = CENTROS.get(a, x + wjp / 2)
        if a in CENTROS: wjp = 0
        if (abs(cx - 160) <= 16 and x not in (12, 92, 95, 105)) or a in BOTONES or a in CENTROS:
            nx = max(4, int(round(160 - wes / 2 if (abs(cx - 160) < 3 and a not in BOTONES and a not in CENTROS) else cx - wes / 2)))
            nx = max(2, nx + AJUSTE_X.get(a, 0))
            w = struct.unpack_from('<I', exe, o(ia0))[0]; struct.pack_into('<I', exe, o(ia0), (w & 0xffff0000) | nx); c += 1
    rep.append('recentradas: %d' % c)
    # 4b) impresiones con la cadena en $s0 ('move a2,s0'): el escaneo de llamadas no las veia (quedaban a la izquierda, y 'Guardado.' usaba
    #     'move a1,a0' => y = x). Se centran en x=160 y se fija y con addiu.
    inv = {d: a0 for a0, d in destino.items() if a0 in movibles_set}; jalp = 0x0c000000 | ((PRINT >> 2) & 0x3ffffff); c2 = 0; ini = o(0x80012500); fin = 0x800 + (0x8006AB90 - 0x80010000)
    for p in range(ini + 4 * 16, fin, 4):
        if struct.unpack_from('<I', exe, p)[0] != jalp: continue
        ws = [struct.unpack_from('<I', exe, p + 4 * k)[0] for k in range(-16, 2)]          # ws[16]=jal, ws[17]=delay
        if not ({0x02003021, 0x02003025} & set(ws[10:17])): continue                                              # move a2,s0
        a = None
        for k in range(16):
            if ws[k] >> 16 == 0x3c10 and ws[k] & 0xffff == 0x8001:
                for k2 in range(k + 1, 17):
                    if ws[k2] >> 16 == 0x2610: a = 0x80010000 + (ws[k2] & 0xffff); break
        a = inv.get(a)
        if a is None or a not in tr or a not in anch: continue
        k0 = max((k for k in range(16) if ws[k] >> 16 == 0x2404 and ws[k - 1] != 0 or ws[k] >> 16 == 0x2404), default=None)
        k0 = [k for k in range(16) if ws[k] >> 16 == 0x2404]
        if not k0: continue
        k0 = k0[-1]; yimm = None
        for k in range(k0, 17):
            if ws[k] >> 16 == 0x2405: yimm = ws[k] & 0xffff
        nx = max(4, int(round(160 - max(anch[a]) / 2)))
        struct.pack_into('<I', exe, p + 4 * (k0 - 16), (ws[k0] & 0xffff0000) | nx)
        if yimm is None:                                                                      # move a1,a0 (y = x original)
            ym = [k for k in range(k0, 17) if ws[k] == 0x00802821]
            assert ym, hex(p)
            struct.pack_into('<I', exe, p + 4 * (ym[0] - 16), 0x24050000 | (ws[k0] & 0xffff))
        c2 += 1
    rep.append('centradas (cadena en s0): %d' % c2)
    # 4c) mensajes del panel 0x80025898(x, lineas, cadena, espera): panel de x a 320-x con el texto en x+6 (alineado a la izquierda). Se centra segun el ancho real.
    jalw = 0x0c000000 | ((0x80025898 >> 2) & 0x3ffffff); c3 = 0
    for p in range(ini + 4 * 12, fin, 4):
        if struct.unpack_from('<I', exe, p)[0] != jalw: continue
        ws = [struct.unpack_from('<I', exe, p + 4 * k)[0] for k in range(-12, 2)]
        a = None; ka0 = None
        for k in range(12):
            if ws[k] >> 16 == 0x3c06 and ws[k] & 0xffff == 0x8001:
                for k2 in range(k + 1, 13):
                    if ws[k2] >> 16 == 0x24c6: a = inv.get(0x80010000 + (ws[k2] & 0xffff)); break
            if ws[k] >> 16 == 0x2404: ka0 = k
        if a is None or a not in tr or a not in anch or ka0 is None: continue
        nx = max(4, (308 - max(anch[a])) // 2)
        struct.pack_into('<I', exe, p + 4 * (ka0 - 12), (ws[ka0] & 0xffff0000) | nx); c3 += 1
    rep.append('paneles centrados: %d' % c3)
    # 5) avisos de anchura
    for a in sorted(tr):
        mw = max(anch[a]); lim = MAXW(a)
        if mw > lim: rep.append('ANCHO %dpx > %d: %x %s' % (mw, lim, a, tr[a][:40]))
        if 0x80010000 <= a < 0x800108A4 and len(anch[a]) > 10: rep.append('LINEAS %d: %x' % (len(anch[a]), a))
        if 0x800108F4 <= a < 0x80010D2C and len(anch[a]) > jp[a].count(b'rr') + 1: rep.append('AYUDA %d lineas > %d: %x' % (len(anch[a]), jp[a].count(b'rr') + 1, a))
    return rep
if __name__ == '__main__':
    exe = bytearray(open(os.path.join(RAIZ, 'extraido', 'SLPS_017.94'), 'rb').read())
    for l in aplicar(exe): print(l)
