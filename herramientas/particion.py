"""Particion de entradas SCE grandes en 2 piezas SIN cambiar IDs (ver parche_carga.py).
dividir(ents, cortes, primer_id=42) -> (ents_nuevas, tabla_parche {entrada: (corte, id_pieza2)})
 - pieza 1 = frags [0:corte] (+ `01 <ID E*1000+corte>` al final del frag corte-1, por si cae al siguiente)
 - pieza 2 (id nuevo) = frags [corte:]
 - las dos conservan tabla de n offsets (los frags de la otra pieza quedan con longitud 0).
reunir(ents_nuevas, tabla) -> ents originales (para comprobar que no se pierde nada, quitando el salto anadido)
elegir_cortes(ents, tamano_unidad, limite) -> {entrada: corte} para las que superan el limite."""
import struct, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verificador as V
LIMITE = 0xB000 - 0x800     # margen de seguridad bajo el buffer de 0xB000

def _tabla(frs_datos, n, base_vacios):
    """frs_datos: {indice_frag: bytes}. Devuelve entrada con tabla de n offsets; frags ausentes tienen longitud 0."""
    cab = 2 * n; off = cab; tab = []; cuerpo = b''
    for k in range(n):
        tab.append(off)
        d = frs_datos.get(k, b''); cuerpo += d; off += len(d)
    assert off < 65536
    return struct.pack('<%dH' % n, *tab) + cuerpo

def dividir(ents, cortes, primer_id=42):
    out = dict(ents); tabla = {}; nuevo = primer_id
    for e, corte in sorted(cortes.items()):
        fr, m = V.frags(ents[e]); assert not m, (e, m)
        n = len(fr); assert 0 < corte < n
        datos = [ents[e][s:t] for s, t in fr]
        # el ultimo fragmento de la pieza 1 salta explicitamente al primero de la pieza 2
        datos[corte - 1] = datos[corte - 1] + b'\x01' + struct.pack('<H', e * 1000 + corte)
        out[e] = _tabla({k: datos[k] for k in range(corte)}, n, 0)
        out[nuevo] = _tabla({k: datos[k] for k in range(corte, n)}, n, 0)
        tabla[e] = (corte, nuevo); nuevo += 1
    return out, tabla

def reunir(ents, tabla):
    out = {k: v for k, v in ents.items() if k not in {n for _, n in tabla.values()}}
    for e, (corte, nuevo) in tabla.items():
        f1, _ = V.frags(ents[e]); f2, _ = V.frags(ents[nuevo]); n = len(f1)
        datos = [ents[e][s:t] for s, t in f1[:corte]] + [ents[nuevo][s:t] for s, t in f2[corte:]]
        assert datos[corte - 1][-3:] == b'\x01' + struct.pack('<H', e * 1000 + corte)
        datos[corte - 1] = datos[corte - 1][:-3]
        cab = 2 * n; off = cab; tab = []
        for d in datos: tab.append(off); off += len(d)
        out[e] = struct.pack('<%dH' % n, *tab) + b''.join(datos)
    return out

def elegir_cortes(ents, tam_frag, limite=LIMITE):
    """tam_frag(entrada, frag) -> tamano estimado del fragmento ya en espanol. Devuelve {entrada: corte} equilibrando las dos mitades."""
    cortes = {}
    for e, d in ents.items():
        fr, m = V.frags(d)
        if m: continue
        z = [tam_frag(e, k) for k in range(len(fr))]
        if 2 * len(fr) + sum(z) <= limite: continue
        tot = sum(z); acc = 0
        for k, x in enumerate(z):
            acc += x
            if acc >= tot / 2: break
        c = k + 1; c = min(max(c, 1), len(fr) - 1)
        assert 2 * len(fr) + sum(z[:c]) + 3 <= limite and 2 * len(fr) + sum(z[c:]) <= limite, ('no cabe en 2 piezas', e)
        cortes[e] = c
    return cortes
