"""idioma.py: language selection for the build and the tools.
The language comes from the KAMA_LANG environment variable ('es' by default, or 'en'); generar_disco.py sets it from its first argument.
  ruta(nombre)  -> path of a translation file for the current language (es: traduccion/NAME, en: traduccion/en/NAME)
  patron()      -> glob pattern of the script files (es_NN.tsv / en_NN.tsv)
  fichero(E)    -> path of the script file of entry E
Spanish files stay where they always were so nothing changes for the Spanish build."""
import os
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
LANG = os.environ.get('KAMA_LANG', 'es')
if LANG not in ('es', 'en'): raise SystemExit('KAMA_LANG must be es or en, not %r' % LANG)
def ruta(nombre):
    return os.path.join(RAIZ, 'traduccion', nombre) if LANG == 'es' else os.path.join(RAIZ, 'traduccion', LANG, nombre)
def patron(): return ruta('%s_*.tsv' % LANG)
def fichero(E): return ruta('%s_%02d.tsv' % (LANG, E))
