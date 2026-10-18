"""Disco HITO (traduccion completa + particion automatica). Derivado de construir_prueba. Uso: python herramientas/construir_hito.py [salida]
(Disco de PRUEBA original: fuente latina (BIN.PAC id 0 en su sitio) + SCE.PAC sin comprimir al final del disco con el ISO9660 actualizado
+ texto de prueba en espanol en SCE 27 frag 3. Uso (raiz del proyecto): python herramientas/construir_prueba.py [salida]  (~2 min)"""
import sys, os, struct, time
sys.path.insert(0, 'herramientas')
import disco, fuente_kama as FK, glifos_latinos as GL, sce_pac as SP, scriptparse as S
SS = 2352
BIN = 'rom/Sound Novel Evolution 2 - Kamaitachi no Yoru Tokubetsu-hen (Japan).bin'
SAL = sys.argv[1] if len(sys.argv) > 1 else 'rom/prueba/Kamaitachi_hito1'
orig = open(BIN, 'rb'); total = os.path.getsize(BIN) // SS
def ud(l): orig.seek(l * SS); return orig.read(SS)[24:24 + 2048]
cambios = {}   # lba -> 2048 B nuevos
def poner(lba, datos):
    for k in range(0, len(datos), 2048):
        b = datos[k:k+2048]; b += b'\0' * (2048 - len(b))
        if b != ud(lba + k // 2048): cambios[lba + k // 2048] = b
# 1) fuente
binpac = open('extraido/BIN.PAC', 'rb').read()
E, fin = FK.leer_pac(binpac); offs = [o for _, o in E] + [fin]
ent0 = binpac[E[0][1]*2048:offs[1]*2048]
gl, _ = FK.leer(ent0)
tabla = GL.todos(); n = 0
for ch, g in tabla.items():
    i = GL.indice(SP.MAPA[ch]); assert i is not None and i >= 0, ch
    gl[i] = g; n += 1
for _c, _t in GL.ICONOS.items(): gl[GL.indice(_c)] = GL.texto_glifo(_t)
import menus_exe as _ME
for _c, _w in ((_ME.SPC, 11), (_ME.SPH, 5)): gl[GL.indice(_c)] = (_w, 19, [0] * (_w * 19))     # espacios de menu (glifos en blanco)
nuevo = FK.construir(gl); assert len(nuevo) <= len(ent0), (len(nuevo), len(ent0))
nuevo += b'\0' * (len(ent0) - len(nuevo))
# sector inicial de BIN.PAC en el disco
def listar():
    pvd = ud(16); root = pvd[156:190]; lba, sz = struct.unpack('<I', root[2:6])[0], struct.unpack('<I', root[10:14])[0]
    data = b''.join(ud(lba + i) for i in range((sz + 2047)//2048)); p = 0; r = {}
    while p < len(data):
        l = data[p]
        if l == 0: p = (p//2048 + 1)*2048; continue
        rec = data[p:p+l]; r[rec[33:33+rec[32]].decode('ascii','replace').split(';')[0]] = (p, lba, struct.unpack('<I', rec[2:6])[0], struct.unpack('<I', rec[10:14])[0]); p += l
    return r
L = listar(); BINLBA = L['BIN.PAC'][2]; SCEPOS, DIRLBA, SCELBA, SCESZ = L['SCE.PAC']
poner(BINLBA + E[0][1], nuevo)
# 1b) ejecutable: caracteres de 1 byte
import parche_exe
exe = bytearray(open('extraido/SLPS_017.94', 'rb').read())
parche_exe.aplicar(exe, lambda ch: GL.indice(SP.MAPA[ch]), SP.SINGLE)
import menus_exe
for _l in menus_exe.aplicar(exe): print('menus_exe:', _l)
import mapa_titulos
for _l in mapa_titulos.aplicar(exe): print('mapa_titulos:', _l)
for _l in mapa_titulos.aplicar_finales(exe): print('mapa_titulos:', _l)
import nombres_es
for _l in nombres_es.aplicar(exe, mapa_titulos.LIBRES): print('nombres_es:', _l)
poner(L['SLPS_017.94'][2], bytes(exe))
# 2) SCE.PAC: entradas sin comprimir
sce = open('extraido/SCE.PAC', 'rb').read()
ES, finS = S.pac(sce)      # (la descompresion con el emulador era trabajo muerto: 'ents' se reasigna abajo con hito.preparar)
import hito
_o, _n, ents_f, tabla, _c, _te = hito.preparar()
orden = [i for i, _ in ES] + sorted(set(ents_f) - set(i for i, _ in ES))
ents = ents_f
if tabla:
    import parche_carga
    parche_carga.aplicar(exe, tabla); poner(L['SLPS_017.94'][2], bytes(exe))
    print('particion', tabla)
pac = SP.construir_pac(ents, orden=orden, primer_sector=ES[0][1])
NEW0 = total; nsec = (len(pac) + 2047)//2048
# 2b) BGD.PAC: entrada 933 (id 9005, mapa del mando) sustituida por el TIM en espanol SIN comprimir; el BGD se reubica tras SCE.PAC.
#     El cargador calcula la longitud de cada entrada como (inicio de la SIGUIENTE entrada de la tabla) - (inicio): el registro de 9005 se mueve al final de la tabla.
import mando_es
BGDPOS, _dl, BGDLBA, BGDSZ = L['BGD.PAC']
bg = bytearray(b''.join(ud(BGDLBA + i) for i in range(BGDSZ // 2048)))
tabB = []; _i = 0
while True:
    _id, _st = struct.unpack_from('<HH', bg, 4 * _i); tabB.append([_id, _st]); _i += 1
    if _id == 0xffff: break
import fin_es
tim, _fallos = mando_es.construir(); assert not _fallos, _fallos
_AQ = os.path.dirname(os.path.abspath(__file__))
_fin = lambda f: fin_es.poner(open(os.path.join(_AQ, '..', 'extraido', f), 'rb').read())[0]
_imgs = [(9006, tim), (9205, _fin('BGD_957_orig.tim')), (9209, _fin('BGD_961_orig.tim'))]   # mando, 'Fin' (終), 'Fin' (完)
_n = 0
for _idn, _tim in _imgs:
    _ns = (len(_tim) + 2047) // 2048
    k9 = [k for k, (a_, b_) in enumerate(tabB) if a_ == _idn][0]
    rec = tabB.pop(k9); fin0 = tabB[-1][1]; assert fin0 == len(bg) // 2048 if _n else fin0 == BGDSZ // 2048
    rec[1] = fin0; tabB.insert(len(tabB) - 1, rec); tabB[-1][1] = fin0 + _ns
    for _i, (a_, b_) in enumerate(tabB): struct.pack_into('<HH', bg, 4 * _i, a_, b_)
    bg += _tim.ljust(_ns * 2048, b'\0'); _n += _ns
NEW1 = NEW0 + nsec; nsecB = len(bg) // 2048
print('BGD.PAC nuevo: %d sectores (antes %d) en LBA %d; mando %d sectores' % (nsecB, BGDSZ // 2048, NEW1, _n))
print('SCE.PAC nuevo: %d sectores (antes %d) en LBA %d' % (nsec, SCESZ//2048, NEW0))
# 3) ISO9660: registro de SCE.PAC y volumen
d = bytearray(b''.join(ud(DIRLBA + i) for i in range(1)))
sd = bytearray(ud(DIRLBA + SCEPOS // 2048)); q = SCEPOS % 2048
struct.pack_into('<I', sd, q+2, NEW0); struct.pack_into('>I', sd, q+6, NEW0)
struct.pack_into('<I', sd, q+10, len(pac)); struct.pack_into('>I', sd, q+14, len(pac))
cambios[DIRLBA + SCEPOS // 2048] = bytes(sd)
_sd2 = bytearray(cambios.get(_dl + BGDPOS // 2048, ud(_dl + BGDPOS // 2048))); _q2 = BGDPOS % 2048
struct.pack_into('<I', _sd2, _q2+2, NEW1); struct.pack_into('>I', _sd2, _q2+6, NEW1)
struct.pack_into('<I', _sd2, _q2+10, len(bg)); struct.pack_into('>I', _sd2, _q2+14, len(bg))
cambios[_dl + BGDPOS // 2048] = bytes(_sd2)
pvd = bytearray(ud(16)); vs = struct.unpack('<I', pvd[80:84])[0]
newvs = max(vs, NEW1 + nsecB); struct.pack_into('<I', pvd, 80, newvs); struct.pack_into('>I', pvd, 84, newvs)
cambios[16] = bytes(pvd)
print('sectores modificados:', len(cambios))
# 4) escribir
os.makedirs(os.path.dirname(SAL), exist_ok=True); t = time.time()
ya = os.path.getsize(SAL + '.bin') // SS if os.path.exists(SAL + '.bin') else 0
ya = min(ya, total)
with open(SAL + '.bin', 'r+b' if ya else 'wb') as f:
    f.seek(ya * SS); f.truncate(ya * SS); orig.seek(ya * SS); l = ya
    while l < total:
        if time.time() - t > 140: print('parcial %d/%d; repetir el comando' % (l, total)); sys.exit(3)
        n = min(3400, total - l); bl = bytearray(orig.read(n * SS))
        for k in range(n):
            if l + k in cambios:
                raw = bl[k*SS:(k+1)*SS]; bl[k*SS:(k+1)*SS] = disco.sector_form1(l + k, cambios[l + k], bytes(raw[16:24]))
        f.write(bl); l += n
    for k in range(nsec):
        sub = b'\x00\x00\x08\x00\x00\x00\x08\x00' if k < nsec - 1 else b'\x00\x00\x89\x00\x00\x00\x89\x00'
        f.write(disco.sector_form1(NEW0 + k, pac[k*2048:(k+1)*2048].ljust(2048, b'\0'), sub))
    for k in range(nsecB):
        sub = b'\x00\x00\x08\x00\x00\x00\x08\x00' if k < nsecB - 1 else b'\x00\x00\x89\x00\x00\x00\x89\x00'
        f.write(disco.sector_form1(NEW1 + k, bytes(bg[k*2048:(k+1)*2048]), sub))
open(SAL + '.cue', 'w').write('FILE "%s.bin" BINARY\r\n  TRACK 01 MODE2/2352\r\n    INDEX 01 00:00:00\r\n' % os.path.basename(SAL))
print('escrito', SAL, '%.0f s' % (time.time() - t))
