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

def revisar(ents, es, filas_max=FILAS_MAX):
    """-> (screens, bad): bad = [(E, F, start_row, [rows per option], total, [keys without translation])] for screens over filas_max rows or incomplete."""
    bad = []; pant = pantallas(ents); n = 0
    for p in pant:
        E, F = p['E'], p['F']
        if E in OMITIDAS: continue                                  # developer-note entries, unreachable from the story script
        n += 1
        trad = [es.get((E, F, i), '') for i, _ in p['pre']]; colas = [LY.a_texto(a)[1] for _, a in p['pre']]
        faltan = [(E, F, i) for i, a in p['pre'] if (E, F, i) not in es and _tiene_jp(a)]
        lay = LY.maquetar_fragmento(trad, colas); sx = ''.join(lay)
        m = list(re.finditer(r'\{g\}|\{P\}|\{#PAGINA\}', sx)); tail = sx[m[-1].end():] if m else sx
        q = tail.count('{r}') + tail.count('{@}'); filas = []
        for o in p['opts']:
            keys = o.get('keys', [])
            if not keys: continue                                        # target without text: nothing is printed
            tr = []; co = []; sin = False
            for key in keys:
                u = _texto_unidad(ents, key)
                if key in es: tr.append(es[key])
                elif u is not None and _tiene_jp(u): faltan.append(key); sin = True; tr.append('')      # Japanese text that has no Spanish yet
                else: tr.append(LY.a_texto(u)[0] if u is not None else '')                                 # symbols/codes: it stays as it is
                co.append(LY.a_texto(u)[1] if u is not None and not isinstance(key[2], str) else '')
            if sin: continue
            filas.append(_filas_opcion(tr, co))
        tot = q + sum(filas)
        if faltan or tot > filas_max: bad.append((E, F, q, filas, tot, faltan))
    return n, bad

if __name__ == '__main__':
    import revisar_traduccion as R
    o = V.cargar_originales(); es = R.cargar_es(); n, bad = revisar(o, es)
    print('choice screens:', n, ' over %d rows or incomplete:' % FILAS_MAX, len(bad))
    for E, F, q, filas, tot, faltan in bad: print('  E%d.f%d  question rows %d  option rows %s  total %d%s' % (E, F, q, filas, tot, '  (no translation: %s)' % faltan if faltan else ''))
