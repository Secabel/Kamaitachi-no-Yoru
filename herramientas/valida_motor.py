"""valida_motor.py: valida el texto traducido contra el impresor REAL del juego (SLPS_017.94, funcion 0x80039288) ejecutado en unicorn,
en vez de contra un modelo propio. Lee la RAM (EXE parcheado + fuente con los glifos latinos) de un savestate de DuckStation.
Uso:  python herramientas/valida_motor.py [ruta_savestate]
 - Pantallas de opciones: se imprime la pregunta, cada letra y cada etiqueta (unidades del fragmento llamado) exactamente como lo hace el
   script (op 14 = origen x; op 02 = llamada a la etiqueta; op 16 = espera de eleccion, lo que sigue se imprime despues de elegir).
   Tienen que caber en 9 filas (y <= 193).
 - Texto corrido: cada fragmento se imprime desde una pagina limpia; ni los glifos ni el icono de espera (que cae en la fila siguiente tras un 'r') pueden pasar de la fila 9 (y <= 193).
Limites conocidos (no verificados): se supone que el fragmento empieza en pagina limpia (no se sigue el flujo entre fragmentos) y los nombres
{n1}/{n2} usan los que haya en la RAM del savestate."""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verificador as V, traducir as T, revisar_traduccion as R, opciones as O, sim_motor as M
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ICONOS = (0x8483, 0x8484)
Y_TEXTO = 193; Y_OPCIONES = 193      # ultima fila visible: y = 17 + 22*8 (9 filas); la de debajo se corta

def savestate():
    c = sorted(glob.glob(os.path.join(RAIZ, 'duckstation', 'savestates', '*.sav')))
    if not c: raise SystemExit('falta un savestate en duckstation/savestates')
    return c[0]

def unidad(n, key):
    E, F, idx = key; fr, _ = V.frags(n[E]); s, t = fr[F]; cmds, _ = V.parse(n[E][s:t]); k = 0; m17 = 0
    for p, op, a in cmds:
        if op == 0:
            if idx == k: return bytes(a)
            k += 1
        elif op == 0x17:
            if idx == 'm%d' % m17: return bytes(a[1:])
            m17 += 1

def filas(mo, desde, iconos=False):
    """filas (y) con glifos; con iconos=True tambien cuentan los iconos de espera (el cursor de 'rp' cae en la fila siguiente)."""
    return sorted({y for x, y, g in mo.log[desde:] if iconos or g not in ICONOS})

def simular_fragmento(mo, n, E, F, opts=None):
    """-> y maxima de un glifo. opts = pantalla de opciones (dict de opciones.pantallas) o None."""
    fr, _ = V.frags(n[E]); s, t = fr[F]; cmds, _ = V.parse(n[E][s:t])
    mo.log = []; mo.esperas = []; mo.pagina(); it = iter(opts['opts']) if opts else None; cur = None
    for p, op, a in cmds:
        if opts and op == 0x16: break
        if op == 0:
            mo.imprimir(bytes(a))
            if opts and O.LETRA.match(bytes(a)): cur = next(it)
        elif op == 0x14: mo.origen(8 + a[0], 8 + a[0])
        elif opts and op == 2 and cur is not None and cur.get('keys'):
            for key in cur['keys']:
                u = unidad(n, key)
                if u is not None: mo.imprimir(u)
    ys = filas(mo, 0)
    if not opts: ys += [y for x, y in mo.esperas]          # el icono de espera tambien tiene que verse
    return max(ys) if ys else 0

def main(sav=None):
    o = V.cargar_originales(); es = R.cargar_es(); n = T.aplicar(o, es)
    mo = M.Motor(M.ram_de_savestate(sav or savestate()))
    pant = {(p['E'], p['F']): p for p in O.pantallas(n) if p['E'] not in O.OMITIDAS}
    mal = []
    for (E, F), p in sorted(pant.items()):
        y = simular_fragmento(mo, n, E, F, p)
        if y > Y_OPCIONES: mal.append(('opciones', E, F, y))
    print('pantallas de opciones: %d, fuera de pantalla: %d' % (len(pant), len(mal)))
    tot = 0; malt = []
    for E in sorted(n):
        fr, m = V.frags(n[E])
        if m: continue
        for F in range(len(fr)):
            if (E, F) in pant: continue
            try: cmds, mm = V.parse(n[E][fr[F][0]:fr[F][1]])
            except Exception: continue
            if mm != 'ok' or not any(op == 0 and any(b >= 0xa1 for b in a) for p, op, a in cmds): continue
            tot += 1
            try: y = simular_fragmento(mo, n, E, F)
            except Exception as e: malt.append(('ERROR', E, F, str(e)[:40])); continue
            if y > Y_TEXTO: malt.append(('texto', E, F, y))
    print('fragmentos de texto: %d, con texto o icono fuera de pantalla: %d' % (tot, len(malt)))
    for x in mal + malt: print('  ', x)
    return mal, malt

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
