"""sim_motor.py: ejecuta el impresor de texto REAL del EXE (0x80039288) en unicorn/MIPS sobre texto ya compilado y devuelve la posicion (x,y) de cada glifo.
La RAM (EXE parcheado + fuente con los glifos latinos) sale de un savestate de DuckStation (carpeta duckstation/savestates)."""
import os, struct, glob, sys
import zstandard as zstd
from unicorn import *
from unicorn.mips_const import *
GP = 0x8007913c; B = 0x80080000; RA = 0x80000004; BUF = 0x800cb010
def ram_de_savestate(ruta):
    b = open(ruta, 'rb').read(); i = b.find(b'\x28\xb5\x2f\xfd'); out = []
    while i >= 0:
        try: out.append(zstd.ZstdDecompressor().decompressobj().decompress(b[i:]))
        except Exception: pass
        i = b.find(b'\x28\xb5\x2f\xfd', i + 1)
    cuerpo = max(out, key=len); return cuerpo[0x1a62:0x1a62 + 0x200000]
class Motor:
    def __init__(self, ram):
        self.mu = mu = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 + UC_MODE_LITTLE_ENDIAN)
        ram = bytearray(ram)
        # los jal a funciones de dibujo/GPU/sonido (fuera del impresor y de la busqueda de glifo 0x80044dd0) se anulan: v0=0 y el hueco de retardo se ejecuta normal
        for a in range(0x80038000, 0x8003b000, 4):
            o = a & 0x1fffffff; wd = struct.unpack_from('<I', ram, o)[0]
            if wd >> 26 == 3:
                tgt = ((a + 4) & 0xf0000000) | ((wd & 0x3ffffff) << 2)
                if not (0x80038000 <= tgt < 0x8003b000 or tgt == 0x80044dd0): struct.pack_into('<I', ram, o, 0x00001021)     # move $v0,$zero
        mu.mem_map(0, 0x200000); mu.mem_write(0, bytes(ram)); self.ram0 = bytes(ram); self.log = []; self.esperas = []
        mu.hook_add(UC_HOOK_CODE, self._h, begin=0x800380ec, end=0x800380ec)
    def _h(self, uc, addr, size, _):
        self.log.append((uc.reg_read(UC_MIPS_REG_A0) & 0xffff, uc.reg_read(UC_MIPS_REG_A1) & 0xffff, uc.reg_read(UC_MIPS_REG_A2) & 0xffff))
    def w(self, a, b): self.mu.mem_write(a & 0x1fffffff, b)
    def r(self, a, n): return bytes(self.mu.mem_read(a & 0x1fffffff, n))
    def u8(self, a): return self.r(a, 1)[0]
    def u16(self, a): return struct.unpack('<H', self.r(a, 2))[0]
    def u32(self, a): return struct.unpack('<I', self.r(a, 4))[0]
    @property
    def x(self): return self.u16(0x800794b8)
    @property
    def y(self): return self.u16(0x800794bc)
    def frame(self):
        mu = self.mu; mu.reg_write(UC_MIPS_REG_SP, 0x801FFF00); mu.reg_write(UC_MIPS_REG_GP, GP); mu.reg_write(UC_MIPS_REG_RA, RA)
        mu.emu_start(0x80039288, RA, count=400000)
    def pagina(self, x=8, y=17, xo=8):
        """pagina limpia: cursor al origen"""
        self.w(0x800794b8, struct.pack('<H', x)); self.w(0x800794b0, struct.pack('<H', xo)); self.w(0x800794bc, struct.pack('<H', y))
        for off in (-0x6aac, -0x6b12, -0x6b10, -0x6a30, -0x6ae6, -0x6b00, -0x6b32): self.w(B + off, b'\0')
        self.w(B - 0x6bc6, b'\0')
    def origen(self, xo, x=None):
        self.w(0x800794b0, struct.pack('<H', xo))
        if x is not None: self.w(0x800794b8, struct.pack('<H', x))
    def imprimir(self, datos, maxf=4000):
        """imprime una unidad de texto (bytes sin el NUL final): el motor la termina solo al llegar al NUL (puntero a 0); las esperas p/P/pg
        se 'pulsan' automaticamente. -> lista de (x,y,glifo) nuevos"""
        n0 = len(self.log); x, y, xo = self.x, self.y, self.u16(0x800794b0)
        self.mu.mem_write(0, self.ram0); self.pagina(x=x, y=y, xo=xo)       # estado limpio del motor (como un texto recien iniciado); solo se arrastra el cursor
        self.w(BUF, bytes(datos) + b'\0\0\0\0'); self.w(0x800794c0, struct.pack('<I', BUF)); self.w(B - 0x6bc6, b'\0')
        for k in range(maxf):
            self.frame()
            if self.u8(B - 0x6bc6): self.esperas.append((self.x, self.y)); self.w(B - 0x6bc6, b'\0'); self.w(B - 0x6aac, b'\0')     # (x,y) donde se dibuja el icono de espera; # espera: tecla
            if self.u32(0x800794c0) < BUF: break
        else: raise RuntimeError('unidad sin terminar')
        if bytes(datos).endswith(b'g'):      # 'g' al final de la unidad: el interprete limpia la pagina antes del siguiente texto (cursor al origen, y=17)
            xo = self.u16(0x800794b0); self.pagina(x=xo, y=17, xo=xo)
        return [(x, y, g) for x, y, g in self.log[n0:]]
