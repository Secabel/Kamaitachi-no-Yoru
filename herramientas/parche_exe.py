"""Parches del ejecutable SLPS_017.94 (archivo completo con cabecera PS-EXE de 0x800 B; direccion RAM = 0x80010000 + off - 0x800).
1) Caracteres de 1 byte (0xA1..0xDF): el manejador generico de caracteres (0x8003a29c) lee 2 bytes; si el primero esta en A1..DF
   usa solo 1 byte (codigo = el byte) -> cueva en 0x8006ab90 (384 B a cero en todas las partidas guardadas).
2) Tabla hash de glifos (0x8006b754, 4096 x (u16 codigo, s16 indice), vacio = ffff,0): se anaden los codigos 00A1..00DF apuntando al glifo latino ya existente.
Uso: aplicar(exe_bytearray, glifo_index_fn, SINGLE) """
import struct
R = dict(zero=0, at=1, v0=2, v1=3, a0=4, a1=5, a2=6, a3=7)
def I(op, rs, rt, imm): return (op << 26) | (R[rs] << 21) | (R[rt] << 16) | (imm & 0xffff)
def lbu(rt, off, rs): return I(0x24, rs, rt, off)
def sw(rt, off, rs): return I(0x2b, rs, rt, off)
def addiu(rt, rs, imm): return I(0x09, rs, rt, imm)
def sltiu(rt, rs, imm): return I(0x0b, rs, rt, imm)
def ori(rt, rs, imm): return I(0x0d, rs, rt, imm)
def beq(rs, rt, off): return I(0x04, rs, rt, off)
def j(addr): return (2 << 26) | ((addr >> 2) & 0x3ffffff)
def sll(rd, rt, sa): return (R[rt] << 16) | (R[rd] << 11) | (sa << 6)
def orr(rd, rs, rt): return (R[rs] << 21) | (R[rt] << 16) | (R[rd] << 11) | 0x25
def move(rd, rs): return (R[rs] << 21) | (R[rd] << 11) | 0x21
NOP = 0
CAVA = 0x8001187c        # ANTES 0x8006ab90: ESA ZONA ES EL BUFFER DE CABECERA DE LA TARJETA (el guardado copia 0x180 B ahi y destruia la cueva -> cuelgue). Ahora en la cola estatica del 2.o hueco de cadenas del EXE (hasta 0x800118c4; despues van los nombres por defecto)
RET = 0x8003a2b8        # 'bne a1,v0,...' del manejador original
HOOK = 0x8003a29c       # 'lbu a0,(v0)' original
HASH = 0x8006b754
def cueva():
    c = []
    c += [lbu('a0', 0, 'v0'), lbu('a1', 1, 'v0'), addiu('at', 'a0', -0xA1), sltiu('at', 'at', 0x3F)]
    base = len(c)                    # indice de beqz
    c += [None, NOP]
    c += [addiu('v0', 'v0', 1), sw('v0', 0, 'v1'), move('a1', 'a0'), sll('a0', 'a0', 8), j(RET), ori('v0', 'zero', 0x8177)]
    two = len(c)
    c += [addiu('v0', 'v0', 2), sw('v0', 0, 'v1'), sll('a0', 'a0', 8), orr('a1', 'a1', 'a0'), j(RET), ori('v0', 'zero', 0x8177)]
    c[base] = beq('at', 'zero', two - (base + 1))
    return c
def off(a): return 0x800 + a - 0x80010000
def poner_cueva(exe):
    c = cueva(); assert CAVA + 4 * len(c) <= 0x800118c4
    assert all(x == 0 for x in exe[off(CAVA):off(0x800118c4)]), 'cueva ocupada'
    for k, w in enumerate(c): struct.pack_into('<I', exe, off(CAVA) + 4 * k, w)
def aplicar(exe, indice_glifo, single):
    """exe: bytearray del archivo SLPS; single: lista de caracteres (<=63) para los bytes A1.. ; indice_glifo(ch)->indice de glifo en la fuente."""
    assert len(single) <= 0x3F
    c = cueva(); assert CAVA + 4 * len(c) <= 0x800118c4
    assert struct.unpack_from('<I', exe, off(HOOK))[0] == lbu('a0', 0, 'v0')
    struct.pack_into('<II', exe, off(HOOK), j(CAVA), NOP)          # la cueva en si la escribe poner_cueva(), DESPUES de que menus_exe vacie el hueco
    ocupado = {}
    for k, ch in enumerate(single):
        code = 0xA1 + k; idx = indice_glifo(ch)
        v = (code + 0x7ec0) & 0xffff; h = ((v - ((v & 0xff00) >> 2)) * 5) & 0xfff
        while True:
            cd, ix = struct.unpack_from('<Hh', exe, off(HASH) + 4 * h)
            if cd == 0xffff: break
            assert cd != code, 'codigo ya en la tabla'
            h += 1; assert h < 0x1000
        struct.pack_into('<Hh', exe, off(HASH) + 4 * h, code, idx)
    return exe
