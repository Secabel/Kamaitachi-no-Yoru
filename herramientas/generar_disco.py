"""Entry point: builds the translated disc (Spanish by default, English with the first argument 'en') from YOUR original disc image.
Usage (any folder):  python herramientas/generar_disco.py [es|en] [output_name]
  1. Put the original image at  rom/Sound Novel Evolution 2 - Kamaitachi no Yoru Tokubetsu-hen (Japan).bin
  2. Run this script.  The result (.bin + .cue) is written to rom/es_completo/ (or to the output name you pass, without extension).
On Windows, if you get encoding errors, run  set PYTHONUTF8=1  first.  Requires: pip install capstone unicorn"""
import os, sys, zlib, runpy
if len(sys.argv) > 1 and sys.argv[1] in ('es', 'en'): os.environ['KAMA_LANG'] = sys.argv.pop(1)   # must be set before the tools are imported
LANG = os.environ.get('KAMA_LANG', 'es')
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(RAIZ); sys.path.insert(0, 'herramientas')
BIN = 'rom/Sound Novel Evolution 2 - Kamaitachi no Yoru Tokubetsu-hen (Japan).bin'
TAM, CRC32 = 548839200, 0x0CA59B07
NOMBRE = 'rom/es_completo/Kamaitachi_ES_v37' if LANG == 'es' else 'rom/en_completo/Kamaitachi_EN_v37'
CUE = 'FILE "%s" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'

def verificar_disco():
    if not os.path.exists(BIN): sys.exit('Original disc image not found: ' + BIN)
    if os.path.getsize(BIN) != TAM: sys.exit('Wrong size for the original image (%d bytes, expected %d).' % (os.path.getsize(BIN), TAM))
    c = 0
    with open(BIN, 'rb') as f:
        while True:
            b = f.read(1 << 24)
            if not b: break
            c = zlib.crc32(b, c)
    if c != CRC32: sys.exit('CRC32 mismatch for the original image (%08X, expected %08X).' % (c, CRC32))
    print('Original image verified (CRC32 %08X).' % c)

if __name__ == '__main__':
    salida = sys.argv[1] if len(sys.argv) > 1 else NOMBRE
    if LANG == 'en' and not os.path.isdir(os.path.join('traduccion', 'en')): sys.exit('English translation not started yet (traduccion/en is missing).')
    verificar_disco()
    import preparar_extraido
    print('Extracting the files the build needs from the disc...')
    preparar_extraido.preparar(BIN, 'extraido')
    os.makedirs(os.path.dirname(salida) or '.', exist_ok=True)
    sys.argv = ['construir_hito.py', salida]
    runpy.run_path(os.path.join('herramientas', 'construir_hito.py'), run_name='__main__')
    if not os.path.exists(salida + '.cue'):
        open(salida + '.cue', 'w').write(CUE % (os.path.basename(salida) + '.bin'))
    print('Done: %s.bin / %s.cue' % (salida, salida))
