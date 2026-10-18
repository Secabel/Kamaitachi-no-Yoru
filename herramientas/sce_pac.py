"""Reempaquetado de SCE.PAC (Kamaitachi no Yoru TH): entradas SIN comprimir (el cargador solo descomprime si hay magia 'ike').
- codificar_es(txt, mapa): texto con codigos de control ASCII (r p P g n2 ...) y letras latinas -> bytes (letras = SJIS de 2 bytes)
- reinsertar(fr, reemplazos): fr = fragmento, reemplazos {pos_del_comando: bytes_nuevos_del_texto}
- construir_entrada(lista_de_fragmentos), construir_pac(dict id->bytes, primer_sector)"""
import struct, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scriptparse as SP
AQUI = os.path.dirname(os.path.abspath(__file__))
MAPA = json.load(open(os.path.join(AQUI, '..', 'tablas', 'mapa_caracteres_es.json'), encoding='utf-8'))

SINGLE = 'abcdefghijklmnopqrstuvwxyz' + 'áéíóúñü' + 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' + '.,' + '-:'   # 63 caracteres de 1 byte (A1..DF); ver parche_exe.py
def codificar_es(txt):
    """Cada caracter del mapa -> 2 bytes SJIS. Los codigos de control se escriben entre llaves: {r} {p} {P} {g} {n2} {c1} {w5}...
    se emiten como ASCII literal (sin llaves)."""
    out = bytearray(); k = 0
    while k < len(txt):
        if txt[k] == '{':
            j = txt.index('}', k); c = txt[k+1:j]; k = j + 1
            if c == '#PAGINA': out += b'pg\x00\x00'     # fin de pagina: cierra la unidad de texto y abre otra (op 00)
            else: out += c.encode('ascii')
            continue
        ch = txt[k]; k += 1
        if ch in SINGLE: out.append(0xA1 + SINGLE.index(ch)); continue
        c = MAPA[ch]; out += bytes([c >> 8, c & 255])
    return bytes(out)

def reinsertar(fr, reemplazos):
    import verificador as _V; cmds, motivo = _V.parse(fr); assert motivo == 'ok', motivo
    pos = [c[0] for c in cmds] + [len(fr)]
    out = bytearray()
    for n, (p, op, a) in enumerate(cmds):
        if p in reemplazos:
            assert op in (0, 0x17)
            out += bytes([op]) + (bytes(a[:1]) if op == 0x17 else b'') + reemplazos[p] + b'\0'
        else:
            out += fr[p:pos[n+1]]
    return bytes(out)

def construir_entrada(frs):
    n = len(frs); cab = 2 * n; off = cab; tabla = []
    for f in frs: tabla.append(off); off += len(f)
    assert off < 65536, 'entrada >64 KB: offsets de fragmento u16'
    return struct.pack('<%dH' % n, *tabla) + b''.join(frs)

def construir_pac(entradas, primer_sector=None, orden=None):
    """entradas: {id: bytes}. Devuelve bytes del PAC (tabla + entradas alineadas a 2048)."""
    ids = orden or sorted(entradas)
    hdr_sect = primer_sector or ((len(ids) * 4 + 4 + 2047) // 2048)
    sec = hdr_sect; tabla = bytearray(); datos = bytearray()
    for i in ids:
        tabla += struct.pack('<HH', i, sec)
        e = entradas[i]; ns = (len(e) + 2047) // 2048
        datos += e + b'\0' * (ns * 2048 - len(e)); sec += ns
    tabla += struct.pack('<HH', 0xffff, sec)
    return bytes(tabla) + b'\0' * (hdr_sect * 2048 - len(tabla)) + bytes(datos)
