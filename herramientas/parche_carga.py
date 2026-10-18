"""Parche del cargador de scripts: entradas SCE partidas en 2 piezas SIN cambiar ningun ID de script.
El cargador principal (0x8001bfb8) calcula entrada = ID/1000 y carga esa entrada del SCE.PAC (pac 2). Aqui, justo despues de calcular
la entrada, una cueva mira la tabla CUT[entrada] (0 = sin partir): si frag = ID%1000 >= CUT -> entrada = NEW[entrada] (id de la pieza 2 en el PAC).
Las dos piezas conservan una tabla de fragmentos de longitud completa (los fragmentos de la otra pieza apuntan al final de los datos).
Cueva en 0x800721e0.. (justo detras del codigo de menu1b, dentro de la zona estatica a cero 0x800720bc..0x800722be), tablas CUT/NEW (32 B cada una, entradas < 32).
ANTES estaba en 0x8006abe0, dentro del buffer de cabecera de la tarjeta: el guardado lo sobrescribia (cuelgue/pantalla negra al cargar escenas).
aplicar(exe_bytearray, {entrada: (corte, id_pieza2)})"""
import struct
R = dict(zero=0, at=1, v0=2, v1=3, a0=4, a1=5, a2=6, a3=7, t0=8, t1=9, t2=10, t3=11, t4=12, s3=19, gp=28)
def I(op, rs, rt, imm): return (op << 26) | (R[rs] << 21) | (R[rt] << 16) | (imm & 0xffff)
def RT(rs, rt, rd, sa, fn): return (R[rs] << 21) | (R[rt] << 16) | (R[rd] << 11) | (sa << 6) | fn
def lbu(rt, off, rs): return I(0x24, rs, rt, off)
def sb(rt, off, rs): return I(0x28, rs, rt, off)
def lui(rt, imm): return I(0x0f, 'zero', rt, imm)
def ori(rt, rs, imm): return I(0x0d, rs, rt, imm)
def andi(rt, rs, imm): return I(0x0c, rs, rt, imm)
def sltiu(rt, rs, imm): return I(0x0b, rs, rt, imm)
def beq(rs, rt, off): return I(0x04, rs, rt, off)
def bne(rs, rt, off): return I(0x05, rs, rt, off)
def addu(rd, rs, rt): return RT(rs, rt, rd, 0, 0x21)
def subu(rd, rs, rt): return RT(rs, rt, rd, 0, 0x23)
def sltu(rd, rs, rt): return RT(rs, rt, rd, 0, 0x2b)
def multu(rs, rt): return RT(rs, rt, 'zero', 0, 0x19)
def mflo(rd): return RT('zero', 'zero', rd, 0, 0x12)
def srl(rd, rt, sa): return RT('zero', rt, rd, sa, 0x02)
def j(a): return (2 << 26) | ((a >> 2) & 0x3ffffff)
NOP = 0
HOOK = 0x8001bff0       # srl v0,a3,6   (siguiente: sb v0,0x330(gp))
VUELTA = 0x8001bff8     # lbu s2,0x330(gp)
CODIGO = 0x800721e0
CUT = 0x80072244
NEW = 0x80072264
LIMITE = 0x800722be
NENT = 32
def cueva():
    c = [srl('v0', 'a3', 6), sltiu('t1', 'v0', NENT), None, NOP,
         lui('t0', 0x8007), addu('t0', 't0', 'v0'), lbu('t1', CUT - 0x80070000, 't0'), andi('t2', 's3', 0xffff),
         None, NOP,
         ori('t3', 'zero', 1000), multu('v0', 't3'), NOP, NOP, mflo('t3'), subu('t2', 't2', 't3'),
         sltu('t4', 't2', 't1'), None, NOP,
         lbu('v0', NEW - 0x80070000, 't0'), NOP]
    hecho = len(c)
    c += [sb('v0', 0x330, 'gp'), j(VUELTA), NOP]
    c[2] = beq('t1', 'zero', hecho - 3); c[8] = beq('t1', 'zero', hecho - 9); c[17] = bne('t4', 'zero', hecho - 18)
    return c
def off(a): return 0x800 + a - 0x80010000
def aplicar(exe, cortes):
    c = cueva(); assert CODIGO + 4 * len(c) <= CUT and NEW + NENT <= LIMITE
    zona = lambda a, n: all(x == 0 for x in exe[off(a):off(a) + n])
    assert zona(CODIGO, NEW + NENT - CODIGO), 'cueva ocupada'
    assert struct.unpack_from('<II', exe, off(HOOK)) == (srl('v0', 'a3', 6), sb('v0', 0x330, 'gp')), 'el cargador no es el esperado'
    for k, w in enumerate(c): struct.pack_into('<I', exe, off(CODIGO) + 4 * k, w)
    for e, (corte, nuevo) in cortes.items():
        assert 0 <= e < NENT and 0 < corte < 256 and 42 <= nuevo < 256, (e, corte, nuevo)
        exe[off(CUT) + e] = corte; exe[off(NEW) + e] = nuevo
    struct.pack_into('<II', exe, off(HOOK), j(CODIGO), NOP)
    return exe
