"""Maquetacion al espanol para Kamaitachi TH. Motor: 8 lineas/pagina, x de 0 a 280 px utiles (origen 8, salto automatico en x>=288),
avance = ancho del glifo + 1. Codigos: r salto, p espera (misma pagina), P espera + limpia pagina, g fin de bloque.
Formato de texto de traduccion: prosa + codigos entre llaves, p.ej. '{n2} paro de golpe{c1}...'. Los 'r' NO se escriben: los decide la maquetacion.
 a_texto(bytes_unidad) -> (cuerpo_str, cola_str)   |  maquetar_fragmento(unidades_es, colas) -> [bytes]"""
import re, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glifos_latinos as GL, fuente_kama as FK, sce_pac as SP
MAXX = 280; LINEAS = 8; NOMBRE_W = 72
_gl, _ = FK.leer(GL._blob); _t = GL.todos()
def ancho(ch):
    if ch in _t: return _t[ch][0] + 1
    i = GL.indice(SP.MAPA[ch]); return _gl[i][0] + 1
COLA = set(b'rpPg@')
TOK = re.compile(rb'n\d|[cChsv]\d|w.|[^\x80-\xff]', re.S)
def _lead(b): return 0x81 <= b <= 0x9f or 0xe0 <= b <= 0xfc
TOK2 = re.compile(rb'n\d|[cChsv]\d|w.|[rpPg@LokR]', re.S)
def a_texto(u):
    """unidad japonesa (bytes sin NUL) -> (cuerpo con {codigos}, cola 'rp'...). Lectura hacia delante (SJIS correcto)."""
    u = bytes(u); i = 0; toks = []                      # toks: (texto, es_cola)
    while i < len(u):
        b = u[i]
        if _lead(b): toks.append((u[i:i+2].decode('cp932', 'replace'), False)); i += 2; continue
        if 0xA1 <= b <= 0xDF: toks.append((u[i:i+1].decode('cp932', 'replace'), False)); i += 1; continue
        m = TOK2.match(u, i)
        if m: t = m.group(); toks.append(('{' + t.decode('ascii') + '}', len(t) == 1 and t in b'rpPg@')); i = m.end()
        else: toks.append(('{%02x}' % b, False)); i += 1
    k = len(toks)
    while k > 0 and toks[k-1][1]: k -= 1
    cola = ''.join(t[0][1:-1] for t in toks[k:])
    return ''.join(t[0] for t in toks[:k]), cola

NOMBRES = {}     # antes {'n1': 'Toru', 'n2': 'Mari'}: ahora el texto lleva {n1}/{n2} y el motor muestra los nombres tecleados     # nombres fijos de los protagonistas escritos en el texto (el motor los muestra en kanji)
class Estado:
    def __init__(s): s.x = 0; s.l = 0
    def copia(s): e = Estado(); e.x, e.l = s.x, s.l; return e
def _nl(est, out):
    if est.l + 1 >= LINEAS: out.append('{#PAGINA}'); est.l = 0
    else: out.append('{r}'); est.l += 1
    est.x = 0
def _cuerpo(txt, est):
    out = []
    for tk in re.findall(r'\{[^}]*\}|\s+|[^\s{]+', txt):
        if tk.startswith('{'):
            m = re.fullmatch(r'\{(n\d)\}', tk)
            if m and m.group(1) in NOMBRES: tk = NOMBRES[m.group(1)]
            elif m:
                if est.x + NOMBRE_W > MAXX and est.x > 0:
                    if out and out[-1].isspace(): out[-1] = ''
                    _nl(est, out)
                est.x += NOMBRE_W; out.append(tk); continue
            elif tk in ('{r}', '{@}'):
                if est.x == 0 and out and out[-1] in ('{r}', '{#PAGINA}'): continue
                _nl(est, out); continue
            elif tk == '{g}':
                # {g} limpia la pagina al instante: esperar antes (salvo que ya haya espera) y reiniciar el estado
                if not (out and out[-1] in ('{p}', '{P}')): out.append('{p}')
                out.append('{g}'); est.x = 0; est.l = 0; continue
            else: out.append(tk); continue
        if tk.isspace():
            if est.x == 0: continue
            est.x += ancho(' ') * len(tk); out.append(' ' * len(tk)); continue
        w = sum(ancho(c) for c in tk)
        if est.x + w > MAXX and est.x > 0:
            if out and out[-1].isspace(): out[-1] = ''
            _nl(est, out)
        est.x += w; out.append(tk)
    return ''.join(out)
def _cola(cola, est):
    for c in cola:
        if c in 'r@': est.x = 0; est.l += 1
        if c == 'g': est.x = 0; est.l = 0
def maquetar_fragmento(trad, colas):
    """trad: textos con {codigos} ('' = unidad sin texto); colas: colas originales. -> lista de str con {r}/{P}/{p}..."""
    est = Estado(); res = []                 # res: [cuerpo, cola]
    # un '@' (salto duro) al final de una unidad que acaba a mitad de frase era una pista de ajuste del japones: se descarta
    colas = [c.replace('@', '') if ('@' in c and t.strip() and t.rstrip()[-1] not in '.!?…”»)"\':;' + chr(0x2019)) else c for t, c in zip(trad, colas)]
    for t, c in zip(trad, colas):
        # {g} al final del cuerpo limpiaba la pagina ANTES de la espera de la cola (el texto desaparecia sin poder leerse): pasa a la cola, tras la espera
        tr = t.rstrip(); pg = False
        while tr.endswith('{g}'): tr = tr[:-3].rstrip(); pg = True
        if pg:
            t = tr; cc = c.replace('r', '').replace('@', '')
            if 'g' in cc: pass
            elif 'p' in cc or 'P' in cc: cc += 'g'
            else: cc = 'pg'
            c = cc
        # unidad sin texto cuya cola empieza por '@' justo tras una nueva linea: dejaba una linea en blanco de mas
        if not t.strip() and c.startswith('@') and est.x == 0 and est.l > 0: c = c.lstrip('@')
        if t.strip() and res:
            prev = res[-1]
            # lineas que ocupara la unidad desde el estado actual
            e2 = est.copia(); cu = _cuerpo(t, e2); lineas_fin = e2.l
            # si no cabe en la pagina y se puede cortar limpiamente entre unidades (cola anterior termina en p) -> pagina nueva
            if (est.l >= LINEAS or "{#PAGINA}" in cu) and prev[1][-1:] in ('p', 'P') and est.l > 0:
                prev[1] = prev[1][:-1].rstrip('r@') + 'pg'; est.l = 0; est.x = 0
        cu = _cuerpo(t, est); _cola(c, est)
        res.append([cu, c])
    return [cu + ''.join('{%s}' % x for x in c) for cu, c in res]
