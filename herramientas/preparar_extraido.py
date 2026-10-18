"""Extracts from the ORIGINAL disc image everything the build needs into extraido/ (nothing of the game is stored in the repository).
Usage (from the project root): python herramientas/preparar_extraido.py ["path/to/original.bin"]

Produces:
  extraido/{SLPS_017.94, BIN.PAC, SCE.PAC}   files copied from the ISO9660 filesystem
  extraido/SLPS_017.94.text.bin               executable without its 0x800-byte PS-X EXE header
  extraido/SCE_descomprimido/SCE_NN.bin       every compressed ('ike') SCE.PAC entry, decompressed
  extraido/BGD_{933,957,961}_orig.tim         original images later replaced by the build (controller map, 'Fin' marks)
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ike_descomprimir as IK
SS = 2352
BIN_POR_DEFECTO = 'rom/Sound Novel Evolution 2 - Kamaitachi no Yoru Tokubetsu-hen (Japan).bin'
QUERER = ['SLPS_017.94', 'SCE.PAC', 'BIN.PAC']
BGD_LBA = 5600                       # original BGD.PAC position on the disc
BGD_IMAGENES = {933: 933, 957: 957, 961: 961}   # output name -> entry index in BGD.PAC

def pac(d):
    """Table of (id, start sector) pairs ending in 0xffff + final sector."""
    E = []; p = 0
    while True:
        i, o = struct.unpack_from('<HH', d, p); p += 4
        if i == 0xffff: return E, o
        E.append((i, o))

def preparar(ruta_bin=BIN_POR_DEFECTO, destino='extraido'):
    f = open(ruta_bin, 'rb')
    def ud(l): f.seek(l * SS); return f.read(SS)[24:24 + 2048]
    def leer(lba, n): return b''.join(ud(lba + k) for k in range(n))
    pvd = ud(16); assert pvd[1:6] == b'CD001', 'not a MODE2/2352 ISO9660 image'
    root = pvd[156:190]
    rlba, rsz = struct.unpack('<I', root[2:6])[0], struct.unpack('<I', root[10:14])[0]
    data = leer(rlba, (rsz + 2047) // 2048); p = 0; archivos = {}
    while p < len(data):
        l = data[p]
        if l == 0: p = (p // 2048 + 1) * 2048; continue
        rec = data[p:p + l]; p += l
        nom = rec[33:33 + rec[32]].decode('ascii', 'replace').split(';')[0]
        archivos[nom] = (struct.unpack('<I', rec[2:6])[0], struct.unpack('<I', rec[10:14])[0])
    os.makedirs(destino, exist_ok=True)
    for nom in QUERER:
        lba, sz = archivos[nom]
        open(os.path.join(destino, nom), 'wb').write(leer(lba, (sz + 2047) // 2048)[:sz]); print('extracted', nom, sz)
    exe = open(os.path.join(destino, 'SLPS_017.94'), 'rb').read(); assert exe[:8] == b'PS-X EXE'
    texto = exe[0x800:]; open(os.path.join(destino, 'SLPS_017.94.text.bin'), 'wb').write(texto)
    # SCE.PAC: decompress 'ike' entries
    sce = open(os.path.join(destino, 'SCE.PAC'), 'rb').read(); E, fin = pac(sce); offs = [o for _, o in E] + [fin]
    os.makedirs(os.path.join(destino, 'SCE_descomprimido'), exist_ok=True); n = 0
    for k, (i, o) in enumerate(E):
        e = sce[o * 2048:offs[k + 1] * 2048]
        if e[:5] == IK.MAGIC:
            r, _sz = IK.descomprimir(e, exe=texto); assert r is not None, ('decompression failed', i)
            open(os.path.join(destino, 'SCE_descomprimido', 'SCE_%02d.bin' % i), 'wb').write(r); n += 1
    print('SCE.PAC: %d compressed entries decompressed' % n)
    # BGD.PAC (original, LBA 5600): images used by the build
    tab = leer(BGD_LBA, 16); B, bfin = pac(tab); bo = [o for _, o in B] + [bfin]
    for nombre, k in BGD_IMAGENES.items():
        e = leer(BGD_LBA + B[k][1], bo[k + 1] - B[k][1])
        if e[:5] == IK.MAGIC:
            r, _sz = IK.descomprimir(e, exe=texto); assert r is not None, ('decompression failed', k)
        else: r = e
        assert r[:4] == b'\x10\x00\x00\x00', 'not a TIM: BGD entry %d' % k
        open(os.path.join(destino, 'BGD_%d_orig.tim' % nombre), 'wb').write(r); print('BGD image', nombre, len(r))

if __name__ == '__main__':
    preparar(*(sys.argv[1:2] or [BIN_POR_DEFECTO]))
