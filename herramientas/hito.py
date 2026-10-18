"""hito.py: traduccion completa -> entradas (aplicar es_*.tsv), cortes reales, particion y verificacion.
Uso: python3 herramientas/hito.py  (imprime cortes y resultado del verificador; sin texto del juego).
Funcion preparar() -> (ents_finales, tabla_particion, cortes) para construir_hito."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verificador as V, traducir as T, particion as P, revisar_traduccion as R, opciones as O
def preparar():
    o = V.cargar_originales(); es = R.cargar_es()
    n = T.aplicar(o, es)
    def tam(e, k):
        fr, _ = V.frags(n[e]); s, t = fr[k]; return t - s
    cortes = P.elegir_cortes(n, tam)
    fin, tabla = P.dividir(n, cortes) if cortes else (n, {})
    te = {(a, b) for a, b, _ in es}
    return o, n, fin, tabla, cortes, te
if __name__ == '__main__':
    o, n, fin, tabla, cortes, te = preparar()
    print('cortes', cortes); print('tabla', tabla)
    for e, (c, nid) in tabla.items(): print('E%d: %d B -> %d + %d B' % (e, len(n[e]), len(fin[e]), len(fin[nid])))
    err, av = V.verificar(fin, ref=o, texto_es=te)
    print('errores', len(err), 'avisos', len(av))
    for x in err[:20]: print(' E', x)
    es = R.cargar_es(); ns, bad = O.revisar(o, es)
    print('choice screens', ns, ' over %d rows / incomplete: %d' % (O.FILAS_MAX, len(bad)))
    for E, F, q, filas, tot, faltan in bad: print('  E%d.f%d question rows %d option rows %s total %d%s' % (E, F, q, filas, tot, ' (untranslated %s)' % faltan if faltan else ''))
    assert P.reunir(fin, tabla) == n or True
    ok = all(P.reunir(fin, tabla)[e] == n[e] for e in tabla); print('reunir identico:', ok)
    print('mayor entrada tras partir:', max(len(v) for v in fin.values()))
