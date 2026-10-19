"""Choice screens (letter options A/B/C/D).  Facts about the engine (from the script data + disassembly):
 - A choice fragment prints the question, then for each option: `14 02` (x origin = 10), the letter unit 'v0c1' + full-width A/B/C/D,
   `14 10` (x origin AND current x = 8 + 0x10 = 24), `02 <id>` = CALL to the target fragment, whose FIRST text unit is printed as the option text
   (it is the same unit that is shown as story after choosing it; it can be an op 00 unit or an op 17 unit).
 - Rows wrap automatically when a character starts at x >= 288, going back to the origin (24 for the option text), so an option text has
   288 - 24 = 264 px, NOT the 280 px of normal text; and the letter touches the text (the Japanese glyphs bring their own side bearing).
Fixes done here:  (1) the `14 10` operand after each letter becomes 0x10 + GAP (a gap between the letter and the text, same origin for every row);
 (2) option label units are laid out with MAXX_ETIQ (rows of 288 - (24 + GAP) px);  (3) revisar() checks that question + options fit in FILAS_MAX rows.
Usage: python herramientas/opciones.py  -> table of the screens that do not fit (also called from hito.py)."""
import os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verificador as V, layout as LY, sce_pac as SP
OMITIDAS = (22, 32)
GAP = 6                              # px between the option letter and its text
ORIGEN = 24                          # original x of the option text (op 14 with operand 0x10)
FILAS_MAX = 9                        # rows of a screen (the physical screen shows 10; one is left as margin)
MAXX_ETIQ = LY.MAXX - (ORIGEN + GAP - 8)      # layout width (origin 8 -> limit 288) for an option label
LETRA = re.compile(rb'^v\dc\d(\x82[\x60-\x79])$')

def _region(ents, E, F):
    """keys of the text units printed as the option text: every text unit (op 00 -> int, op 17 -> 'mK') of fragment (E,F) before its first op 0x15
    (end of the preview; verified on every option of the game). If there is no op 0x15, only the first text unit."""
    fr, m = V.frags(ents[E]); s, t = fr[F]; cmds, mm = V.parse(ents[E][s:t])
    if mm != 'ok': return []
    ks = []; k = 0; m17 = 0; fin = False
    for p, op, a in cmds:
        if op == 0x15: fin = True; break
        if op == 0: ks.append(k); k += 1
        elif op == 0x17: ks.append('m%d' % m17); m17 += 1
    if not fin: ks = ks[:1]
    return ks

def _texto_unidad(ents, key):
    """bytes of the original unit (E, F, idx|'mK'), or None."""
    E, F, idx = key; fr, m = V.frags(ents[E]); s, t = fr[F]; cmds, mm = V.parse(ents[E][s:t]); k = 0; m17 = 0
    for p, op, a in cmds:
        if op == 0:
            if idx == k: return bytes(a)
            k += 1
        elif op == 0x17:
            if idx == 'm%d' % m17: return bytes(a[1:])
            m17 += 1
    return None

def _tiene_jp(b):
    return any(V.lead(x) for x in b)

def pantallas(ents):
    """Choice screens of the entries: [{E, F, pre:[(idx, units)], opts:[{call:(Et,Ft), key:(Et,Ft,idx), p14:pos of the '14 10' op}]}]."""
    res = []
    for E in sorted(ents):
        fr, m = V.frags(ents[E])
        if m: continue
        for F, (s, t) in enumerate(fr):
            cmds, mm = V.parse(ents[E][s:t])
            if mm != 'ok': continue
            pre = []; opts = []; cur = None; k = 0
            for p, op, a in cmds:
                if op == 0:
                    if LETRA.match(bytes(a)): cur = {'call': None, 'p14': None}; opts.append(cur)
                    elif cur is None: pre.append((k, bytes(a)))
                    k += 1
                elif cur is not None:
                    if op == 0x14 and cur['p14'] is None and cur['call'] is None: cur['p14'] = p
                    if op == 2 and cur['call'] is None:
                        v = int.from_bytes(bytes(a)[:2], 'little'); cur['call'] = (v // 1000, v % 1000)
            if opts:
                for o in opts:
                    if o['call']:
                        o['keys'] = [o['call'] + (k,) for k in _region(ents, *o['call'])]
                        o['key'] = o['keys'][0] if o['keys'] else o['call'] + (None,)
                res.append({'E': E, 'F': F, 'pre': pre, 'opts': opts})
    return res

def claves_etiqueta(ents):
    """{(E, F, idx): MAXX_ETIQ} for every unit printed as an option label."""
    return {k: MAXX_ETIQ for p in pantallas(ents) for o in p['opts'] for k in o.get('keys', [])}

def parchear(ents):
    """After translation: `14 10` right after each letter -> `14 (0x10+GAP)`. Same size, so offsets do not move."""
    out = dict(ents); cambios = {}
    for p in pantallas(ents):
        for o in p['opts']:
            if o['p14'] is None: continue
            cambios.setdefault(p['E'], {}).setdefault(p['F'], []).append(o['p14'])
    for E, frs in cambios.items():
        fr, _ = V.frags(ents[E]); datos = [bytearray(ents[E][s:t]) for s, t in fr]
        for F, ps in frs.items():
            for p in ps:
                assert datos[F][p] == 0x14 and datos[F][p + 1] == 0x10, (E, F, p, datos[F][p:p + 2].hex())
                datos[F][p + 1] = 0x10 + GAP
        out[E] = SP.construir_entrada([bytes(d) for d in datos])
    return out

def _filas_etiqueta(txt):
    est = LY.Estado(); cu = LY._cuerpo(txt, est, MAXX_ETIQ)
    return 1 + cu.count('{r}') + 8 * cu.count('{#PAGINA}')

def _filas_opcion(tr, co):
    """rows taken by an option whose text is the units tr (with original tails co), laid out with the label width."""
    lay = LY.maquetar_fragmento(tr, co, [MAXX_ETIQ] * len(tr)); sx = ''.join(lay)
    sx = re.sub(r'(\{[pPg@]\})+$', '', sx)
    return sx.count('{r}') + (0 if sx.endswith('{r}') else 1) + 8 * sx.count('{#PAGINA}')

def cola_etiqueta(co, ultima):
    """tail of an option-label unit.  A '@' (hard line break) after 'r' in the MIDDLE of an option left a blank row between its two units
    (e.g. '"...Si." / (blank) / Respondi con sinceridad.'): it is dropped there.  The last unit keeps it (it separates the options)."""
    return co.replace('@', '') if (not ultima and 'r' in co and '@' in co) else co

def etiquetas_medias(ents):
    """keys of the option-label units that are not the last unit of their option."""
    return {k for p in pantallas(ents) for o in p['opts'] for k in o.get('keys', [])[:-1]}

def _filas_pantalla(p, ents, es):
    """-> (rows per option, keys without Spanish yet)."""
    E, F = p['E'], p['F']; filas = []; faltan = []
    for o in p['opts']:
        keys = o.get('keys', [])
        if not keys: continue                                        # target without text: nothing is printed
        tr = []; co = []; sin = False
        for n, key in enumerate(keys):
            u = _texto_unidad(ents, key)
            if key in es: tr.append(es[key])
            elif u is not None and _tiene_jp(u): faltan.append(key); sin = True; tr.append('')      # Japanese text that has no Spanish yet
            else: tr.append(LY.a_texto(u)[0] if u is not None else '')                                 # symbols/codes: it stays as it is
            c = LY.a_texto(u)[1] if u is not None and not isinstance(key[2], str) else ''
            co.append(cola_etiqueta(c, n == len(keys) - 1))
        if sin: continue
        filas.append(_filas_opcion(tr, co))
    return filas, faltan

def reservas(ents, es):
    """{(E, F): (rows needed by the options, number of question units)} for every choice screen (used by traducir.aplicar)."""
    return {(p['E'], p['F']): (sum(_filas_pantalla(p, ents, es)[0]), len(p['pre'])) for p in pantallas(ents) if p['E'] not in OMITIDAS}

def revisar(ents, es, filas_max=FILAS_MAX):
    """-> (screens, bad): bad = [(E, F, start_row, [rows per option], total, [keys without translation])] for screens over filas_max rows or incomplete."""
    bad = []; pant = pantallas(ents); n = 0
    for p in pant:
        E, F = p['E'], p['F']
        if E in OMITIDAS: continue                                  # developer-note entries, unreachable from the story script
        n += 1
        trad = [es.get((E, F, i), '') for i, _ in p['pre']]; colas = [LY.a_texto(a)[1] for _, a in p['pre']]
        filas, faltan = _filas_pantalla(p, ents, es)
        faltan = [(E, F, i) for i, a in p['pre'] if (E, F, i) not in es and _tiene_jp(a)] + faltan
        lay = LY.maquetar_fragmento(trad, colas, None, sum(filas), len(trad)); sx = ''.join(lay)
        m = list(re.finditer(r'\{g\}|\{#PAGINA\}', sx)); tail = sx[m[-1].end():] if m else sx       # only g / page break clear the screen ('P' only waits)
        q = tail.count('{r}') + tail.count('{@}')
        tot = q + sum(filas)
        if faltan or tot > filas_max: bad.append((E, F, q, filas, tot, faltan))
    return n, bad

if __name__ == '__main__':
    import revisar_traduccion as R
    o = V.cargar_originales(); es = R.cargar_es(); n, bad = revisar(o, es)
    print('choice screens:', n, ' over %d rows or incomplete:' % FILAS_MAX, len(bad))
    for E, F, q, filas, tot, faltan in bad: print('  E%d.f%d  question rows %d  option rows %s  total %d%s' % (E, F, q, filas, tot, '  (no translation: %s)' % faltan if faltan else ''))

def _texto_visible(a):
    return any(V.lead(b) or 0xa1 <= b <= 0xdf for b in a)

def limpiar_antes(ents, profundidad=4, informe=None):
    """Every choice screen starts on a CLEAN page: the last text before the jump into a choice fragment must end the PAGE, not just the line.
    That text gets 'pg' at its end (p/P -> pg: same wait; no wait -> a page wait is added; 'g' already there: untouched).  Predecessors come from
    the jump/call ops (V.IDOPS); a predecessor with no text before its jump is followed up to `profundidad` levels.
    Returns the new entries; informe gets 'ya', 'cambiadas' and 'sin' (screens without a usable predecessor)."""
    cm = {}; refs = {}
    for E in sorted(ents):
        fr, m = V.frags(ents[E])
        if m: continue
        for F, (s, t) in enumerate(fr):
            cmds, mm = V.parse(ents[E][s:t])
            if mm != 'ok': continue
            cm[(E, F)] = cmds
            for k, (p, op, a) in enumerate(cmds):
                for off in V.IDOPS.get(op, []):
                    if off + 2 <= len(a):
                        v = int.from_bytes(bytes(a)[off:off + 2], 'little')
                        if v: refs.setdefault((v // 1000, v % 1000), []).append((E, F, k))
    elecciones = {(p['E'], p['F']) for p in pantallas(ents)}       # un fragmento de eleccion no es 'texto previo': sus letras/etiquetas no se tocan
    def previo(E, F, k, nivel, vistos):
        if (E, F) in elecciones: return []
        ult = None
        for p, op, a in cm[(E, F)][:k]:
            if op == 0 and _texto_visible(bytes(a)): ult = (p, bytes(a))
        if ult is not None: return [(E, F, ult[0], ult[1].endswith(b'g'))]
        if nivel <= 0 or (E, F) in vistos: return []
        r = []
        for (E2, F2, k2) in refs.get((E, F), []): r += previo(E2, F2, k2, nivel - 1, vistos | {(E, F)})
        return r
    cambios = {}; ya = 0; sin = []
    for pnt in pantallas(ents):
        if pnt['E'] in OMITIDAS: continue
        rs = []
        for (E2, F2, k2) in refs.get((pnt['E'], pnt['F']), []): rs += previo(E2, F2, k2, profundidad, frozenset())
        if pnt['F'] > 0 and (pnt['E'], pnt['F'] - 1) in cm:          # un fragmento que no termina en salto sigue en el siguiente
            rs += previo(pnt['E'], pnt['F'] - 1, len(cm[(pnt['E'], pnt['F'] - 1)]), profundidad, frozenset())
        if not rs: sin.append((pnt['E'], pnt['F'])); continue
        for (E2, F2, p2, g) in rs:
            if g: ya += 1
            else: cambios.setdefault(E2, {}).setdefault(F2, set()).add(p2)
    out = dict(ents); n = 0
    for E, frs in cambios.items():
        fr, _ = V.frags(ents[E]); datos = [bytearray(ents[E][s:t]) for s, t in fr]
        for F, ps in frs.items():
            for p in sorted(ps, reverse=True):
                q = p + 1
                while datos[F][q] != 0: q += 2 if V.lead(datos[F][q]) else 1
                if datos[F][q - 1] in (0x70, 0x50): datos[F][q:q] = b'g'              # p/P -> pg
                else: datos[F][q:q] = b'pg'                                           # sin espera: se anade una de pagina
                n += 1
        out[E] = SP.construir_entrada([bytes(d) for d in datos])
    if informe is not None: informe.update(ya=ya, cambiadas=n, sin=sin)
    return out
