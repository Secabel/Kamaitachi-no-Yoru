"""Aplica traduccion/es_*.tsv a los originales y revisa con el verificador. Imprime solo contadores e IDs (sin texto del juego).
Uso: python herramientas/revisar_traduccion.py [-v]"""
import sys, os, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verificador as V, traducir as T, sce_pac as SP, layout as LY
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
def cargar_es():
    es = {}
    for p in sorted(glob.glob(os.path.join(RAIZ, 'traduccion', 'es_*.tsv'))):
        es.update(T.leer_es(open(p, encoding='utf-8').read()))
    return es
def revisar(es=None, verbose=False):
    o = V.cargar_originales(); es = es or cargar_es()
    mal = sorted({(k, ch) for k, v in es.items() for ch in re.sub(r'\{[^}]*\}', '', v) if ch not in SP.MAPA})
    if mal: print('CARACTERES SIN MAPA:', [(k, c) for k, c in mal][:20])
    n = T.aplicar(o, {k: v for k, v in es.items() if not any(c in SP.MAPA is False for c in '')})
    te = {(a, b) for a, b, _ in es}
    err, av = V.verificar(n, ref=o, texto_es=te)
    print('unidades', len(es), 'fragmentos', len(te), 'errores', len(err), 'avisos', len(av))
    for x in err[:30]: print(' E', x)
    if verbose:
        for x in av:
            if re.match(r'E(\d+)\.f(\d+)', x) and (int(re.match(r'E(\d+)\.f(\d+)', x).group(1)), int(re.match(r'E(\d+)\.f(\d+)', x).group(2))) in te: print(' A', x)
    return n, err
if __name__ == '__main__': revisar(verbose='-v' in sys.argv)
