"""Flujo de traduccion por lotes (Kamaitachi no Yoru TH).
 fuente(ents, lista_frags)      -> texto de trabajo: por fragmento '@E.F' y una linea por unidad  'idx<TAB>japones{cola}'  (solo unidades con texto)
 leer_es(texto)                 -> {(E,F,idx): texto_es}  (lineas 'E.F.idx<TAB>texto', codigos entre llaves: {n3} {c1} {s2}; sin saltos de linea: los pone layout)
 aplicar(ents, es)              -> ents nuevas (maquetadas y reinsertadas) ; es: {(E,F,idx): texto}
Una unidad = un comando 00 (texto) de un fragmento; idx = indice entre las unidades de texto del fragmento (0,1,2...). Menus (op 17) = unidades con idx 'm<k>'.
Unidades sin kana/kanji (solo codigos) no se traducen. Texto omitido en `es` = se deja en japones."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verificador as V, layout as LY, sce_pac as SP, opciones as O

def tiene_jp(b):
    i = 0
    while i < len(b):
        if V.lead(b[i]): return True
        i += 1
    return False

def unidades(ents, E, F):
    fr, m = V.frags(ents[E]); s, t = fr[F]; f = ents[E][s:t]
    cmds, mm = V.parse(f)
    if mm != 'ok': return None
    out = []; k = 0
    for p, op, a in cmds:
        if op == 0:
            out.append((k, p, 0, bytes(a))); k += 1
        elif op == 0x17:
            out.append(('m%d' % sum(1 for x in out if x[2] == 0x17), p, 0x17, bytes(a)))
    return f, out

def fuente(ents, lista):
    res = []
    for E, F in lista:
        r = unidades(ents, E, F)
        if not r: continue
        f, us = r; ls = []
        for idx, p, op, a in us:
            if op == 0x17: body, cola = LY.a_texto(a[1:])[0], '' ; src = body
            else:
                body, cola = LY.a_texto(a); src = body + ('{%s}' % cola if cola else '')
            if tiene_jp(a): ls.append('%s\t%s' % (idx, src))
        if ls: res.append('@%d.%d\n' % (E, F) + '\n'.join(ls))
    return '\n'.join(res) + '\n'

def leer_es(txt):
    es = {}
    for ln in txt.splitlines():
        if not ln.strip() or ln.startswith('#'): continue
        k, v = ln.split('\t', 1); e, f, i = k.split('.')
        es[(int(e), int(f), i if i.startswith('m') else int(i))] = v
    return es

def aplicar(ents, es, estadisticas=None):
    out = dict(ents); porfrag = {}
    etq = O.claves_etiqueta(ents)          # units printed as option labels (narrower rows, see opciones.py)
    etq_med = O.etiquetas_medias(ents); reservas = O.reservas(ents, es)      # option labels that are not the last unit of their option / rows the options need below the question
    for (E, F, i), v in es.items(): porfrag.setdefault((E, F), {})[i] = v
    nuevos = {}
    for (E, F), tr in sorted(porfrag.items()):
        r = unidades(out if E in nuevos else ents, E, F)
        f, us = r
        trad = []; colas = []; pos = []; idxs = []; cuerpos = []; maxxs = []
        for idx, p, op, a in us:
            if op == 0x17: continue
            body, cola = LY.a_texto(a)
            if (E, F, idx) in etq_med: cola = O.cola_etiqueta(cola, False)
            trad.append(tr.get(idx, '')); colas.append(cola); pos.append((p, idx)); cuerpos.append(body); maxxs.append(etq.get((E, F, idx)))
        rs, npre = reservas.get((E, F), (0, None))
        lay = LY.maquetar_fragmento(trad, colas, maxxs, rs, npre)
        rep = {}
        for (p, idx), t, l, cb, co in zip(pos, trad, lay, cuerpos, colas):
            if idx in tr and t is not None: rep[p] = SP.codificar_es(l)
            elif cb == '' and l != ''.join('{%s}' % ch for ch in co): rep[p] = SP.codificar_es(l)   # unidad sin texto cuya cola cambia (p.ej. '@' redundante)
        for idx, p, op, a in us:
            if op == 0x17 and idx in tr:
                _b, _c = LY.a_texto(a[1:])                 # la cola original (p.ej. '@' = salto duro entre opciones) se conserva
                _t = tr[idx]
                if (E, F, idx) in etq: _t = LY._cuerpo(_t, LY.Estado(), etq[(E, F, idx)])      # option label of a choice screen: lay it out too
                rep[p] = SP.codificar_es(_t + ''.join('{%s}' % ch for ch in _c))
        nuevos.setdefault(E, {})[F] = SP.reinsertar(f, rep)
    for E, frs in nuevos.items():
        fr, _ = V.frags(ents[E]); datos = [ents[E][s:t] for s, t in fr]
        for F, d in frs.items(): datos[F] = d
        out[E] = SP.construir_entrada(datos)
    return O.limpiar_antes(O.parchear(out))     # gap between option letter and text (op 14 operand); every choice starts on a clean page (pg before the question)
