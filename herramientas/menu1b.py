"""Cadenas de 1 byte por letra para el impresor de menus del ejecutable (0x80038658), que solo entiende codigos de 2 bytes.
Una cadena que empieza por 0x01 se expande a una pila temporal (codigos de 2 bytes) y se llama al impresor original con ese buffer.
Formato de la cadena 1-byte:  01 { b }* 00
  b = 0x02 c0 c1   -> 2 bytes crudos (codigos de control 'c4', 'rr', 's8', iconos de boton...)
  b = 0x03..0x2f   -> indice en TABLA (puntuacion y acentos; 2 bytes por entrada)
  b = 0x30..0x7a   -> digitos (0x30-39) y letras: codigo = b + 0x821F (b<0x61) o b + 0x8220 (b>=0x61)
El gancho sustituye las 2 primeras instrucciones del impresor ('addiu sp,-0x30' / 'sw s1,0x14(sp)') por 'j ENVOLTORIO; nop'.
Cueva: 0x800720bc (514 B)."""
import struct
R = {'zero': 0, 'at': 1, 'v0': 2, 'v1': 3, 'a0': 4, 'a1': 5, 'a2': 6, 'a3': 7, 't0': 8, 't1': 9, 't2': 10, 't3': 11, 't4': 12, 's1': 17, 'sp': 29, 'ra': 31}
PRINT = 0x80038658
CAVA = 0x800720bc          # zona a cero de 514 B (a cero en todas las partidas guardadas)
LIMITE = CAVA + 514
def I(op, rs, rt, imm): return (op << 26) | (R[rs] << 21) | (R[rt] << 16) | (imm & 0xffff)
def Rr(rs, rt, rd, sa, fn): return (R[rs] << 21) | (R[rt] << 16) | (R[rd] << 11) | (sa << 6) | fn
def asm(prog, base):
    lab = {}; pc = 0
    for it in prog:
        if isinstance(it, str) and it.endswith(':'): lab[it[:-1]] = base + 4 * pc
        else: pc += 1
    out = []
    for it in prog:
        if isinstance(it, str) and it.endswith(':'): continue
        f = it(lab, base + 4 * len(out)) if callable(it) else it
        out.append(f)
    return out, lab
def br(op, rs, rt, l): return lambda lab, pc: I(op, rs, rt, (lab[l] - (pc + 4)) >> 2)
def jj(op, l): return lambda lab, pc: (op << 26) | (((lab[l] if isinstance(l, str) else l) >> 2) & 0x3ffffff)
NOP = 0
def programa(tabla_addr):
    t = tabla_addr; hi = 0x8007; lo = t - 0x80070000          # lhu con desplazamiento sobre lui 0x8007
    assert -0x8000 <= lo < 0x8000
    P = [
        'W:', I(0x24, 'a2', 't0', 0), I(0x09, 'zero', 't1', 1), br(4, 't0', 't1', 'EXP'), NOP,
        I(0x09, 'sp', 'sp', -0x30), jj(2, 0x80038660), I(0x2b, 'sp', 's1', 0x14),
        'EXP:', I(0x09, 'sp', 'sp', -0x190), I(0x2b, 'sp', 'ra', 0x18c), I(0x09, 'a2', 't0', 1), I(0x09, 'sp', 't1', 0x10), Rr('t1', 'zero', 'a2', 0, 0x21),
        'LOOP:', I(0x24, 't0', 't2', 0), I(0x09, 't0', 't0', 1), br(4, 't2', 'zero', 'END'), NOP,
        I(0x09, 'zero', 't3', 2), br(4, 't2', 't3', 'ESC'), NOP,
        I(0x0b, 't2', 't3', 0x30), br(5, 't3', 'zero', 'TAB'), NOP,
        I(0x0b, 't2', 't3', 0x61), I(0x0d, 'zero', 't4', 0x8220), br(4, 't3', 'zero', 'L1'), NOP,
        I(0x0d, 'zero', 't4', 0x821F),
        'L1:', Rr('t2', 't4', 't2', 0, 0x21),
        'ST:', Rr('zero', 't2', 't3', 8, 0x02), I(0x28, 't1', 't3', 0), I(0x28, 't1', 't2', 1), I(0x09, 't1', 't1', 2), jj(2, 'LOOP'), NOP,
        'TAB:', Rr('zero', 't2', 't2', 1, 0x00), I(0x0f, 'zero', 't3', hi), Rr('t3', 't2', 't3', 0, 0x21), I(0x25, 't3', 't2', lo), jj(2, 'ST'), NOP,
        'ESC:', I(0x24, 't0', 't2', 0), I(0x24, 't0', 't3', 1), I(0x09, 't0', 't0', 2), I(0x28, 't1', 't2', 0), I(0x28, 't1', 't3', 1), I(0x09, 't1', 't1', 2), jj(2, 'LOOP'), NOP,
        'END:', I(0x28, 't1', 'zero', 0), jj(3, PRINT), NOP, I(0x23, 'sp', 'ra', 0x18c), I(0x09, 'sp', 'sp', 0x190), Rr('ra', 'zero', 'zero', 0, 0x08), NOP,
    ]
    return P
def construir(irreg):
    """irreg: lista de (caracter, codigo2) -> (palabras, direccion_tabla, bytes_tabla, {car: byte})"""
    assert len(irreg) <= 0x2d
    prog, _ = asm(programa(0x80070000 + 0x1000), CAVA)       # solo para medir
    n = len(prog); tabla = CAVA + 4 * n
    prog, lab = asm(programa(tabla), CAVA)
    tb = bytearray(2 * (3 + len(irreg))); mp = {}
    for k, (ch, code) in enumerate(irreg):
        b = 3 + k; mp[ch] = b; struct.pack_into('<H', tb, 2 * b, code)
    return prog, tabla, bytes(tb), mp, lab
def aplicar(exe, irreg):
    """exe: bytearray (archivo con cabecera, direccion RAM = 0x80010000 + off - 0x800). -> {car: byte}"""
    off = lambda a: a - 0x80010000 + 0x800
    prog, tabla, tb, mp, lab = construir(irreg)
    fin = tabla + len(tb); assert fin <= LIMITE, 'cueva insuficiente: %d B de mas' % (fin - LIMITE)
    assert all(b == 0 for b in exe[off(CAVA):off(fin)]), 'cueva ocupada'
    assert struct.unpack_from('<II', exe, off(PRINT)) == (0x27bdffd0, 0xafb10014), 'impresor distinto'
    for k, w in enumerate(prog): struct.pack_into('<I', exe, off(CAVA) + 4 * k, w)
    exe[off(tabla):off(tabla) + len(tb)] = tb
    struct.pack_into('<II', exe, off(PRINT), (2 << 26) | ((lab['W'] >> 2) & 0x3ffffff), 0)
    return mp
