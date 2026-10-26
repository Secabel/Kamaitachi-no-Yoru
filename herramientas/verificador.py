"""Revisor estatico de scripts SCE (Kamaitachi no Yoru TH). Uso:
   python herramientas/verificador.py            -> revisa los originales (calibracion)
   from verificador import verificar, cargar_originales ; verificar(ents, ref=originales) -> (errores, avisos)
ents = {id_entrada: bytes (descomprimido)}.
Comprueba: tabla de fragmentos, parseo de comandos, tamano <= buffer 0xB000, IDs de salto resolubles,
texto (codigos validos, bytes simples A1..DF solo los del mapa, 2 bytes solo del mapa, ancho <=280 px, <=8 lineas/pagina, bloques que acaban en pg/Pg)."""
import os, re, sys, struct, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scriptparse as S, sce_pac as SP
AQUI = os.path.dirname(os.path.abspath(__file__)); RAIZ = os.path.join(AQUI, '..')
BUFFER = 0xB000; MAXX = 280; LINEAS = 8; NOMBRE_W = 102
# operandos que son IDs u16 (offset dentro de los operandos); 13: 2,4,6,8 ; 57: 2,6,10,14,18
IDOPS = {0x01: [0], 0x02: [0], 0x07: [0], 0x0e: [1], 0x0f: [1], 0x13: [2, 4, 6, 8], 0x25: [1], 0x40: [2], 0x4b: [0], 0x56: [0],
         0x57: [2, 6, 10, 14, 18], 0x5e: [1]}
DUDOSOS = {0x30, 0x32, 0x34, 0x35, 0x36}

def lead(b): return 0x81 <= b <= 0x9f or 0xe0 <= b <= 0xfc

def parse(fr):
    """igual que scriptparse.parse pero con SJIS correcto (A1..DF = 1 byte)."""
    p = 0; out = []
    def fin(q):
        while q < len(fr) and fr[q] != 0: q += 2 if lead(fr[q]) else 1
        return q
    while p < len(fr):
        op = fr[p]
        if op == 0:
            q = fin(p + 1)
            if q >= len(fr): return out, 'texto sin NUL'
            out.append((p, 0, fr[p+1:q])); p = q + 1; continue
        if op >= 0xca: return out, 'opcode>=ca (%02x)' % op
        if op == 0x17:
            q = fin(p + 2)
            if q >= len(fr): return out, 'texto17 sin NUL'
            out.append((p, 0x17, fr[p+1:q])); p = q + 1; continue
        n = S.SZ[op]
        if op == 0x13 and p + 1 < len(fr): n = 2 + 2 * (fr[p+1] + 1)
        if op == 0x57 and p + 1 < len(fr): n = 2 + 4 * (fr[p+1] + 1)
        if p + 1 + n > len(fr): return out, 'operandos exceden (%02x)' % op
        out.append((p, op, fr[p+1:p+1+n])); p += 1 + n
    return out, 'ok'

def frags(e):
    """-> (lista de (ini,fin), error|None)"""
    if len(e) < 2: return [], 'entrada vacia'
    tb = int.from_bytes(e[:2], 'little')
    if tb % 2 or tb == 0 or tb > len(e): return [], 'cabecera de tabla invalida (%d)' % tb
    of = [int.from_bytes(e[x:x+2], 'little') for x in range(0, tb, 2)]
    if of[0] != tb: return [], 'primer offset != tamano de tabla'
    if any(b < a for a, b in zip(of, of[1:])): return [], 'offsets no crecientes'
    if of[-1] > len(e): return [], 'offset fuera de entrada'
    return list(zip(of, of[1:] + [len(e)])), None

def cargar_originales():
    ents = {}; sce = open(os.path.join(RAIZ, 'extraido', 'SCE.PAC'), 'rb').read()
    ES, fin = S.pac(sce); oS = [o for _, o in ES] + [fin]
    for k, (i, o) in enumerate(ES):
        e = sce[o*2048:oS[k+1]*2048]
        if e[2:5] == b'ike':
            f = os.path.join(RAIZ, 'extraido', 'SCE_descomprimido', 'SCE_%02d.bin' % i)
            e = open(f, 'rb').read()
        ents[i] = e
    return ents

# ---- texto ----
_inv = None
def _tablas():
    global _inv
    if _inv is None:
        _inv = {v: k for k, v in SP.MAPA.items()}
        import layout as LY; _inv = (_inv, LY.ancho)
    return _inv
TOK = re.compile(rb'n\d|[cChsv]\d|w.|[rpPg@LokR]', re.S)

def revisar_texto(u, est, ctx, err, av, es):
    """u = bytes de una unidad; est=[x,linea] (se actualiza); es = revisar ancho/lineas."""
    inv, ancho = _tablas(); i = 0; x, l = est
    while i < len(u):
        b = u[i]
        if lead(b):
            c = u[i:i+2]
            if len(c) < 2: err.append('%s: byte de cabecera SJIS truncado' % ctx); break
            code = (c[0] << 8) | c[1]; i += 2
            ch = inv.get(code)
            if ch is None:
                if es: av.append('%s: 2 bytes fuera del mapa %04X (japones residual?)' % (ctx, code))
                x += 25; continue
            w = ancho(ch)
        elif 0xA1 <= b <= 0xDF:
            k = b - 0xA1
            if k >= len(SP.SINGLE): err.append('%s: byte simple %02X sin glifo' % (ctx, b)); i += 1; continue
            w = ancho(SP.SINGLE[k]); i += 1
        else:
            m = TOK.match(u, i)
            if not m: err.append('%s: codigo de control invalido %r' % (ctx, u[i:i+3])); i += 1; continue
            t = m.group(); i = m.end()
            if t[:1] == b'n':
                if es and x + NOMBRE_W > MAXX and x > 0: x = 0; l += 1
                if es and l >= LINEAS: err.append('%s: mas de %d lineas por pagina' % (ctx, LINEAS)); l = 0
                x += NOMBRE_W; continue
            if t in (b'r', b'@'): x = 0; l += 1
            elif t == b'g': x = 0; l = 0
            if es and l >= LINEAS: err.append('%s: mas de %d lineas por pagina' % (ctx, LINEAS)); l = 0
            continue
        if es:
            if x + w > MAXX and x > 0: x = 0; l += 1
            if l >= LINEAS: err.append('%s: mas de %d lineas por pagina' % (ctx, LINEAS)); l = 0
        x += w
    est[0], est[1] = x, l

def verificar(ents, ref=None, es=True, texto_es=None, conocidos=None, alias=None):
    """texto_es: conjunto de (entrada,frag) a revisar como espanol (ancho/lineas). Si None y es: todo."""
    if conocidos is None and ref is not None and ref is not ents:
        conocidos = {(int(m.group(1)), int(m.group(2))) for x in verificar(ref, es=False, conocidos=set())[0] for m in [re.match(r'E(\d+)\.f(\d+)', x)] if m}
    conocidos = conocidos if conocidos is not None else set()
    if ref is ents and not conocidos: conocidos = {(int(m.group(1)), int(m.group(2))) for x in verificar(ents, es=False, conocidos=set())[0] for m in [re.match(r'E(\d+)\.f(\d+)', x)] if m}
    err = []; av = []
    ids = set(ents); nfr = {}
    for a, e in ents.items():
        fr, m = frags(e)
        if m: err.append('E%d: %s' % (a, m)); continue
        nfr[a] = len(fr)
        if len(e) > BUFFER: err.append('E%d: %d B > buffer 0x%X' % (a, len(e), BUFFER))
    for a, e in ents.items():
        if a not in nfr: continue
        fr, _ = frags(e)
        for n, (s, t) in enumerate(fr):
            f = e[s:t]; cmds, m = parse(f); ctx = 'E%d.f%d' % (a, n)
            err0 = len(err)
            if m != 'ok':
                ok_ref = False
                if ref and a in ref:
                    rf, mm = frags(ref[a])
                    if not mm and n < len(rf): ok_ref = parse(ref[a][rf[n][0]:rf[n][1]])[1] == 'ok'
                (err if ok_ref or not ref else av).append('%s: parseo %s' % (ctx, m)); continue
            est = [0, 0]; es_f = es and (texto_es is None or (a, n) in texto_es)
            for p, op, ar in cmds:
                if op in IDOPS:
                    for o in IDOPS[op]:
                        if o + 2 > len(ar): continue
                        v = int.from_bytes(ar[o:o+2], 'little')
                        if v in (0, 0xffff): continue
                        if v // 1000 not in nfr or v % 1000 >= nfr[v // 1000]:
                            err.append('%s+%d: op%02X ID %d no resuelve' % (ctx, p, op, v))
                elif op in (0, 0x17):
                    revisar_texto(ar[1:] if op == 0x17 else ar, est, '%s+%d' % (ctx, p), err, av, es_f)
                    if op == 0 and est[1] > 0 and ar[-1:] not in (b'g', b'P', b'p', b'r'): pass
            # los bloques acaban en pg/Pg: ultimo texto del fragmento
            tx = [c for c in cmds if c[1] == 0]
            if es_f and tx and tx[-1][2][-2:] not in (b'pg', b'Pg') and tx[-1][2][-1:] != b'g':
                av.append('%s: el ultimo texto no acaba en g' % ctx)
            if ((alias or {}).get(a, a), n) in conocidos and len(err) > err0:
                av.extend('[ya en original] ' + x for x in err[err0:]); del err[err0:]
    return err, av

if __name__ == '__main__':
    o = cargar_originales()
    err, av = verificar(o, ref=o, es=False)
    print('originales: %d errores, %d avisos' % (len(err), len(av)))
    for x in err[:30]: print(' E', x)
    for x in av[:10]: print(' A', x)
